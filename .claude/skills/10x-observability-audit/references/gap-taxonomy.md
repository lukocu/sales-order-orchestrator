# Observability gap taxonomy

Every finding gets exactly one primary category and one severity. The
categories are stack-agnostic mechanisms; the examples show how each looks in
different ecosystems so auditors recognise them in any codebase.

## Categories

### coverage-gap — code runs where the error tracker cannot see it

The tracker is initialised per request, per route, or per process, and some
code executes outside every such scope. `capture*` calls there silently
no-op, and uncaught exceptions only reach raw platform logs.

- Middleware/filters ordered _before_ the tracker's middleware.
- Routes that opt out of (or were never wrapped in) a reporting wrapper.
- Background work after the response: `waitUntil`, `setImmediate`, goroutines,
  Celery/Sidekiq/BullMQ jobs, cron, queue consumers, separate worker binaries
  without their own init.
- Streamed response bodies (SSR streaming, SSE, chunked NDJSON): errors
  after the first byte cannot change the status and escape status-based
  capture.
- Client-side: framework error handling that catches before the global
  handler (hydration/chunk-load errors, error boundaries that render a
  fallback without reporting, `try/catch` around app bootstrap).
- Unhandled promise rejections / uncaught exceptions with no global handler.

### swallowed — the error is caught and disappears

`catch {}` / `except: pass` / `rescue nil` / `.catch(() => null)` /
`_ = err` / `if err != nil { return nil }`, returning a default, an empty
list, `false`, or a fallback UI, with no log and no report.

### logged-not-captured — only a log line, no alert

The failure is written to console/stdout/log service but never becomes an
issue or alert. Includes `log.error` that is only searchable if you already
know to look, and log forwarding that lands in a "logs" product rather than
the issue stream.

### flattened-response — a real failure becomes an ordinary response

Server-side failures returned as 4xx, redirects with an error query param,
`200 {ok:false}`, `202 accepted`, an error event inside a 200 stream, or a
generic 500/503 with the cause discarded. Status-code-based monitoring
cannot see most of these, and support sees misleading symptoms ("check
your input", "unknown error").

### missing-throw — an error result is treated as a normal outcome

Result-style errors ignored: Supabase/PostgREST `{ error }`, Go `err`, Rust
`Result` unwrapped to default, `fetch` without `res.ok` check, HTTP client
not raising on 4xx/5xx, `null` from a failed lookup treated as "not found"
or "no access".

### identity-lost — the error survives but its diagnosis doesn't

`new Error('X failed')` without `cause`, `String(err)` / `str(e)`,
re-raising without chaining (`raise X from e` missing), mapping to an enum
and dropping status/DB code, logger turning error objects into `{}` or
`[object Object]`, stack replaced on rethrow, messages truncated.

### missing-context — the event can't be tied to a user, entity or step

No route/operation tag, no user or tenant id, no entity id (order, lesson,
document), no request/trace id, no stage within a multi-step flow; or
over-redaction removing the only identifier with no hashed/id replacement.

### config — tracker/logger setup _in code_ degrades every event

Only for settings you can cite in the repo that actively make events worse:
sampling in code that drops errors, scrubbing hooks that rewrite stack
frames/breadcrumbs/fields they shouldn't, ignore lists that match
first-party errors, init code that passes no release/environment when the
SDK needs it from code, an `enabled`/DSN gate in code that turns reporting
off in a production deploy target.

**Not a finding:** a platform or vendor setting that is absent from the
repo, such as log collection not enabled in the deploy config
(`wrangler.toml`, `vercel.json`, `serverless.yml`, Helm values), no log
forwarding, no alert rules, no source-map/symbol upload step you can see,
or a tracker key missing from the example env file. These are often set in a
dashboard. List them under the report's _Assumptions_. Never use them as a
root cause or rate them above `low`, and even `low` only when the user
confirmed the setting is really off.

`config` is the least important category in this audit. Most runs should
have few or none.

### noise — expected conditions drown real signal

Validation errors, user cancellations, aborted requests, optimistic
concurrency conflicts, planned kill-switch responses reported as errors;
duplicate reporting of one failure; high-cardinality messages (raw URLs
with ids) creating one issue per entity.

## Severity rubric

Judge severity by the flow's importance and by what a responder would get,
**assuming the monitoring pipeline is on in production**. A gap is
critical because of what the code does with the error, never because a
dashboard setting might be off.

| Severity     | Meaning                                                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **critical** | A realistic production failure in a critical flow would be **invisible** (no issue, no alert, maybe not even a log) or would affect many users before anyone could tell what broke. Also: a gap that disables a previous fix's regression signal. |
| **high**     | The failure is visible but **undiagnosable**: no stack/cause/status, wrong category (bug reported as outage or user error), or visible only in logs nobody alerts on, in an important flow.                                                       |
| **medium**   | Diagnosable with effort (missing entity context, grouping problems, secondary flows), or a noise source that meaningfully hides real issues.                                                                                                      |
| **low**      | Polish: unmapped user-facing error codes, minor context gaps, cosmetic grouping.                                                                                                                                                                  |

## Finding format

```
| # | Location (file:line) | Category | Severity | What happens in production | Fix direction |
```

"What happens in production" must describe the observable outcome for
users _and_ for responders, e.g. "Payment provider 5xx → user sees generic
error, response is 200 `{ok:false}`, no issue, no log with provider status."
