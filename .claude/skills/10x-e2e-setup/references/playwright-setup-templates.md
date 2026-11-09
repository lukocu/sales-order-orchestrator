# Playwright setup templates

Starting points for the files `/10x-e2e-setup` creates. Replace every
`<placeholder>` with a value you **detected** in the project; never keep a
number or path from this file just because it is here.

## `playwright.config.ts` (new file)

```typescript
import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

// Local secrets (E2E_USERNAME, E2E_PASSWORD, app env) come from the gitignored
// env file. In CI the file is absent and the variables come from the job.
if (existsSync('<env file, e.g. .env>')) process.loadEnvFile('<env file>');

// <port> was detected from <source, e.g. astro.config.mjs server.port / framework default>.
// E2E_PORT overrides it when that port is taken on this machine.
const PORT = Number(process.env.E2E_PORT ?? <port>);
const baseURL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' },
      dependencies: ['setup'],
    },
  ],
  webServer: {
    // Production-like build + preview, on the port above.
    command: `<build command> && <preview command> --port ${PORT}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
```

Notes:

- **Env loading.** `process.loadEnvFile` is built into Node 20.12+ / 21.7+ and
  needs no dependency. On an older Node, add `dotenv` as a dev dependency and use
  `import 'dotenv/config'` instead. Do not load an env file that holds production
  values — the E2E run must point at a local backend.
- **Preview command and the port flag.** Pass the port the way the preview
  script accepts it: `npm run preview -- --port ${PORT}` (npm needs the `--`),
  `pnpm preview --port ${PORT}`, `yarn preview --port ${PORT}`,
  `bun run preview --port ${PORT}`; for Next.js `next start -p ${PORT}`. When the
  project has no preview/start script, use the dev command and say so in
  `test-stack.md`.
- **Preview env.** Some adapters serve the preview from a different env file than
  dev (for example a Cloudflare Workers build reads `.dev.vars`). If the project's
  CI workflow or README prepares such a file, the learner needs the same file
  locally; point that out rather than creating secrets yourself.
- **No auth in the app.** Drop the `setup` project, the `storageState` line and
  `dependencies`, and record `auth: none` in `test-stack.md`.

### Stack notes

- **If your stack is Astro 7 or newer:** `astro preview` detects an AI agent in
  its environment and moves itself into a background daemon. The npm process
  exits, Playwright reports `Process from config.webServer exited early`, and the
  orphaned daemon keeps the port, so later runs silently reuse whatever build
  it serves. Keep it in the foreground with an `env` key on the app entry:

  ```typescript
  webServer: {
    // ...command, url, reuseExistingServer, timeout as above
    env: { ASTRO_PREVIEW_BACKGROUND: '1' },
  },
  ```

  The variable is undocumented (verified on Astro 7; Astro 6 stays in the
  foreground without it). Use the same variable when you start the preview by
  hand for exploration. If a daemon was already left behind, stop it with
  `npx astro preview stop` and confirm the port is free.

### Who owns what in the config

`/10x-e2e-setup` owns the **app entry**: the `webServer` entry whose `url` is the
base URL, together with the fields `test-stack.md` records (base URL, port,
build + preview command, `reuseExistingServer`, the `setup` project,
`storageState`). `/10x-e2e` may later:

- turn `webServer` into an array and add entries for local mock servers (an
  external API the app calls server-side);
- add an `env` key to the app entry, or one step between build and preview in
  its command, to point that build at the mock.

A re-run of the setup compares and records only its own fields in the app entry
(`url`, port, `reuseExistingServer`, and a command that still runs the build and
then the preview on `PORT`) and leaves extra entries and those additions alone.
A step between build and preview, or an extra `env` variable, is not a
difference, so `test-stack.md` keeps the plain build + preview command.

### Extending an existing config

Add only the missing pieces and leave every existing key as it is:

| Missing                        | Add                                                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `webServer`                    | the block above                                                                                                          |
| `use.baseURL`                  | `baseURL` from the `PORT` constant                                                                                       |
| `setup` project                | `{ name: 'setup', testMatch: /.*\.setup\.ts/ }` + `dependencies: ['setup']` and `storageState` on the browser project(s) |
| `use.trace` / `use.screenshot` | `'on-first-retry'` / `'only-on-failure'`                                                                                 |

If an existing key has a different value (another port, another auth file,
`trace: 'off'`), ask before changing it and show the old and new value.

## `tests/e2e/auth.setup.ts`

Explore the sign-in page first (`playwright-cli open <baseURL><sign-in path>`,
then `playwright-cli snapshot`) and use the accessible names it shows. The names
below are from a typical email + password form.

```typescript
import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/user.json';

setup('sign in once and save the session', async ({ page }) => {
  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  if (!username || !password) {
    throw new Error('Set E2E_USERNAME and E2E_PASSWORD (see context/foundation/test-stack.md, ## E2E)');
  }

  await page.goto('<sign-in path, e.g. /auth/signin>');
  // A form rendered by a client-side framework (a React island, an SPA) drops input
  // typed before it hydrates, and its validation then blocks the submit. Retry
  // fill + submit until the submit leaves the sign-in page. Clear before filling:
  // re-filling the same value fires no change event in a controlled input.
  await expect(async () => {
    await page.getByLabel('<email field label>').fill('');
    await page.getByLabel('<email field label>').fill(username);
    await page.getByLabel('<password field label>', { exact: true }).fill('');
    await page.getByLabel('<password field label>', { exact: true }).fill(password);
    await page.getByRole('button', { name: '<submit button name>' }).click();
    // Wait for a state only a signed-in user reaches.
    await page.waitForURL((url) => !url.pathname.startsWith('<sign-in path>'), { timeout: 5_000 });
  }).toPass();
  await expect(<a locator only a signed-in user sees>).toBeVisible();

  await page.context().storageState({ path: authFile });
});
```

The retry is safe here because signing in twice changes nothing. For an action
that must not run twice (it creates data), wait for the page to be interactive
before the first input instead. **If your stack is Astro:** every island has
hydrated when `page.waitForFunction(() => !document.querySelector('astro-island[ssr]'))`
resolves (verified on Astro 6 with React islands). It is a DOM query, so keep it
in one helper next to the seed rather than in every spec.

Prove the file on a **cold server**: stop any server you started, confirm the
port is free, then run the seed. A warm, already-hydrated page hides the race.

## Test user (local only)

The auth setup signs in as a dedicated test user with credentials from
`E2E_USERNAME` and `E2E_PASSWORD`:

- Put both in the gitignored env file (never in the config, a spec, or a tracked
  file). If the project has `.env.example`, add the two **names** there with
  empty values so the next person knows they exist.
- Create the user in the **local** stack only. First check that the app's backend
  URL in the env file points at `localhost` / `127.0.0.1`; if it points anywhere
  else, stop and ask — never create test users in a shared or production backend.
- Supabase (local, `npx supabase start`): sign up through the app's own sign-up
  page, or open the local Studio (URL from `npx supabase status`) →
  Authentication → Add user, with auto-confirm on. Local `supabase/config.toml`
  usually has `enable_confirmations = false`, so a sign-up is usable at once.
- Other auth: use the project's documented way to create a local user (a seed
  script, an admin CLI, a sign-up page). If there is none, ask the user.

## `.gitignore` lines

Append only the lines that are missing:

```
# Playwright
playwright/.auth/
test-results/
playwright-report/
blob-report/
playwright/.cache/
.playwright-cli/
```

`.playwright-cli/` holds `playwright-cli` snapshots and console logs, which can
contain credentials. The first `playwright-cli` call (in step 3) creates it, so
ignore it here rather than waiting for step 6.

Also confirm that the env file holding `E2E_PASSWORD` is already ignored.
