---
date: 2026-11-16T13:17:28+01:00
researcher: Claude (Opus 5.5)
git_commit: 19c993f
branch: claude/recursing-solomon-072a8c
repository: agent-orchestrator
topic: "Two-way UI audit of the app shell (LoginForm, Inbox header + list, App) for the F-03 design-system + PL|EN foundation"
tags: [research, ui, design-system, tailwind, shadcn, i18n, accessibility, app-shell]
status: complete
last_updated: 2026-11-16
last_updated_by: Claude (Opus 5.5)
---

# Research: app-shell audit for design-system-i18n-foundation (F-03)

**Date**: 2026-11-16T13:17:28+01:00
**Researcher**: Claude (Opus 5.5)
**Git Commit**: 19c993f
**Branch**: claude/recursing-solomon-072a8c
**Repository**: agent-orchestrator

## Research Question

Two-way audit (source → views, view → source) of the app shell — `LoginForm`, the Inbox header and list, `App` — recorded as charges with `file:line` and user effect. Also verify: the missing `@/` alias, compatibility of Tailwind v4 / shadcn / react-i18next with TS 7 and Vite 8, the inbox empty state and the login error state in the 7-state matrix, and record the frontend decisions in `tech-stack.md` (Open Roadmap Question 4).

Scope: the shell only. `AnalysisPanel` and its sections belong to S-11 / S-12 and were not audited here (see `context/audits/ux/2026-11-16-prism-analysis-flow.md`).

## Summary

- **The design-system contract is absent, both halves.** Values: 8 colour tokens in `frontend/src/index.css:1-28` and no role tokens for primary, input, ring or radius. Components: no shared-component directory (`frontend/src/components/` holds 20 files, none is a primitive). Every view styles plain elements through global and BEM selectors. The literal scan over the shell `.tsx` files finds 0 hits because the debt is in the stylesheet: 168 lines with px/rem values in the 908-line `index.css`, including `6px` on 13 lines and `999px` on 4 lines.
- **All five pre-audit charges hold.** Two anchors move: the `<h1>` is at `App.tsx:46`, not `:47`, and the dark `--border` sits on `index.css:23` (confirmed). The ~430 test-query figure is now measured: **456** Testing Library query calls across `frontend/src`, of which **82** are in the four shell test files.
- **The stack works with the pinned toolchain** (`typescript@7.0.2`, `vite@8.3.7`), but two setup notes are not optional:
  1. shadcn's Vite guide adds `"baseUrl": "."`. TypeScript 7 removed `baseUrl` (TS5101 in TS 6.0: "will stop functioning in TypeScript 7.0"), so the alias has to be `"paths": { "@/*": ["./src/*"] }` **without** `baseUrl`.
  2. Vite 8 resolves the alias natively with `resolve.tsconfigPaths: true`, so no `path.resolve(__dirname)` alias is needed.
- **Dark mode is OS-driven** (`@media (prefers-color-scheme: dark)`, `index.css:17-28`), and there is no theme toggle. shadcn's default is a `.dark` class, but Tailwind v4's default `dark:` variant is that same media query. Keeping the media query keeps current behaviour and needs no `@custom-variant`.
- **Candidate token values reach WCAG 1.4.11 in both themes.**

  | Token | Light | Dark |
  |---|---|---|
  | `--input` (field border) | `#818b98`, 3.45:1 on card | `#6e7681`, 3.77:1 on card |
  | `--ring` | `#0969da`, 4.88:1 on bg | `#4493f8`, 6.11:1 on bg |

  A blue `--primary` is a **new colour**: the repo has no accent today. Approving it is a decision for the plan.

## Charges

Each charge has a category, evidence (`file:line`) and the user effect. All five map to phases in the plan (env/library → token values → one view → states), except the one deferred piece named under charge 4.

### C-1 [Missing shared component] One global `button` style for every action

- **Evidence:**
  - The global selector at `frontend/src/index.css:51-59` (border `var(--border)`, background `var(--card)`) styles all of these the same way: Sign in (`LoginForm.tsx:63`), Sign out (`Inbox.tsx:198`), Fetch mail (`Inbox.tsx:212`), list Retry (`Inbox.tsx:227`), the session-error Retry (`App.tsx:51`), the "Awaiting supervisor only" toggle (`Inbox.tsx:233-240`) and each inquiry row (`Inbox.tsx:252`). The last two get class overrides.
  - Disabled is only `opacity: 0.6` plus `cursor: default` (`index.css:61-64`).
  - The toggle carries `aria-pressed` (`Inbox.tsx:236`). Whether its pressed state has its own visual style is an open item for the plan.
- **User effect:** nothing marks the primary action. "Sign in" looks the same as "Sign out", and "Fetch mail" looks the same as "Retry".
- **Direction:** shadcn `Button` with `default` / `outline` / `ghost` / `destructive` variants. Inquiry rows stay a list-item pattern and do not become a Button variant.

### C-2 [Missing tokens / WCAG 1.4.11, 2.4.7] Field and button borders under 3:1, no focus style

- **Evidence:**
  - `--border` is `#d1d9e0` in light (`index.css:6`) and `#3d444d` in dark (`index.css:23`).
  - It is used for the login inputs (`index.css:102-110`, background `var(--bg)`) and for every button (`index.css:53`).
  - Measured contrast: 1.43:1 on card and 1.34:1 on bg (light); 1.76:1 on card and 1.92:1 on bg (dark).
  - `index.css` has **0** lines containing `focus`, so focus falls back to the browser default ring.
- **User effect:** a low-vision user may not see where the username and password fields are. Keyboard focus is inconsistent between browsers and themes.
- **Direction:**
  - Add a `--input` token for control borders and a `--ring` token for `:focus-visible`.
  - Keep `--border` for decorative dividers and cards, where 1.4.11 does not apply.

### C-3 [Missing tokens] Colour-named palette, no scales

- **Evidence:**
  - Only 8 colour tokens (`index.css:2-9`, `:19-26`). They are named by meaning (`ok`/`warn`/`error`), but there is no `primary`, `accent`, `input`, `ring`, `destructive` or `radius`.
  - No spacing or type scale: 168 lines in `index.css` contain a px/rem value; `6px` radius appears on 13 lines and `999px` on 4.
  - The badges (`index.css:194-230`) map inquiry statuses directly to `ok`/`warn`/`error`/`border`. Their filled variant `.badge--awaiting_supervisor` reads at 4.87:1 light and 6.86:1 dark (passes). The labels come from `OUTCOME_LABEL` (`Inbox.tsx:32-36`) plus literals (`Inbox.tsx:266`, `:270`).
- **User effect:** every new view picks its own values. The upcoming S-11 to S-15 views would copy the drift.
- **Direction:**
  - Semantic shadcn tokens in `:root` and in the `prefers-color-scheme: dark` block, published through `@theme inline`.
  - Map the existing values onto role names: `--text`→`--foreground`, `--muted`→`--muted-foreground`, `--bg`→`--background`, `--card`→`--card`, `--error`→`--destructive`, `--border`→`--border`.
  - Keep `--ok` / `--warn` as `--success` / `--warning`, extra tokens beyond the shadcn defaults.
  - A shadcn `Badge` with status variants replaces `.badge--*`.

### C-4 [Accidental architecture] No app shell

- **Evidence:**
  - The `<h1>` lives in `App` (`App.tsx:46`).
  - The user identity, role and Sign out live inside `Inbox` (`Inbox.tsx:193-201`), so they exist only on the inbox screen.
  - `HealthFooter` renders in every `App` state, including loading, anonymous and error (`App.tsx:60`). Logged-out visitors therefore see database and migration status (`HealthFooter.tsx:30-37`).
  - Page width switches on auth state (`App.tsx:45`).
- **User effect:** there is no place for the PL|EN switch (FR-021) or for the navigation S-11 and S-15 need, and an anonymous visitor sees the migration number.
- **Direction:** an `AppShell` component (header with title, a nav slot, the language switch, and the user menu with Sign out when authenticated) wraps both login and inbox.
- **Deferred → S-11:** moving or hiding `HealthFooter` (PRD v2 Access Control: no system status before login). Reason: S-11 builds the system page it moves to. If the plan finds hiding it for anonymous users is a one-line change, it may pull that piece forward.

### C-5 [Accidental architecture / FR-021] English hardcoded, no language switch

- **Evidence:**
  - Strings are written inline:
    - `App.tsx`: lines 46, 47, 50, 52.
    - `LoginForm.tsx`: lines 24, 27, 35, 38, 48, 64.
    - `Inbox.tsx`: maps at lines 32-36; messages at 39, 45, 60; JSX at 199, 211, 213, 223, 228, 239, 243, 246, 266, 270, 288, 290.
    - `HealthFooter.tsx`: lines 6-11 and 26-36.
    - `ROLE_LABEL` in `frontend/src/api/auth.ts:15-18`.
  - The document language is fixed: `<html lang="en">` (`frontend/index.html:2`).
  - `Inbox.tsx:59` matches a backend message by its English text (`'Mailbox unavailable'`). That coupling is the S-16 "backend messages by code" item.
  - Tests query by visible text: 456 Testing Library query calls in `frontend/src`, 82 of them in the four shell test files (`App.test.tsx` 34, `Inbox.test.tsx` 33, `HealthFooter.test.tsx` 8, `LoginForm.test.tsx` 7).
- **User effect:** a Polish salesperson works in an English interface and cannot switch. Screen readers announce Polish content with English pronunciation rules once translations land, unless `lang` follows the choice.
- **Direction:**
  - react-i18next with bundled resources (no HTTP backend) and Polish as the default.
  - The choice is persisted in `localStorage`, and `document.documentElement.lang` is updated on `languageChanged`.
  - The test setup initialises i18next with `lng: 'en'`, as recommended in the react-i18next testing guide, so the 456 queries keep passing against English resources that equal today's strings.

## Detailed Findings

### Toolchain and compatibility (verified 2026-11-16)

The installed toolchain is `typescript@7.0.2` and `vite@8.3.7` (`npm ls`). `frontend/package.json` declares only `react` and `react-dom` as runtime dependencies.

| Package | Latest | Peer range (npm) | Fits TS 7.0.2 / Vite 8.3.7 / React 19.3 |
|---|---|---|---|
| `tailwindcss` | 4.3.5 | — | yes |
| `@tailwindcss/vite` | 4.3.5 | `vite ^5.2.0 \|\| ^6 \|\| ^7 \|\| ^8` | yes |
| `shadcn` (CLI) | 4.23.0 | — | yes (dev-time tool) |
| `radix-ui` | 1.8.1 | `react ^16.8 … ^19.0` | yes |
| `react-i18next` | 18.0.2 | `i18next >=27.0.1`, `typescript ^5 \|\| ^6 \|\| ^7`, `react >=18` | yes |
| `i18next` | 27.1.3 | `typescript ^5 \|\| ^6 \|\| ^7` | yes |
| `lucide-react` | 1.73.0 | `react … ^19.0.0` | yes |
| `sonner` | 2.0.8 | `react ^18 \|\| ^19` | yes; not needed in F-03 |
| `class-variance-authority` / `clsx` / `tailwind-merge` / `tw-animate-css` | 0.7.1 / 2.1.1 / 3.7.0 / 1.4.0 | — | yes (shadcn utilities) |

Sources:
- Context7 `/websites/ui_shadcn`: the Vite install guide.
- Context7 `/tailwindlabs/tailwindcss.com`: `@theme inline`, and the `dark:` variant defaulting to `prefers-color-scheme`.
- Context7 `/websites/react_i18next`: quick start and testing guide.
- Context7 `/vitejs/vite/v8.3.5`: `resolve.tsconfigPaths`.
- Context7 `/microsoft/typescript/v7.0.2`: TS5101 `baseUrl` deprecation, and TS5090 for non-relative `paths` without `baseUrl`.

### Path alias `@/`

- Absent: neither `frontend/tsconfig.app.json` nor `frontend/tsconfig.json` sets `paths`, and `frontend/vite.config.ts` has no `resolve` key.
- Required shape under TS 7:
  - `"paths": { "@/*": ["./src/*"] }` in `tsconfig.app.json` (used for typechecking) and in the root `tsconfig.json` (read by the shadcn CLI). Both use a `./` prefix, because TS5090 rejects non-relative targets when `baseUrl` is unset.
  - `resolve: { tsconfigPaths: true }` in `vite.config.ts`. Vitest reads the same Vite config (`vite.config.ts:20-23`), so tests resolve the alias too.

### Theme mechanics

- Current: `:root` values plus a dark override inside `@media (prefers-color-scheme: dark)` (`index.css:1-28`), and `color-scheme: light dark` (`index.css:12`).
- With Tailwind v4: the values stay in `:root` and in that same media block, and `@theme inline` publishes them as `--color-*`.
- Writing raw colours inside `@theme inline` would freeze the light values and break dark mode. That is the classic failure the /10x-ui contract warns about.

### 7-state matrix on the shell (current state)

| State | Login | Inbox header / list | Status now |
|---|---|---|---|
| default | `LoginForm.tsx:34-67` | `Inbox.tsx:192-285` | global element styles, no tokens for roles |
| hover | none | none | **missing** (0 `hover` rules in `index.css`) |
| focus-visible | browser default | browser default | **missing** (0 `focus` rules) |
| disabled | `LoginForm.tsx:63` while submitting | Sign out `:198`, Fetch `:212` while pending | opacity 0.6 only |
| error | `LoginForm.tsx:58-62`, `role="alert"`, next to the button | list error `Inbox.tsx:224-231`; sign-out error `:202-206`; fetch error `:218` | present; colour via `--error`, text carries meaning |
| empty | N/A (form) | `Inbox.tsx:242-247`: two distinct messages (no inquiries / none awaiting) | present as plain muted text, no empty-state treatment |
| loading | App session check `App.tsx:47` (text) | `Inbox.tsx:223` (text) | text only; no skeleton, layout jumps when the list arrives |


## Code References

- `frontend/src/index.css:1-28`: the 8 colour tokens, light and dark (media-query driven)
- `frontend/src/index.css:51-64`: global `button` and `button:disabled`
- `frontend/src/index.css:102-110`: login input border, `--border`
- `frontend/src/index.css:194-230`: badge variants mapped to ok/warn/error
- `frontend/src/App.tsx:44-61`: page layout, `<h1>`, HealthFooter in all states
- `frontend/src/components/LoginForm.tsx:33-67`: form, error, submit
- `frontend/src/components/Inbox.tsx:32-60`: outcome labels and fetch-status messages; `:59` English backend-message match
- `frontend/src/components/Inbox.tsx:193-285`: header, list, filter, empty states, badges
- `frontend/src/components/HealthFooter.tsx:24-39`: status panel with migration
- `frontend/src/api/auth.ts:15-18`: `ROLE_LABEL`
- `frontend/index.html:2`: `lang="en"`
- `frontend/vite.config.ts:11-23`: no `resolve`, Vitest config shared
- `frontend/tsconfig.app.json`: no `paths`
- `frontend/src/test/setup.ts`: where the i18n test init (`lng: 'en'`) goes

## Architecture Insights

- The app has no router (`App.tsx:17`). Session state selects the view. An `AppShell` can wrap the existing state switch without introducing TanStack Router; the router belongs to S-17 (shareable URLs).
- The codebase convention puts no API calls in components beyond the `api/*` wrappers, and `api/auth.ts` exports display labels. Moving `ROLE_LABEL` to i18n keys removes UI copy from the API layer.
- Badge colours already pair a text label with colour (comment at `index.css:194`), which satisfies WCAG 1.4.1. The Badge component should keep that rule.

## Historical Context (from prior changes)

- No prior change in `context/changes/**` or `context/archive/**` mentions Tailwind, shadcn, i18n, a component library or a plain-CSS decision (grep over both trees, 2026-11-16). The plain CSS grew slice by slice without a recorded decision.
- `context/foundation/tech-stack.md:28` records only "A separate React + TypeScript frontend … added manually in the first change". The frontend stack choice is undocumented (Open Roadmap Question 4).
- `context/foundation/lessons.md` (JSONB / model change needs a migration) supports translating backend messages by stable code at display time rather than rewriting stored JSONB. That work is S-16, not this change.

## Related Research

- `context/audits/ux/2026-11-16-prism-analysis-flow.md`: Prism UX + WCAG audit; source of the contrast and focus findings.
- `context/foundation/prd.md` v2: FR-015 to FR-021, NFR WCAG 2.2 AA, 375 px.

## Decisions to record in tech-stack.md (Open Roadmap Question 4)

The plan for this change records the frontend stack in `context/foundation/tech-stack.md`. This research only surfaces the content; writing it there is a plan or implement step, so that the decision lands together with the code. Content:

- React 19 + Vite 8 + TypeScript 7 stay.
- Added: Tailwind v4 via `@tailwindcss/vite`; shadcn/ui primitives copied into `src/components/ui` (Radix via `radix-ui`); lucide-react icons; react-i18next + i18next with bundled PL/EN resources, Polish as default.
- Parked: TanStack Router (S-17), sonner (S-14), TanStack Query, Next.js and SSR.
- Constraints: no `baseUrl` (TS 7); alias via `paths` plus `resolve.tsconfigPaths`; dark mode stays `prefers-color-scheme`; tests run in English.

## Open Questions

Decisions for `/10x-plan`. The research cannot settle these.

1. **Primary colour.** The repo has no accent. Candidates `#0969da` (light) and `#4493f8` (dark) pass for ring and primary-foreground (5.19:1 and 6.11:1), but a new brand colour is a product choice.
2. **Migration strategy for `index.css`.** Option one: shell views move to Tailwind utilities and the old selectors are deleted only for the shell, while `AnalysisPanel` keeps its BEM CSS until S-11/S-12. Option two: a global swap. Tailwind's preflight reset will change the unstyled `AnalysisPanel` (margins, lists, headings), so the first option needs a check of that view after Preflight lands.
3. **Language-switch placement and form.** A segmented `PL | EN` in the shell header (FR-021) on both login and inbox. Confirm it stays visible at 375 px.
4. **Whether to hide `HealthFooter` for anonymous users now** (one line in `App.tsx:60`) or leave all of it to S-11.
5. **Test strategy for Polish.** English stays pinned for the 456 queries. Should one smoke test per shell view assert the Polish render, to catch missing keys?
