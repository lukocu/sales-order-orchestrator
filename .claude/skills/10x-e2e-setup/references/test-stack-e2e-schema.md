# `test-stack.md` — the `## E2E` section (writer → reader contract)

`context/foundation/test-stack.md` records how this project runs its tests.
`/10x-e2e-setup` is the **only writer** of its `## E2E` section. Readers:

- `/10x-e2e` (Setup step 5) reads these fields instead of scanning the repo;
- `/10x-tdd` reads the file for runner and run commands;

## Ownership rules

- The writer owns **only** the `## E2E` section: from the `## E2E` heading up to
  the next `## ` heading or the end of the file. Everything else in the file is
  preserved byte for byte.
- File absent → create it with a one-line title and the `## E2E` section only:

  ```markdown
  # Test stack

  ## E2E

  ...
  ```

- Section absent → append it at the end of the file.
- Section present → compare field by field, ignoring `updated`. All equal →
  leave the file untouched (a re-run changes nothing). Something differs →
  rewrite the section and set `updated` to today.
- Readers treat a field that points at a missing file as stale and fall back to
  their own scan; they never edit this section.

## The section

Field labels are fixed; readers look them up by label. Keep the order.

```markdown
## E2E

<!-- Written by /10x-e2e-setup. Re-run it to change this section; other skills only read it. -->

- runner: Playwright Test, @playwright/test <installed version>
- config: <path, e.g. playwright.config.ts>
- single-spec command: <e.g. npx playwright test tests/e2e/<name>.spec.ts>
- full-suite command: <e.g. npx playwright test>
- base URL: <http://localhost:<the port the run uses>>
- port: <the port the run uses> (<E2E_PORT from the env file | detected from <source>>; detected default <n>, override with E2E_PORT)
- web server command: <the app entry's build + preview command, e.g. npm run build && npm run preview -- --port $E2E_PORT>; reuseExistingServer outside CI
- auth setup project: <setup (tests/e2e/auth.setup.ts), credentials from E2E_USERNAME / E2E_PASSWORD in <env file> — or: none>
- storageState: <playwright/.auth/user.json (gitignored) — or: none>
- seed: <path, e.g. tests/e2e/seed.spec.ts> — protects <risk id + one-line risk>
- browser CLI: <playwright-cli | npx -y @playwright/cli>, command skill at <path> — or: --help only
- updated: <YYYY-MM-DD>
```

## Required fields

| Label                 | Meaning                                                                                                                                                                                                                       |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `runner`              | Runner name and the installed `@playwright/test` version                                                                                                                                                                      |
| `config`              | Path of the Playwright config                                                                                                                                                                                                 |
| `single-spec command` | How to run one spec file                                                                                                                                                                                                      |
| `full-suite command`  | How to run everything                                                                                                                                                                                                         |
| `base URL`            | The URL tests and `playwright-cli` open                                                                                                                                                                                       |
| `port`                | The detected port, where it came from, and the `E2E_PORT` override                                                                                                                                                            |
| `web server command`  | What the app `webServer` entry (the one serving the base URL) starts: its build + preview command. Mock-server entries and mock hooks `/10x-e2e` adds are not recorded here, so they never make a re-run rewrite this section |
| `auth setup project`  | Setup project name + file + where credentials come from, or `none`                                                                                                                                                            |
| `storageState`        | Path of the saved session, or `none`                                                                                                                                                                                          |
| `seed`                | Seed spec path and the risk it protects                                                                                                                                                                                       |
| `updated`             | Date of the last change to this section                                                                                                                                                                                       |

`browser CLI` is optional; the others are required. Values are facts found in
the project, never placeholders — if a value is unknown, the setup is not
finished.
