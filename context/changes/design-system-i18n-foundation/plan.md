# Design system and PL|EN i18n foundation for the app shell — Implementation Plan

## Overview

Introduce the design-system contract the frontend lacks: semantic tokens through Tailwind v4 and shadcn/ui components copied into `src/components/ui`. Add react-i18next with Polish as the default language and a PL | EN switch. Then rebuild the app shell (login, header, inbox list) on that base. This is roadmap item F-03 (M-2 `ux-driven-redesign`) and the foundation every later M-2 slice (S-11 to S-17) builds on. The inquiry view (`AnalysisPanel` and its sections) keeps running on the old CSS until S-11 and S-12 rebuild it.

## Current State Analysis

From `research.md` (commit 84d1438):

- **Values:** 8 colour tokens in `frontend/src/index.css:1-28`. Dark mode comes from `@media (prefers-color-scheme: dark)` and there is no toggle. There is no primary, input, ring, radius, spacing or type scale. 168 lines of `index.css` (908 lines) carry px/rem literals.
- **Components:** none shared. A global `button` selector (`index.css:51-64`) styles every action alike, and disabled is only `opacity: 0.6`.
- **Accessibility:** `--border` is used on fields and buttons at 1.43:1 (light) and 1.76:1 (dark), which fails WCAG 1.4.11. `index.css` has 0 `focus` rules and 0 `hover` rules.
- **App shell:** there is none. The `<h1>` is in `App.tsx:46`. The user identity and Sign out sit in `Inbox.tsx:193-201`. `HealthFooter` renders in every state, including for anonymous visitors (`App.tsx:60`).
- **i18n:** English is hardcoded across `App.tsx`, `LoginForm.tsx`, `Inbox.tsx`, `HealthFooter.tsx` and `ROLE_LABEL` (`api/auth.ts:15-18`). `index.html:2` sets `lang="en"`. The tests make 456 text-based queries.
- **Toolchain:** `typescript@7.0.2`, `vite@8.3.7`, Vitest 5 sharing `vite.config.ts`. There is no `@/` alias. CI (`.github/workflows/ci.yml:72-80`) and the `Dockerfile:6-9` run `npm ci` → lint → typecheck → test → build.

## Desired End State

- `npm run dev` shows a shell with a header (product name, a nav slot, the PL | EN switch, and user plus Sign out when logged in) around the login form or the inbox. The app opens in Polish, the choice persists across reloads, and `<html lang>` follows it.
- Every shell control is a shadcn component styled only by semantic tokens.
  - Field borders reach ≥3:1 and a token-driven focus ring is visible on every control, in both themes.
  - "Sign in" and "Fetch mail" read as primary actions; "Sign out" does not.
- The inquiry view looks as it did before. It is checked with before/after screenshots.
- `/kitchen-sink.html` (dev only) shows the shell in all 7 states, captured at desktop and 375 px.
- `AGENTS.md` tells the next agent where tokens and components live. `tech-stack.md` records the frontend stack.
- Verify with: `npm run lint && npm run typecheck && npm test && npm run build` in `frontend/`, plus the manual checks per phase.

### Key Discoveries:

- TS 7 removed `baseUrl`. shadcn's Vite guide adds it, so the alias must be `paths` only, with `./` targets (TS5090 otherwise). Source: Context7 `/microsoft/typescript/v7.0.2`.
- Vite 8 resolves tsconfig `paths` natively with `resolve.tsconfigPaths: true`, and Vitest reads the same config (`vite.config.ts:20-23`).
- Tailwind v4's default `dark:` variant already is `prefers-color-scheme`, so the current OS-driven dark mode carries over without `.dark` or `@custom-variant`.
- `App.test.tsx:276` asserts "shows the health footer in both views". That test changes with the HealthFooter decision.
- `App.test.tsx:180` and `Inbox.tsx:196` read `ROLE_LABEL`. It is the only consumer outside `api/auth.ts`.

## What We're NOT Doing

- Rebuilding the inquiry view (`AnalysisPanel`, `ChecksSection`, `OrchestrationSection`, `PolicySection`, `RecommendationSection`, `ReplyDraftSection`, `RunMetrics`). That is S-11 and S-12, which will also translate those strings.
- Moving `HealthFooter` to a system page (S-11). This change only hides it for anonymous visitors.
- Translating backend messages by code, including the `'Mailbox unavailable'` match at `Inbox.tsx:59` (S-16). Backend-sourced message text is shown as received.
- Translating customer content or model-written reasoning (PRD FR-021).
- Router and URLs: TanStack Router (S-17), sonner toasts (S-14), TanStack Query.
- A manual light/dark toggle. Dark mode stays OS-driven.
- Playwright or screenshot tests in CI. The visual gate is the kitchen sink plus screenshots.
- A hardcoded-value lint check. The repo's linter (oxlint) has no CSS or class-literal rule, so a custom check would be a new dependency. The guardrail is the `AGENTS.md` rule plus the scan command in it.
- A whole-library shadcn install. Only Button, Input, Label, Card and Badge are added.

## Implementation Approach

Follow the /10x-ui order: environment and library → token values → one view → states.

i18n lands before the view so the view is written once against `t()`. Old and new CSS coexist through cascade layers: the old stylesheet moves into a layer below Tailwind's utilities so new classes always win. A scoped compatibility block restores the browser defaults the inquiry view relies on once Preflight is on. S-11 and S-12 later delete that block rather than re-tune it.

## Critical Implementation Details

- **Cascade order.** Unlayered CSS beats every `@layer`. If the old `index.css` stays unlayered, its `button {…}` (`index.css:51`) overrides shadcn Button classes. The old rules must sit in a named layer declared before `utilities`, for example `@layer theme, base, legacy, components, utilities;`. Their source order must not change, because the old file depends on it.
- **Preflight and the inquiry view.** The inquiry view relies on browser defaults for headings, lists, `dl` and `pre`: about 30 elements across 7 components, and only `h1` is styled (`index.css:46`). The compatibility block is scoped to that view's root container, not global, so the shell gets a clean Preflight base. Take the "before" screenshots of the inquiry view **before** Tailwind is imported.
- **Token publishing.** Raw colour values live only in `:root` and in the `prefers-color-scheme: dark` block. `@theme inline` contains only `var(--…)` references. A raw colour inside `@theme inline` freezes the light value and breaks dark mode.

## Phase 1: Toolchain and coexistence

### Overview

Install the libraries, wire the alias and Tailwind, and fence the old CSS into a layer, so the app builds and looks unchanged.

### Changes Required:

#### 1. Dependencies

**File**: `frontend/package.json`, `frontend/package-lock.json`

**Intent**: Add the runtime and build dependencies for the design system and i18n, so CI and Docker pick them up through `npm ci`.

**Contract**:
- Runtime: `tailwindcss`, `@tailwindcss/vite`, `radix-ui`, `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `lucide-react`, `i18next`, `react-i18next`.
- Versions: the current majors verified in research (Tailwind 4.3, i18next 27, react-i18next 18).
- No new npm scripts.

#### 2. Path alias

**File**: `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/vite.config.ts`

**Intent**: Make `@/…` resolve to `src/…` for TypeScript, Vite, Vitest and the shadcn CLI, without `baseUrl`.

**Contract**:
- `compilerOptions.paths: { "@/*": ["./src/*"] }` in both tsconfig files. No `baseUrl`.
- `resolve.tsconfigPaths: true` in `vite.config.ts`.
- `@tailwindcss/vite` added to `plugins` next to `react()`.

#### 3. shadcn configuration and utility

**File**: `frontend/components.json`, `frontend/src/lib/utils.ts`

**Intent**: Point the shadcn CLI at this repo's layout so later `shadcn add` calls land in `src/components/ui`.

**Contract**:
- `components.json`: style "new-york", `tsx: true`, `tailwind.css: "src/index.css"`, `tailwind.cssVariables: true`, `baseColor: "neutral"` (overridden by our tokens in Phase 2), `iconLibrary: "lucide"`.
- Aliases: `components → @/components`, `ui → @/components/ui`, `lib → @/lib`, `utils → @/lib/utils`.
- `utils.ts` exports `cn(...inputs)` (`clsx` + `tailwind-merge`).
- If `shadcn init` tries to rewrite `index.css` or add `baseUrl`, revert those parts by hand.

#### 4. Layered stylesheet

**File**: `frontend/src/index.css` (the old content moves to `frontend/src/styles/legacy.css`)

**Intent**: Import Tailwind and keep every old rule working underneath it, with no visual change.

**Contract**:
- `index.css` becomes the entry point: the layer order declaration, then `@import "tailwindcss"`, then `@import "tw-animate-css"`, then the old file imported into the `legacy` layer.
- The old content moves unchanged into `styles/legacy.css`, in its existing order.
- See Critical Implementation Details for the layer order.

#### 5. Inquiry-view compatibility block

**File**: `frontend/src/styles/legacy.css` (appended inside the legacy layer); `frontend/src/components/AnalysisPanel.tsx` only if its root lacks a stable class

**Intent**: Restore the browser defaults Preflight removes, only inside the inquiry view, so it renders as before.

**Contract**:
- A block headed `/* Preflight compatibility for the inquiry view — delete in S-11/S-12 */`, scoped under the inquiry detail root (`.inbox__detail`, `Inbox.tsx:287`).
- It restores: heading sizes and margins, list style and padding for `ul`/`ol`, `dl`/`dd` margins, `pre` margin, and the button border style.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- No `baseUrl` in either tsconfig: `grep -c baseUrl frontend/tsconfig*.json` reports 0 per file
- An `@/` import resolves in tests: `src/lib/utils.ts` is imported via `@/lib/utils` from at least one test

#### Manual Verification:

- Login, inbox and an analysed inquiry (ACME discount) match the "before" screenshots taken at desktop width before step 4. The analysed inquiry is checked in light and dark.

**Implementation Note**: After automated verification passes, pause for the human to confirm the screenshots before Phase 2. Progress checkboxes live in `## Progress`.

---

## Phase 2: Token values and components

### Overview

Define the semantic tokens from the existing palette plus the agreed blue primary. Then add the five shadcn components the shell needs.

### Changes Required:

#### 1. Token values

**File**: `frontend/src/index.css` (outside the legacy layer); `context/changes/design-system-i18n-foundation/tokens.md` (new)

**Intent**: One source of role-named values in light and dark, published to Tailwind, with their origin recorded in the repo.

**Contract**:
- Values are defined in `:root` and in `@media (prefers-color-scheme: dark) { :root {…} }`.
- **Mapped from the current palette (light / dark):**

  | Token | Light | Dark | Source token |
  |---|---|---|---|
  | `--background` | `#f6f8fa` | `#0d1117` | `--bg` |
  | `--foreground` | `#1f2328` | `#e6edf3` | `--text` |
  | `--card` | `#fff` | `#151b23` | `--card` |
  | `--card-foreground` | same as `--foreground` | same as `--foreground` | — |
  | `--muted-foreground` | `#59636e` | `#9198a1` | `--muted` |
  | `--border` | `#d1d9e0` | `#3d444d` | `--border` (decorative only) |
  | `--destructive` | `#cf222e` | `#f85149` | `--error` |
  | `--success` | `#1a7f37` | `#3fb950` | `--ok` |
  | `--warning` | `#9a6700` | `#d29922` | `--warn` |

- **New values:**

  | Token | Light | Dark |
  |---|---|---|
  | `--primary` | `#0969da` | `#4493f8` |
  | `--primary-foreground` | `#fff` | `#0d1117` |
  | `--input` | `#818b98` | `#6e7681` |
  | `--ring` | `#0969da` | `#4493f8` |
  | `--radius` | `0.375rem` (today's `6px`) | same |

  `--muted`, `--secondary` and `--accent` are derived from the existing surfaces.
- `@theme inline` publishes `--color-*` for each value via `var()`, plus `--radius-sm/md/lg`.
- The old variable names (`--text`, `--bg`, `--ok`, …) stay defined as aliases to the new ones. `legacy.css` keeps working without edits.
- `tokens.md` lists every value and its contrast pair, and its source: "mapped from `index.css:1-28` @ 84d1438; primary per plan decision 2026-11-16".

#### 2. Base focus and border defaults

**File**: `frontend/src/index.css` (`@layer base`)

**Intent**: Give every focusable element a visible token focus ring and default borders to `--border`, as shadcn expects.

**Contract**:
- `*` gets `border-color: var(--border)`.
- `:focus-visible` gets an outline in `--ring`, 2px, with offset.
- `body` gets background and foreground from the tokens.

#### 3. shadcn components

**File**: `frontend/src/components/ui/{button,input,label,card,badge}.tsx`

**Intent**: Bring in the five primitives through the stack's own path so they are readable source in the repo.

**Contract**:
- Added with `npx shadcn@latest add button input label card badge`.
- Badge gains `success` and `warning` variants (outline and filled), mapping to the current outcome and awaiting-supervisor styles (`legacy.css`, formerly `index.css:194-230`).
- Button keeps the shadcn variants `default`, `outline`, `ghost`, `destructive` and `link`.
- Disabled is `disabled:opacity-50 disabled:pointer-events-none` from shadcn, and its contrast is checked in Phase 5.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Raw colours appear only in the token blocks: `grep -nE '#[0-9a-fA-F]{3,8}\b' frontend/src/index.css` shows matches only inside the `:root` and dark `:root` blocks
- The five component files exist under `frontend/src/components/ui/`

#### Manual Verification:

- With the OS in dark mode, the token values change (checked in devtools on `:root`). The inquiry view still matches its screenshots.

**Implementation Note**: Pause for manual confirmation before Phase 3.

---

## Phase 3: i18n foundation

### Overview

Set up react-i18next with bundled Polish and English resources, Polish as the default, and a persisted switch that also updates `<html lang>`. Tests stay in English.

### Changes Required:

#### 1. i18n instance and resources

**File**: `frontend/src/i18n/index.ts`, `frontend/src/i18n/locales/{pl,en}.json`

**Intent**: One i18next instance, initialised before render, with every shell string as a key in both languages.

**Contract**:
- Bundled resources, no HTTP backend. One namespace (`translation`). Keys are grouped by area: `app.*`, `login.*`, `inbox.*`, `role.*`, `outcome.*`, `health.*`, `language.*`.
- English values equal today's strings exactly, so the existing queries keep matching.
- Language comes from `localStorage` key `lang` if it holds `pl` or `en`, otherwise `pl`. `fallbackLng: 'en'`.
- On `languageChanged`: write `localStorage` (inside try/catch) and set `document.documentElement.lang`.
- `escapeValue: false`.
- No language-detector dependency: the order is localStorage → `pl`, which a few lines cover.

#### 2. Bootstrapping and the HTML default

**File**: `frontend/src/main.tsx`, `frontend/index.html`

**Intent**: Initialise i18n before the first render, and make the static document language match the default.

**Contract**:
- `main.tsx` imports `./i18n` before `App`.
- `index.html` sets `lang="pl"`.

#### 3. Language switch

**File**: `frontend/src/components/LanguageSwitch.tsx`

**Intent**: A visible PL | EN control (FR-021) that changes the language in place.

**Contract**:
- A group labelled by `t('language.label')` holding two buttons, `PL` and `EN`. Each has an accessible name for its language ("Polski", "English") and `lang` set on its label.
- The active option has `aria-pressed="true"`.
- Built from the shadcn `Button` with `ghost`/`outline` variants. Fits at 375 px.

#### 4. Test setup and new tests

**File**: `frontend/src/test/setup.ts`, `frontend/src/i18n/i18n.test.ts`, `frontend/src/components/LanguageSwitch.test.tsx`

**Intent**: Pin tests to English so the 456 queries keep passing. Catch missing translations and prove the switch works.

**Contract**:
- `setup.ts` imports the i18n instance and calls `changeLanguage('en')` before each test.
- `i18n.test.ts` asserts that the flattened key sets of `pl.json` and `en.json` are equal and that no value is empty.
- `LanguageSwitch.test.tsx`:
  - It renders the switch with a translated label, clicks `PL`, and asserts the Polish label text, `document.documentElement.lang === 'pl'` and the `localStorage` value.
  - A second case: an invalid stored value falls back to `pl`.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- The key-parity test passes: `cd frontend && npx vitest run src/i18n`
- The language-switch test passes: `cd frontend && npx vitest run src/components/LanguageSwitch.test.tsx`

#### Manual Verification:

- None in this phase. The switch is not mounted in the app until Phase 4.

**Implementation Note**: Continue to Phase 4 once automated checks pass.

---

## Phase 4: App shell (the one view)

### Overview

Wrap login and inbox in an `AppShell` and rebuild the login form, the header and the inbox list on the components, tokens and `t()`. Hide HealthFooter for anonymous visitors. Remove the shell's legacy selectors.

### Changes Required:

#### 1. AppShell

**File**: `frontend/src/components/AppShell.tsx`, `frontend/src/App.tsx`

**Intent**: One frame for every app state, holding the header, a nav slot for S-11 and S-15, the language switch, and the user menu when logged in.

**Contract**:
- Props: `user: User | null`, `onSignOut?: () => void`, `signingOut?: boolean`, `nav?: ReactNode`, `children`.
- The header holds the product name as the page `<h1>`, the `nav` slot, `LanguageSwitch`, and, when `user` is set, the display name, the role label from `t('role.<role>')`, and a Sign out Button (`outline`).
- `App.tsx` renders `AppShell` around every state (loading, error, anonymous, authenticated).
- `HealthFooter` renders only when `state.kind === 'authenticated'`.
- The width switch at `App.tsx:45` moves into AppShell (narrow content for login, wide for the inbox).
- Sign-out ownership moves from `Inbox` to `App`, because `App` owns the session state. The logic and messages are unchanged.
- The sign-out error shows below the header with `role="alert"`.

#### 2. Login form

**File**: `frontend/src/components/LoginForm.tsx`

**Intent**: Rebuild the form on Card, Label, Input and Button with translated text. Behaviour is unchanged.

**Contract**:
- The same fields, `name`/`autoComplete`, submit flow and `role="alert"` error.
- Sign in is the `default` (primary) Button.
- Inputs use the `--input` border and the ring focus.
- The error text uses `text-destructive` and stays next to the button.

#### 3. Inbox list

**File**: `frontend/src/components/Inbox.tsx`

**Intent**: Move the list column onto Card, Button and Badge with translated text, keeping behaviour and the detail panel unchanged.

**Contract**:
- Fetch mail is a `default` Button. Retry is `outline`.
- The "Awaiting supervisor only" filter is a toggle Button whose `aria-pressed` state has a distinct look.
- The source, outcome and awaiting badges use Badge variants. `OUTCOME_LABEL` becomes `t('outcome.<kind>')`.
- Empty, loading and error states keep their text and roles.
- The inquiry rows stay list items styled with tokens, with hover and focus-visible states.
- The header block at `Inbox.tsx:193-206` is removed (now in AppShell). `Inbox` props drop `onSignedOut`.
- The detail panel (`Inbox.tsx:287+`) and `AnalysisPanel` are untouched.

#### 4. Remove `ROLE_LABEL` and dead legacy selectors

**File**: `frontend/src/api/auth.ts`, `frontend/src/styles/legacy.css`, `frontend/src/components/HealthFooter.tsx`

**Intent**: Take UI text out of the API layer and delete the old selectors the shell no longer uses.

**Contract**:
- `ROLE_LABEL` is deleted from `auth.ts` (its consumers move to `t('role.*')`).
- HealthFooter strings move to `health.*` keys. Its look stays.
- `legacy.css` loses `.page`, `.page--wide`, the global `h1`, `.login*`, `.inbox__header`, `.inbox__user`, `.inbox__role`, `.inbox__list*`, `.inbox__filter`, `.inquiry*`, `.badge*`, the global `button` and `button:disabled`.
- Before removing a selector, grep for its remaining users. Any selector still used by the inquiry view stays.

#### 5. Tests

**File**: `frontend/src/App.test.tsx`, `frontend/src/components/LoginForm.test.tsx`, `frontend/src/components/Inbox.test.tsx`, `frontend/src/components/HealthFooter.test.tsx`

**Intent**: Keep the existing English assertions and adapt only what the shell move changes.

**Contract**:
- `App.test.tsx:276` "shows the health footer in both views" becomes two assertions: present when logged in, absent on the login screen.
- Sign-out tests move from `Inbox.test.tsx` to `App.test.tsx` (or an `AppShell.test.tsx`).
- One App-level smoke test switches to PL and asserts the Polish Sign in label and `lang="pl"`.
- No other test text changes. If a query fails, the English resource is wrong, not the test.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- The shell views have no hardcoded colour or arbitrary value. This scan over `frontend/src/App.tsx`, `frontend/src/components/{AppShell,LoginForm,Inbox,LanguageSwitch}.tsx` returns no matches:
  `grep -nE '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(|-\[[0-9.]+(px|rem)\]|\b(bg|text|border|ring|outline|from|via|to|fill|stroke|shadow|divide)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b'`
- `ROLE_LABEL` is gone: `grep -rn ROLE_LABEL frontend/src` returns no matches
- The test asserting HealthFooter is absent for anonymous visitors passes

#### Manual Verification:

- With `npm run dev` against the local backend, the app opens in Polish. Switching to EN and reloading keeps English, and `<html lang>` follows.
- Sign in, Fetch mail, the filter, selecting an inquiry and Sign out all work.
- Supervisor and salesperson roles show the right translated label.
- At 375 px, the header (name, switch, user, Sign out) fits without horizontal scroll.
- The inquiry view still matches its Phase 1 screenshots.

**Implementation Note**: Pause for manual confirmation before Phase 5.

---

## Phase 5: States, visual gate and guardrails

### Overview

Show every shell state at once on a dev-only page, capture it, and leave the rule and stack record that keep the next agent on the contract.

### Changes Required:

#### 1. Kitchen sink

**File**: `frontend/kitchen-sink.html`, `frontend/src/kitchen-sink.tsx`

**Intent**: A dev-only page rendering the shell in the 7-state matrix with static data, in both languages.

**Contract**:
- Served by `npm run dev` at `/kitchen-sink.html`. It is not in `build.rollupOptions.input`, so `npm run build` and the Docker image do not include it.
- It renders, side by side:

  | State | What is shown |
  |---|---|
  | default | login, header logged out and in, inbox list with all badge variants |
  | hover | rows and buttons via a `data-state` / forced-hover note |
  | focus-visible | each control with focus (via `autoFocus` or a static `focus-visible` class from the ring token) |
  | disabled | Sign in submitting, Fetch mail fetching, Sign out signing out |
  | error | login error, list error, sign-out error |
  | empty | no inquiries; none awaiting a supervisor |
  | loading | session check, list loading |

- A PL | EN switch at the top re-renders everything.
- Any state without a meaningful rendering is marked N/A with a reason on the page.

#### 2. Screenshots

**File**: `context/changes/design-system-i18n-foundation/screenshots/`

**Intent**: Evidence of the gate for review.

**Contract**:
- The kitchen sink at desktop (1440 wide) and 375 px, in light and dark.
- Login and inbox in the running app at desktop and 375 px.
- The inquiry view after the change, next to the Phase 1 "before" captures.

#### 3. Agent rule

**File**: `AGENTS.md` (new, repo root)

**Intent**: The repo has no agent rules file, so a short one tells the next agent where the contract lives.

**Contract**:
- A "Frontend UI" section:
  - Tokens live in `frontend/src/index.css` (`:root` / dark block → `@theme inline`), with values in `context/changes/design-system-i18n-foundation/tokens.md` until archived.
  - Components live in `frontend/src/components/ui`. Check it before creating one, and add missing ones with `npx shadcn@latest add <name>`.
  - No literal colours or arbitrary values in views. Use tokens.
  - The scan command from Phase 4.
  - The kitchen sink is at `frontend/kitchen-sink.html`.
  - UI text goes through `t()` with keys in both `pl.json` and `en.json`. Tests run in English.
  - `styles/legacy.css` is shrinking and gets no new rules.
- Written outside any `<!-- BEGIN @przeprogramowani/10x-cli -->` block.

#### 4. Stack record

**File**: `context/foundation/tech-stack.md`; `context/foundation/roadmap.md` (Open Roadmap Question 4)

**Intent**: Answer Open Roadmap Question 4 by recording the frontend stack where the next planner looks.

**Contract**:
- A `## Frontend` section after "Why this stack":
  - React 19 + Vite 8 + TS 7.
  - Tailwind v4 via `@tailwindcss/vite`.
  - shadcn/ui primitives in `src/components/ui` (Radix via `radix-ui`).
  - lucide-react.
  - react-i18next with bundled PL/EN, Polish by default, tests pinned to EN.
  - Constraints: no `baseUrl`, alias via `paths` plus `resolve.tsconfigPaths`, OS-driven dark mode, legacy CSS in a layer until S-12.
  - Parked: TanStack Router (S-17), sonner (S-14), TanStack Query.
- The frontmatter stays unchanged.
- In `roadmap.md`, Open Roadmap Question 4 is marked resolved with a pointer to that section.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- The kitchen sink is excluded from the build: after `npm run build`, `frontend/dist/kitchen-sink.html` does not exist
- `AGENTS.md` exists with a "Frontend UI" section, and `tech-stack.md` has a `## Frontend` section

#### Manual Verification:

- The kitchen sink shows every cell of the 7-state matrix, or N/A with a reason.
  - Focus rings are visible in light and dark.
  - Disabled controls stay readable.
  - Error text sits next to its field or action.
- Screenshots are saved at desktop and 375 px in both themes.
- Field borders and focus rings measure ≥3:1 against their background in both themes (spot-check with devtools).

**Implementation Note**: Then run `/10x-impl-review`. UI findings are not cosmetic skips by default.

---

## Testing Strategy

### Unit Tests:

- Key parity between `pl.json` and `en.json`, with no empty values.
- `LanguageSwitch`: language change, `lang` attribute, persistence, invalid stored value.
- HealthFooter visibility by auth state.

### Integration Tests:

- The existing App, Inbox, LoginForm and HealthFooter tests run in English unchanged in text. Only the structural moves are adjusted (header to AppShell, footer condition).
- One App-level Polish smoke test.

### Manual Testing Steps:

1. Run `npm run dev` against the backend on `:8010` and open the app. It is Polish by default. Switch to EN and reload; it stays EN.
2. Sign in as a salesperson, fetch mail, filter, open the analysed ACME inquiry, and sign out.
3. Repeat as the supervisor.
4. Tab through the login and header and confirm a visible ring on each control in light and dark.
5. Open `/kitchen-sink.html` at 1440 and 375 px.

## Performance Considerations

Tailwind v4 generates only the classes it uses. The added runtime is react-i18next and i18next plus the Radix primitives for five components, which is acceptable for an internal tool. The bundle size before and after is noted in the Phase 5 review and is not a gate.

## Migration Notes

There is no data migration. Rollback is a revert of the change's commits. The legacy layer keeps the inquiry view independent, so S-11 and S-12 can delete `legacy.css` rules incrementally.

## References

- Research: `context/changes/design-system-i18n-foundation/research.md`
- UX + WCAG audit: `context/audits/ux/2026-11-16-prism-analysis-flow.md`
- PRD v2: `context/foundation/prd.md` (FR-015, FR-021, NFR WCAG 2.2 AA)
- Roadmap: `context/foundation/roadmap.md` (F-03, Open Roadmap Question 4)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Toolchain and coexistence

#### Automated

- [x] 1.1 Lint, typecheck, tests and build pass — 62e06b6
- [x] 1.2 No baseUrl in either tsconfig — 62e06b6
- [x] 1.3 An @/ import resolves in tests — 62e06b6

#### Manual

- [x] 1.4 Login, inbox and an analysed inquiry match the before screenshots — 62e06b6

### Phase 2: Token values and components

#### Automated

- [x] 2.1 Lint, typecheck, tests and build pass — 852754e
- [x] 2.2 Raw colours appear only in the token blocks — 852754e
- [x] 2.3 The five component files exist under src/components/ui — 852754e

#### Manual

- [x] 2.4 Dark-mode token values switch and the inquiry view still matches — 852754e

### Phase 3: i18n foundation

#### Automated

- [x] 3.1 Lint, typecheck, tests and build pass
- [x] 3.2 The key-parity test passes
- [x] 3.3 The language-switch test passes

### Phase 4: App shell (the one view)

#### Automated

- [ ] 4.1 Lint, typecheck, tests and build pass
- [ ] 4.2 The shell views have no hardcoded colour or arbitrary value
- [ ] 4.3 ROLE_LABEL is gone
- [ ] 4.4 The test asserting HealthFooter is absent for anonymous visitors passes

#### Manual

- [ ] 4.5 App opens in Polish, switch persists and html lang follows
- [ ] 4.6 Sign in, fetch, filter, select and sign out all work
- [ ] 4.7 Roles show the right translated label
- [ ] 4.8 Header fits at 375 px without horizontal scroll
- [ ] 4.9 Inquiry view still matches its Phase 1 screenshots

### Phase 5: States, visual gate and guardrails

#### Automated

- [ ] 5.1 Lint, typecheck, tests and build pass
- [ ] 5.2 The kitchen sink is excluded from the build
- [ ] 5.3 AGENTS.md and the tech-stack Frontend section exist

#### Manual

- [ ] 5.4 Kitchen sink shows every 7-state cell or N/A with a reason
- [ ] 5.5 Screenshots saved at desktop and 375 px in both themes
- [ ] 5.6 Field borders and focus rings measure at least 3:1 in both themes
