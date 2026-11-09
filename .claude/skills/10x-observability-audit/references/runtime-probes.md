# Runtime probes: proving what the tracker sees

A probe run answers, for each failure shape: what the user gets (HTTP
result / UI), what the platform logs show, and what reaches the error
tracker (and in what shape). It turns "this looks invisible" into "this was
invisible when we tried it".

## Safety rules (non-negotiable)

- **Isolated copy only.** `git worktree add` into a temp path, or the
  subagent `isolation: "worktree"` option. The main working tree is never
  edited.
- **No real telemetry, no real data.** The tracker is pointed at the local
  fake ingest; databases and third parties are local, emulated or stubbed.
  If booting needs production credentials, stop and report the blocker.
- **No commits, pushes or deploys** from the probe copy.
- Secrets may be _copied_ into the isolated copy's local env file if the
  project already keeps local dev secrets; never print their values.

## 1. Fake ingest endpoint

`scripts/fake-ingest.mjs` (bundled with this skill) is a zero-dependency Node
HTTP server that accepts any POST, decompresses gzip/deflate/br, and appends
`{at, method, url, headers, body}` as one JSON line per request.

```bash
node <skill-dir>/scripts/fake-ingest.mjs --port 9876 --out probe/ingest.jsonl
```

Point the tracker at it:

| Tracker                                            | How                                                                                                                                                                                                                                                             |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sentry (any SDK)                                   | DSN `http://publickey@127.0.0.1:9876/1`. Bodies are _envelopes_: newline-separated JSON, header line then item-header/payload pairs; `type: event` holds `exception.values[].stacktrace.frames`, `message`, `tags`, `level`; `type: log` holds structured logs. |
| OpenTelemetry                                      | OTLP/HTTP exporter endpoint `http://127.0.0.1:9876` with JSON protocol (`OTEL_EXPORTER_OTLP_PROTOCOL=http/json`).                                                                                                                                               |
| Datadog / Rollbar / Bugsnag / Honeybadger / others | Override the intake/endpoint URL option the SDK exposes (most have one for proxies or EU regions). If none exists, intercept the SDK's transport or stub its `notify/capture` function to write to a file.                                                      |
| No tracker                                         | Skip the ingest; record only response + logs. The finding is then "nothing is tracked" in the report's capture model.                                                                                                                                           |

Check the project's "is reporting enabled?" gate (env name, DSN resolver,
`NODE_ENV`). You may need a non-production env value that still enables
reporting. Prefer setting env vars over editing that gate.

## 2. Boot the app like production

Use the production build and the production runtime emulator where one
exists (e.g. `wrangler dev` on the built worker, `vercel dev`, `sam local`,
the production Docker image, `NODE_ENV=production` start). A dev server with
hot reload often has different error handling (overlays, no streaming, a
different logger), so results from it don't transfer.

## 3. Probe catalog

Inject each shape behind a trigger (e.g. `?probe=<id>`, a header, or a
dedicated probe route) so one build serves every probe. Pick targets inside
the audited flows where possible.

| id  | Failure shape                                                          | Typical injection                                     |
| --- | ---------------------------------------------------------------------- | ----------------------------------------------------- |
| P1  | Throw in a request handler / page (control: expected to be captured)   | `throw new Error('probe-handler')`                    |
| P2  | Throw in a handler that uses the project's reporting wrapper (control) | same, in a wrapped route                              |
| P3  | Throw in a handler **outside** the wrapper/boundary                    | same, in an unwrapped route                           |
| P4  | Handler **returns** 5xx without throwing                               | return a 500 response                                 |
| P5  | Throw in early middleware / filter / bootstrap                         | throw when trigger is present                         |
| P6  | Error result ignored (DB/HTTP client returns error, code continues)    | query a missing table, ignore the error               |
| P7  | Unhandled promise rejection / floating async error                     | `void Promise.reject(new Error('probe'))`             |
| P8  | Background task fails after the response                               | failing job/`waitUntil`/queue message                 |
| P9  | Error object passed to the structured logger                           | `log.error({ error: new Error('probe', { cause }) })` |
| P10 | Failure after streaming starts (SSR/stream)                            | throw inside a component/stream chunk                 |
| P11 | Client-side: uncaught error, rejected fetch, lazy-chunk load failure   | via the browser (optional; needs a headless browser)  |

## 4. Script it

Write a `suite` script (shell or node) inside the isolated copy that: starts
the fake ingest with a fresh output file, boots the app, waits for health,
fires each probe, waits a few seconds (trackers flush asynchronously),
snapshots the new log lines and ingest lines per probe, and tears
everything down. The script is what makes before/after proof possible:
apply a fix, rebuild, run the identical suite, diff.

Summarize per probe in one or two lines: `EXCEPTION <type>: <value> |
frames=<n> handled=<bool> | tags` / `MESSAGE [level] …` / `LOG [level] …` /
`(nothing)`.

## 5. Report honestly

- Mark every row **observed** or **inferred**.
- Local emulators aren't production. Say which platform behaviour
  (log retention, invocation outcome, alerting) was not observable.
- List every file changed in the isolated copy and the rerun command.
- Leave the copy in place and tell the user where it is. It's the harness
  for proving fixes later.
