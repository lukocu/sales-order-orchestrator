# Mocking External APIs the App Calls

**E2E ≠ zero mocking**: auth, routing and the database stay real, while
expensive or non-deterministic external APIs (LLMs, payment gateways) are mocked
at the network layer. Where you mock depends on **who makes the call**.

## First, find the caller

Search for the API's host or client (e.g. `openrouter.ai`, the SDK import) and
read where the `fetch` runs:

- **In the browser** (a client component calls the API directly): mock it in the
  spec with `page.route('**/api.example.com/**', …)`. No app change is needed.
- **On the server** (an API route, SSR code, a Worker): the request never passes
  through the browser, so `page.route()` doesn't see it, and the test would call
  the real API, with its cost, quota and non-determinism. Use the pattern below.

## Server-side calls: a local mock server

The pattern below was verified on an Astro 6 app (Cloudflare adapter) that calls
OpenRouter from the server.

### 1. An env-overridable base URL (a production change, so ask first)

The app's client gets an optional base URL. When it is unset (production, dev)
nothing changes; the E2E run points it at the mock:

```typescript
// OPENROUTER_BASE_URL is unset in production. Local E2E runs point it at the
// mock in tests/e2e/mocks/openrouter-mock.mjs.
const OPENROUTER_URL = `${OPENROUTER_BASE_URL ?? "https://openrouter.ai/api/v1"}/chat/completions`;
```

- This edits production code, so show the user the diff and wait for their
  approval before you make it. It is not part of the test. Ask it as a question:
  "Mocking <API> needs a production change: <diff summary>. Approve?" with the
  options **Approve (Recommended)** (unset in production, so behaviour is
  unchanged) and **Reject** (then the flow's API call can't be mocked; stop and
  say which facet stays untested).
- Declare the variable the way the app declares its env. For example, with
  Astro's typed env add an optional server secret:
  `OPENROUTER_BASE_URL: envField.string({ context: 'server', access: 'secret', optional: true })`.
- If unit tests mock the env module (e.g. `vi.mock('astro:env/server', …)`), add
  the new name there too, otherwise those suites fail on the missing export.
  Run the unit suite after the change.

### 2. A small local mock server

`tests/e2e/mocks/<api>-mock.mjs`, built on `node:http` with no dependencies:

- answers `GET` with 200, so the `webServer` entry's `url` check knows it is up;
- returns **schema-valid** responses for the calls the flow needs, and echoes
  the test's unique token from the request into the response (e.g.
  `E2E-<timestamp>`), so each test's data is unique and assertable;
- answers every call it doesn't recognise with an error (e.g. 503) rather than
  a guess. Only rely on that when the app treats the failure as non-fatal;
- reads its port from an env variable (e.g. `E2E_<API>_MOCK_PORT`, with a free
  default).

### 3. An extra `webServer` entry, before the app entry

Turn `webServer` into an array. Put the mock first and leave the app entry's own
fields as `/10x-e2e-setup` wrote them — the one exception is the prep hook in
step 4, which may extend the app entry's `command` (or add an `env` key) so this
build talks to the mock:

```typescript
const MOCK_PORT = Number(process.env.E2E_OPENROUTER_MOCK_PORT ?? 3199);

webServer: [
  {
    // Server-side calls can't be caught by page.route(), so the app calls this mock.
    command: 'node tests/e2e/mocks/openrouter-mock.mjs',
    env: { OPENROUTER_MOCK_PORT: String(MOCK_PORT) },
    url: `http://localhost:${MOCK_PORT}`,
    reuseExistingServer: !process.env.CI,
  },
  { /* the app entry: build + preview on PORT, url: baseURL (setup's) */ },
],
```

This is the one config change `/10x-e2e` makes. `/10x-e2e-setup` owns the app
entry and the fields `test-stack.md` records, and its re-run ignores extra
entries. Tell the user what you added.

Before the first run, check the mock port is free (`lsof -nP -iTCP:<port> -sTCP:LISTEN`):
with `reuseExistingServer` a stranger on that port would silently answer as the
mock. Add `stdout: "pipe"` to the mock entry while you debug, so its request log
shows up as `[WebServer]` lines.

### 4. Point only the E2E build at the mock

When the preview is a server that reads its process environment (e.g. a Node
server), an `env` key on the app entry is enough:
``env: { OPENROUTER_BASE_URL: `http://localhost:${MOCK_PORT}` }``.

**If your stack builds with the Cloudflare adapter** (e.g. Astro +
`@astrojs/cloudflare`): the preview runs
in workerd and does not read the process environment. At build time the adapter
copies `.dev.vars` into `dist/server/.dev.vars`, and the preview reads that copy.
`CLOUDFLARE_INCLUDE_PROCESS_ENV=true` is ignored when `.dev.vars` exists
(verified). What worked: append the variable to the built copy **between build
and preview** in the app entry's command, so dev and deploys keep the real API:

```typescript
command: `npm run build && node -e "require('fs').appendFileSync('dist/server/.dev.vars', '\\nOPENROUTER_BASE_URL=http://localhost:${MOCK_PORT}\\n')" && npm run preview -- --port ${PORT}`,
```

### 5. Prove the mock is in the path before the first real run

This includes exploration: start the mock and apply step 4 before the first
`playwright-cli` action that triggers the call, or exploring the flow spends real
money. Before any step that would call the API, check that the variable reached the
server (e.g. read `dist/server/.dev.vars`, or watch the mock's log for the
request). A wrong wiring silently calls the real API, which costs money and makes
the test non-deterministic.

Also look for what the flow _consumes_, not only the rows it writes: a free-tier
counter or credit balance the generate route decrements is test residue too.
Check it before and after a run, and prefer a test user whose runs aren't metered.

The config reads `E2E_OPENROUTER_MOCK_PORT` and hands the port to the mock as
`OPENROUTER_MOCK_PORT`: one number, two names. With the Cloudflare prep hook, the
built `dist/server/.dev.vars` keeps pointing at the mock after the run, so a
manual `npm run preview` without a rebuild sends calls to a dead port. Rebuild
before previewing by hand.

## Where this sits in the loop

- **PLAN:** list the mocked boundary under "Mocked boundaries" and keep
  everything else real.
- **GENERATE:** the spec asserts the app's behaviour on the mocked response (the
  cards it saved, the error it shows), never the mock itself.
- **VERIFY:** the deliberate break goes into the app's code, not the mock. A test
  that only turns red when the mock changes protects the mock, not the risk.
