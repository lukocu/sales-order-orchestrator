# Five Agent E2E Anti-Patterns

Review every agent-generated E2E test against this checklist. Each anti-pattern
has the same root cause: the agent optimizes for "test passes now," not "test is
stable tomorrow." That is a fundamental trait of LLM code generation, not a flaw
of a specific tool.

## 1. Naive assertion

Syntactically valid, semantically empty. The test creates a deck, adds a card,
reloads — and then asserts that the page title contains "Dashboard." It passes,
but it never checks that the card survived the reload. A false sense of safety.

**Control question:** would this assertion fail if the `test-plan.md` risk
materialized? If not, it's a naive assertion.

**Fix:** assert the actual business outcome (after reload, the deck heading and
card content are still visible).

## 2. Brittle selector

`page.locator('div.card-container > div:nth-child(3) > button')` instead of
`page.getByRole('button', { name: 'Delete' })`. The first breaks on any layout
change even when the user flow is unchanged.

**Fix:** `getByRole` / `getByLabel` / `getByText` — the same strategy the seed
test uses. The agent sees roles and names in accessibility snapshots, not CSS
classes.

## 3. Shared state

Test "edit card" assumes test "add card" already ran. Playwright runs tests in
parallel, in random order → flaky. Passes once, then fails randomly.

**Fix:** each test does its own setup, action, assertion, and cleanup in one
self-contained block.

## 4. Hardcoded wait

`page.waitForTimeout()` instead of waiting for state. The agent doesn't know
how long your backend takes, so it inserts `await page.waitForTimeout(3000)`. Passes on your laptop, flakes in CI where the
server responds slower — a false failure unrelated to the risk.

**Fix:** `await page.waitForResponse('**/api/decks')` or
`await expect(element).toBeVisible()`. Web-first assertions auto-retry until the
condition is met.

## 5. No cleanup

The agent creates test data (deck, cards) but never tears it down. First run
works; second run hits a `unique constraint violation` because the record
already exists.

**Fix:** unique identifiers (e.g. timestamp suffix) plus cleanup per test /
`afterEach`. Or teardown-before-setup: each test first deletes data it may have
created in a previous run, guaranteeing a clean start even after a crash.

**The quieter variant: cleanup that fails silently.** An `afterEach` exists, so
the review ticks the box, but it never removes anything. Unique identifiers
hide it: the next run doesn't collide, the data just piles up (and eats
quotas, slows lists, leaks into other tests' searches). Two ways it happens:

- **The cleanup ignores its own result**: `if (!res.ok()) return;`, an
  unchecked `page.request.delete(...)`, a `try { … } catch {}`. Every cleanup
  call asserts it worked: `expect(res).toBeOK()` on the `APIResponse` from
  `page.request` / `request` (or `toHaveURL`/`toBeHidden` when cleanup goes
  through the UI). `toBeOK()` does not accept the page `Response` that
  `page.waitForResponse()` returns — use `expect(res.ok()).toBe(true)` there;
  the wrong matcher throws, and inside `toPass()` a throw can let `afterEach`
  start while the test body is still running. A cleanup that can't do its job must turn
  the run red.
  Reading ids from a `waitForResponse()` response also breaks when the response
  makes the page navigate (a client-side redirect to the new record): the body
  is gone by the time `.json()` runs. Capture it with a pass-through
  `page.route()` instead (below).
- **The API call isn't a browser.** `page.request` / `request` sends no
  `Origin` header and no CSRF token. Frameworks that guard state-changing
  requests answer `403` to it — often only to some calls, which is why setup
  works and cleanup doesn't. Astro (`security.checkOrigin`, on by default for
  on-demand rendering) lets a JSON `POST` through but rejects a body-less
  `DELETE` or a form post whose `Origin` isn't the app's own ("Cross-site
  DELETE form submissions are forbidden"). SvelteKit (`csrf.checkOrigin`) and
  Rails / Django / Laravel CSRF behave alike. Send what the browser sends
  (`headers: { Origin: new URL(baseURL).origin }`, or the CSRF token the app
  issues) — never disable the protection for tests.
- **Some data can only be removed through a flow** (no DELETE route — e.g.
  drafts that disappear only when a session is saved or discarded). Capture
  the ids the cleanup needs _before_ a client-side redirect hides them (a
  pass-through `page.route()` + `route.fetch()` on the creating call — not
  `waitForResponse()`, whose body is lost when the page navigates), and let the cleanup drive that flow through the
  API with asserted calls. A cleanup that skips when an id is missing is the
  silent variant again: assert the id is set.

## Re-prompt discipline

Same discipline as for unit tests, lifted to E2E: **never say
"fix this test."** Name the specific anti-pattern, explain why it doesn't protect
the risk (or why it produces false failures), and give the target pattern. Three
elements per re-prompt: _what's wrong_, _why it doesn't protect the risk_, _what
replaces it_.

### Target-pattern re-prompt examples

Naive assertion:

```text
The final assertion checks the page title instead of verifying that
flashcard data survived the reload. This test will pass even when
Risk #1 materializes (data loss after refresh) — the title stays
"Dashboard" regardless.

Replace it with assertions on the actual business outcome:
deck heading and card content must be visible after page.reload().
The test must fail if the data is lost.
```

Brittle selector:

```text
This test uses CSS selectors (page.locator('.btn-primary'),
page.locator('div.card-container > div:nth-child(3) > button')).
These break on any layout refactor without the risk actually
changing — producing false failures that erode trust in the suite.

Replace all locators with getByRole, getByLabel, or getByText —
the same locator strategy used in seed.spec.ts. The agent sees
roles and names in accessibility snapshots, not CSS classes.
```

Hardcoded wait:

```text
This test uses waitForTimeout(3000) after saving. It passes locally
where the backend responds in 200ms, but will flake in CI where
response times vary — a false failure unrelated to the risk.

Replace with waitForResponse('**/api/cards') or
expect(locator).toBeVisible(). Playwright's web-first assertions
auto-retry until the condition is met.
```

No cleanup (silent):

```text
The afterEach deletes the test's cards through page.request, but it
returns early when the lookup fails and never checks the DELETE status.
If the app rejects the call (a 403 from the origin/CSRF check, a 401),
nothing is removed and the test still passes — the data piles up
unnoticed because every run uses a new id.

Assert every cleanup call: expect(res).toBeOK() on the lookup and on
each delete. Send the headers a browser would send (Origin: the
baseURL origin, or the app's CSRF token) instead of relaxing the check.
```
