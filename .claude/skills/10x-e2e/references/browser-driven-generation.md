# Browser-Driven Generation — Plan and Generate the Test Yourself

You explore the running app with `playwright-cli` (`open`, `snapshot`,
`click <ref>`, `fill`, `press`; snapshots are files on disk) and play **both
roles**: you _plan_ the flow from what the app actually renders, then you
_generate_ one spec from what the browser actually exposed. You don't delegate to
a packaged agent and you don't generate from assumptions — you author tests from
the **accessibility tree**, not pixels. This file captures how to do that well; it
does not replace the seed (`seed-test-pattern.md`) or the rules
(`e2e-quality-rules.md`), which still govern every test you write.

```
PLAN      →  explore the running app, map the flow for the risk, write it down
GENERATE  →  execute each step live in the browser, write one spec from the run
```

## Driving the browser with `playwright-cli`

`playwright-cli` is a shell command, so it works in any agent that can run one.
`/10x-e2e-setup` installs it and wires it into your agent; `playwright-cli --help`
lists every command. It drives an app that is already running: start the build +
preview in the background on the base URL's port first (the app `webServer`
entry's commands), and stop it before you run Playwright, so `webServer` owns the
server during VERIFY. The core loop:

```bash
playwright-cli open http://localhost:<port>/<route>   # base URL from test-stack.md
playwright-cli snapshot                                # accessibility tree with element refs
playwright-cli click e5                                # act on a ref from the snapshot
playwright-cli fill e7 "Deck 1727265600"
playwright-cli press Enter
playwright-cli snapshot                                # read the new state
playwright-cli close
```

Use a named session per project (`-s=<repo-name>` on every command, e.g. `playwright-cli -s=<repo-name> open …`): the `default` session is shared machine-wide, so another project's browser could receive your commands.

- Every command reports the page state and writes the snapshot as a YAML file under
  `.playwright-cli/`; read the file that command's output names (not the newest file
  by date, which can be stale) instead of pulling the whole tree into
  context. To keep one, save it under that directory:
  `playwright-cli snapshot --filename=.playwright-cli/<name>.yaml` (a bare
  `--filename=<name>.yaml` writes into the current directory, usually the repo
  root, where it is neither tracked nor ignored). `playwright-cli find <text>`
  searches a large snapshot.
- For pages behind login, load the auth state the setup project produced
  (`playwright-cli state-load playwright/.auth/user.json`) instead of clicking
  through the login form. `state-load` needs an open browser: `open` first (a
  session from an earlier step may be gone, e.g. after `playwright-cli install`).
  If `playwright/.auth/user.json` doesn't exist yet (no run since setup), create
  it first: `npx playwright test --project=setup`.
- Never print session secrets: `cookie-list`, `state-save` output and
  `localstorage-*` dumps carry live tokens. Read the state from the file, not
  the terminal.
- The tool surface stays out of your context, so a scenario costs far fewer tokens
  than driving the browser through a tool-per-action server.

If your tool has no shell but has a Playwright MCP server, the same steps apply
through its browser tools (navigate, snapshot, click, type, wait). If neither is
available, fall back to the prompt-template path (`e2e-prompt-template.md`) and
write the spec from your reading of the app.

Either way you produce the same artifact: a spec authored from the
**accessibility tree** the app actually rendered.

## Why the accessibility tree changes everything

You work from a snapshot of roles, names, and states with element refs — exactly
what a screen reader sees — not pixels:

```yaml
- button "Add card" [ref=e5]
- textbox "Deck name" [ref=e7]
- heading "My Deck" [level=2] [ref=e9]
```

Consequences to lean into:

- The snapshot exposes roles and names, so you **naturally** reach for `getByRole`
  / `getByLabel` / `getByText`. CSS selectors would be guesswork.
- If an element has no accessible name or role, you can't find it from the snapshot
  — which is itself a signal that a screen reader can't either. Fix the app's
  accessibility rather than reaching for a brittle selector.
- The snapshot is cheaper (fewer tokens) and more stable than a screenshot, so you
  generate faster and flake less.

**Prefer `playwright-cli snapshot` over `playwright-cli screenshot`.** Take a
screenshot only when a risk is genuinely visual (layout, overlap, animation) —
that's the vision path, not the default.

## PLAN — explore and map the flow

You plan first. Drive the plan from the risk, not the page, and keep every
scenario independent:

- **Navigate and set up the page first**, then explore from the snapshot before any
  other interaction.
- **Plan from the risk**, not the page. Feed yourself the one risk from
  `context/foundation/test-plan.md` this phase protects — a focused plan for that
  flow, not a generic crawl of every button.
- **Each scenario must be independent and runnable in any order** — its own setup,
  action, assertion, and cleanup, always assuming a fresh/blank starting state. This
  is what keeps the suite parallel-safe.
- **Model scenarios on the seed.** The seed (`seed.spec.ts`) is the example every
  generated test follows — **seed quality is test quality.**
- Cover the happy path **and** at least the edge/error case the risk implies; a
  happy-path-only plan rarely catches the regression you care about.
- Write the plan down (a short Markdown scenario list) so GENERATE has explicit
  steps and expected outcomes to execute against.

## GENERATE — execute live, write from the run

Then you generate. Turn one plan scenario into one TypeScript spec by performing
the steps live, then writing the code from what actually happened:

- **Set up the page, then execute each step for real.** Use each plan step's
  description as the intent for the corresponding browser action; observe the actual
  result rather than imagining it.
- **Write the spec from the real run, not from guesses.** The locators and waits the
  browser actually resolved are more resilient than hand-written ones — use those.
  Check a generated `.nth(n)` or `.first()` before you copy it: it usually means
  the name matched more than one element as a substring ("Akceptuj" inside
  "Zaakceptuj wszystkie"). Pass `exact: true`, or scope to the row
  (`getByRole('listitem').filter({ hasText })`), instead of a position.
- **One test per file.** The file name is the fs-friendly scenario name; the test
  lives in a `describe` matching the top-level plan/risk item; the test title matches
  the scenario name.
- **Comment each step.** Put the plan's step text as a comment before the actions
  that implement it (don't duplicate the comment when one step needs several
  actions).
- **Keep a provenance header** linking the spec back to its risk and seed, e.g.:

  ```ts
  // risk: test-plan.md #1 — flashcard data persists after reload
  // seed: tests/seed.spec.ts
  ```

A generated spec still goes through the five-anti-pattern review and the
deliberate-break verification before it counts as done — driving the browser gets
you a _plausible_ test fast; review and verification make it a _protective_ one.

## The auto-heal boundary

Playwright (and similar tools) can auto-"heal" a failing test by re-finding moved
elements. That is genuinely useful — and genuinely dangerous — depending on _why_
the test failed:

- **Selector / timing drift → heal, then review.** A moved button or a changed role
  is a maintenance fix; prefer resilient locators, regexes for dynamic data, and
  web-first waits (never `networkidle` or deprecated APIs). Route any auto-fix
  through PR review; never auto-commit it.
- **Changed business behavior → do NOT heal.** If the app's behavior changed, an
  auto-fix will happily rewrite the assertion to match the new — possibly broken —
  state, masking the very regression the test exists to catch. That is a debugging
  task, not a healing task.
- Never accept a `test.fixme()` / `test.skip()` left behind to force a green suite.
  Treat any such marker as an open bug to investigate — this skill never accepts a
  skipped test as "done."

## How this maps to the skill's loop

| Skill beat   | Browser-driven path                                                                            |
| ------------ | ---------------------------------------------------------------------------------------------- |
| **PLAN**     | You explore the flow for the risk and write a short scenario list that names `seed.spec.ts`    |
| **GENERATE** | You execute the plan live and write one spec per scenario from the real run                    |
| **REVIEW**   | You check the spec against the five anti-patterns and re-prompt by name                        |
| **VERIFY**   | You run the spec green, then deliberately break the protected behavior and confirm it goes red |

The prompt-template path (`e2e-prompt-template.md`) collapses PLAN+GENERATE into a
single filled prompt — simpler for one clear scenario, no live browser needed.
Either way the seed and rules shape the output and the contract is identical: risk,
research anchor, business scenario, real-vs-mocked boundaries, risk-tied assertion.
