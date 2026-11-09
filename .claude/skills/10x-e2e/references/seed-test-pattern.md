# Seed Test Pattern

The seed test (`seed.spec.ts`) is the primary E2E quality lever. It is not an
empty ritual: it's the example every generated test is modeled on. If the seed
uses `getByRole`, generated tests do too. If the seed has
`page.waitForTimeout(2000)`, every generated test inherits that anti-pattern.
**What you show is what you get.**

## The four patterns a good seed demonstrates

- **Role-based locators.** `getByRole('button', { name: 'Add card' })` is robust
  against CSS class changes, DOM structure changes, and component refactors —
  and it matches exactly what the agent sees in accessibility snapshots.
  Playwright: "Prefer user-facing attributes to XPath or CSS selectors." A seed
  using `page.locator('.btn-primary')` teaches the agent to reproduce brittle
  selectors.
- **Test independence.** Agents happily generate tests where test B assumes test
  A created a deck. Playwright runs in parallel, in random order. "Each test
  should be completely isolated from another test and should run independently."
  The seed must show a full cycle — setup, action, assertion, cleanup — in one
  test.
- **Wait for state, not time.** "Never wait for timeout in production. Tests that
  wait for time are inherently flaky." Use `expect(locator).toBeVisible()`,
  `page.waitForURL()`, or `page.waitForResponse()` — a concrete application
  state instead of an arbitrary duration. That includes the page being
  **interactive**: a form rendered by a client-side framework (a React island,
  an SPA) drops input typed before it hydrates. Wrap an idempotent fill + submit
  - `waitForURL(…, { timeout: 5_000 })` in `expect(async () => { … }).toPass()`,
    or wait for a hydration signal before the first input (the auth setup
    template in `/10x-e2e-setup` shows both). Inside `toPass`, clear before you
    fill (`fill('')`, then the value): re-filling the same text fires no change
    event, so a disabled submit stays disabled. When the submit is **not**
    idempotent (it creates a record), don't retry it — wait for the hydration
    signal once, then fill and submit.
- **Risk-tied assertions.** The test name should bind it unambiguously to a risk
  from `context/foundation/test-plan.md`: `test('flashcard data persists after
page reload', ...)`, not `test('test 1', ...)`.

## Exemplar

```typescript
// seed.spec.ts
import { test, expect } from "@playwright/test";

test("created deck persists after page reload", async ({ page }) => {
  const deckName = `Test Deck ${Date.now()}`;
  await page.goto("/");

  await page.getByRole("button", { name: "New deck" }).click();
  await page.getByRole("textbox", { name: "Deck name" }).fill(deckName);
  await page.getByRole("button", { name: "Create" }).click();

  await expect(page.getByRole("heading", { name: deckName })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: deckName })).toBeVisible();

  // Cleanup — asserted, so a cleanup that fails turns the run red
  await page.getByRole("button", { name: "Delete deck" }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("heading", { name: deckName })).toBeHidden();
});
```

A seed that creates no data (e.g. a signed-out redirect) has nothing to clean up;
say so in a comment. Don't "clean up" by signing the shared test user out: many
apps sign out globally, which revokes the saved session every other spec loads.

Note `Date.now()` in the deck name — a unique identifier so parallel runs and
re-runs don't collide (see anti-pattern #5, "No cleanup", in
`e2e-anti-patterns.md`).

## Where the seed lives and how it signs in

`/10x-e2e-setup` writes the seed once per project (default
`tests/e2e/seed.spec.ts`; the real path is recorded in
`context/foundation/test-stack.md`, section `## E2E`) and runs it to green
**from a cold server**: nothing listening on the port, so Playwright's
`webServer` builds and starts the app itself. A green run against a warm server
you started by hand proves little, because it hides hydration races and stale
builds. Review it like any other code — it is the pattern every later test copies.

Tests start signed in: the `setup` project signs in once through the real UI and
saves `playwright/.auth/user.json`, and the test projects load it through
`storageState`. A test never logs in through the UI itself — unless its risk
_is_ the signed-out path (an auth-gate redirect, the login flow). Such a test
opts out explicitly:

```typescript
test.use({ storageState: { cookies: [], origins: [] } });
```

The seed test and the E2E rules are the two strongest quality levers in E2E.
Without them the agent produces tests that pass today but break on the first
refactor or block the parallel-run pipeline.
