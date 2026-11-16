# Design system and PL|EN i18n foundation for the app shell — Plan Brief

> Full plan: `context/changes/design-system-i18n-foundation/plan.md`
> Research: `context/changes/design-system-i18n-foundation/research.md`

## What & Why

Roadmap item F-03 opens milestone M-2 (UX-driven redesign). The frontend has no design system: 8 colour tokens, no shared components, one global `button` style for every action, field borders under WCAG's 3:1, no focus style, and English text hardcoded throughout. This change brings in the contract the next views (S-11 to S-17) will inherit. That means semantic tokens and shadcn components, a PL | EN switch with Polish as the default, and an app shell they all sit in.

## Starting Point

React 19 + Vite 8 + TS 7 with plain CSS (`index.css`, 908 lines, OS-driven dark mode). There is no router and no `@/` alias. The header lives inside `Inbox`, and the system-status footer shows the migration number on the login screen. The tests make 456 text-based queries in English.

## Desired End State

The app opens in Polish, with a PL | EN switch in the header, and the choice persists. Login, header and inbox list are built from shadcn components styled only by tokens:
- The primary actions are blue.
- Every control shows a visible focus ring.
- Field borders pass 3:1 in light and dark.

The inquiry view looks unchanged. A dev-only kitchen-sink page shows the shell in all 7 states. `AGENTS.md` and `tech-stack.md` tell the next agent where the contract lives.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Stack | Stay on React + Vite + TS; add Tailwind v4, shadcn/ui, lucide, react-i18next | Smallest change that gives tokens and components the agent can read | Research (user, 2026-11-16) |
| Path alias | `paths` without `baseUrl` + Vite `resolve.tsconfigPaths` | TS 7 removed `baseUrl`, which shadcn's guide still adds | Research |
| Dark mode | Stay OS-driven (`prefers-color-scheme`) | Already Tailwind v4's default `dark:` variant; no toggle requested | Research |
| Primary colour | Blue `#0969da` light / `#4493f8` dark | Same family as the current palette; 5.19:1 and 6.11:1 measured | Plan |
| Old CSS | Preflight on, old CSS in a `legacy` layer, scoped compatibility block for the inquiry view | shadcn gets its expected base; S-11/S-12 only delete the block | Plan |
| HealthFooter | Hidden for anonymous visitors now; move to a system page in S-11 | One line meets PRD v2 Access Control while the shell already touches `App.tsx` | Plan |
| Test language | English pinned for all existing tests; key-parity test plus one Polish smoke test | Keeps 456 queries green and catches missing keys everywhere | Plan |
| Visual gate | Dev-only `kitchen-sink.html`, excluded from the build | No router or Playwright needed, no effect on the bundle | Plan |
| Agent rule | New `AGENTS.md` with a Frontend UI section | Repo has no rules file; the rule keeps later views on the tokens | Plan |

## Scope

**In scope:**
- Tailwind v4, the shadcn config and the `@/` alias.
- Tokens (light and dark).
- Button, Input, Label, Card, Badge.
- i18n with PL | EN.
- `AppShell`, `LoginForm`, the Inbox list column.
- HealthFooter visibility.
- Kitchen sink, screenshots, `AGENTS.md`, the `tech-stack.md` Frontend section.

**Out of scope:**
- The inquiry view rebuild (S-11/S-12).
- Moving HealthFooter to a system page (S-11).
- Backend messages by code (S-16).
- Router and URLs (S-17).
- Toasts (S-14).
- A manual theme toggle.
- Playwright.
- A custom lint rule.

## Architecture / Approach

`index.css` becomes the entry point:
- a layer order;
- the Tailwind import;
- the old stylesheet imported into a `legacy` layer below utilities, so new classes always win;
- role-named values in `:root` and the dark media block, published through `@theme inline`.

shadcn primitives live in `src/components/ui`. An i18next instance with bundled `pl`/`en` JSON initialises before render and keeps `<html lang>` and `localStorage` in sync. `AppShell` wraps every `App` state and owns the header, nav slot, language switch and user menu.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Toolchain and coexistence | Libraries, alias, Tailwind, old CSS fenced in a layer, app unchanged | Preflight shifting the inquiry view; cascade order |
| 2. Token values and components | Semantic tokens, blue primary, focus ring, five shadcn components | A raw colour in `@theme inline` breaking dark mode |
| 3. i18n foundation | PL/EN resources, persisted switch, EN-pinned tests, parity test | An English resource drifting from today's strings |
| 4. App shell | AppShell, login and inbox list on tokens + `t()`, HealthFooter hidden for anonymous visitors | Moving sign-out ownership without breaking tests |
| 5. States, gate, guardrails | Kitchen sink in 7 states, screenshots, `AGENTS.md`, stack record | Disabled or focus states missed because nothing on the happy path shows them |

**Prerequisites:** Local backend running (`docker compose` on `:8010`) with the seeded ACME inquiries for the manual checks; Node and npm for `npm ci`.

**Estimated effort:** ~3 sessions across 5 phases. Phases 1–2 and 3 are small; Phase 4 is the bulk.

## Open Risks & Assumptions

- The scoped compatibility block may miss a default the inquiry view relies on. The Phase 1 before/after screenshots are the check.
- `shadcn init`/`add` may try to add `baseUrl` or rewrite `index.css`; those edits get reverted by hand.
- The Polish translations of shell copy are written in this change without a native-speaker review beyond the user.

## Success Criteria (Summary)

- A Polish salesperson sees a Polish interface, can switch to English, and sees which action is primary.
- A keyboard or low-vision user can see every field and the focused control in light and dark.
- The next agent building S-11 finds tokens, components and the rule instead of inventing values.
