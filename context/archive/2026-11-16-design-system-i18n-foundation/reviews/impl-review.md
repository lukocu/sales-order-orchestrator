<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Design system and PL|EN i18n foundation for the app shell

- **Plan**: context/changes/design-system-i18n-foundation/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4, 5
- **Date**: 2026-11-16
- **Verdict**: APPROVED
- **Findings**: 0 critical, 2 warnings, 4 observations
- **Triage**: F1–F5 fixed; F6 accepted, deferred to S-14

Commits reviewed: 62e06b6, 852754e, 2517263, 53f4627, 2eeb085, e08c42b (base 84d1438). Every automated criterion from the 5 phases was re-run and passes: lint, typecheck, 239/239 tests, build, no `baseUrl`, the `@/` import in tests, raw colours only in the token blocks, the 5 ui files, `ROLE_LABEL` gone, a 0-match hardcoded scan, the key-parity and switch tests, `dist/kitchen-sink.html` absent, and the `AGENTS.md` and `## Frontend` sections. The user confirmed all 11 manual rows during implementation.

Already decided in the plan and not findings: the HealthFooter is hidden for anonymous visitors (plan decision "hide now"). The known adaptations were verified as harmless: the `onUnauthorized` rename, the `--muted-surface` split, the oxlint override for `ui/**` and the kitchen sink, the solid focus ring, and the global `button` rule moved into the inquiry compatibility block.

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

## Findings

### F1 — Language switch accessible names don't contain the visible text

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (accessibility)
- **Location**: frontend/src/components/LanguageSwitch.tsx:22
- **Detail**: The buttons show "PL" and "EN", but `aria-label` replaces their accessible names with "Polski" and "English". The visible text is not part of the name, which fails WCAG 2.5.3 Label in Name, part of the change's WCAG 2.2 AA target. A voice-control user who says "click EN" gets no match.
- **Fix**: Change the label to start with the visible code, e.g. `aria-label={`${OPTION_LABEL[language]} – ${t(`language.${language}`)}`}` ("EN – English"). Update the switch test queries to match, e.g. `name: /Polski/`.
- **Decision**: FIXED

### F2 — shadcn `destructive` variants keep the literal `text-white`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/components/ui/button.tsx:13, frontend/src/components/ui/badge.tsx:15
- **Detail**: The token contract (and `AGENTS.md`) says no literal colours, but the generated `destructive` Button and Badge use `text-white`. The scan's file list doesn't cover `ui/`, so the next view that uses `variant="destructive"` inherits the literal. The colour itself passes contrast (5.36:1 light, 6.70:1 dark, per tokens.md). The existing `--destructive-foreground` (= `--card`) cannot replace it, because it fails in dark (2.58:1).
- **Fix**: Add an `--on-destructive` value `#fff` to both `:root` blocks, publish it via `@theme inline`, and use `text-on-destructive` in both variants. Record it in tokens.md.
- **Decision**: FIXED

### F3 — Inert second palette in legacy.css

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/styles/legacy.css:1-28
- **Detail**: The old `:root` blocks still define `--text`, `--bg`, `--card` and the rest with raw hex values, in light and dark. The unlayered aliases in `index.css` override them, so editing them does nothing. This contradicts "raw values only in index.css".
- **Fix**: Delete the colour declarations from legacy.css's two `:root` blocks, keeping `font`/`color-scheme`.
- **Decision**: FIXED

### F4 — Messages stored as translated strings keep the old language after a switch

- **Severity**: 💬 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (i18n)
- **Location**: frontend/src/components/Inbox.tsx:88-105, :163; frontend/src/App.tsx:60
- **Detail**: The fetch summary, the list and detail error fallbacks, and `signOutError` are translated when they happen and kept in state. After a PL/EN switch they stay in the old language until replaced. Switching language does not refetch, which is good.
- **Fix**: Store the key plus its params (or the raw error) in state and call `t()` at render time.
  - Strength: Every message follows the switch at once; matches how the rest of the shell renders text.
  - Tradeoff: Touches five or so state shapes in Inbox/App for a rare situation (switching while an error is shown).
  - Confidence: MED — straightforward, but the backend-message passthrough has to stay untranslated.
  - Blind spot: AnalysisPanel callbacks that feed these states were not traced.
- **Decision**: FIXED

### F5 — Dates stay in English format in the Polish UI

- **Severity**: 💬 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality (i18n)
- **Location**: frontend/src/components/format.ts:3
- **Detail**: `formatDate` uses a fixed `Intl.DateTimeFormat('en-GB')`, so the Polish inbox list shows "14 Nov 2026, 09:05". The plan did not cover formats. `format.ts` is shared with the inquiry view (S-11/S-12 scope).
- **Fix**: Format with the active language (`pl-PL` / `en-GB`) via `i18n.language` at call time, or defer to S-12 together with the inquiry view.
  - Strength: The Polish user sees "14 lis 2026, 09:05", consistent with the rest of the UI.
  - Tradeoff: Changes inquiry-view output too, and tests that assert dates would need EN pinning (already in place).
  - Confidence: MED — tests may assert formatted dates.
  - Blind spot: Haven't counted date assertions in the test suite.
- **Decision**: FIXED

### F6 — Focus drops to `<body>` while signing out

- **Severity**: 💬 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality (accessibility)
- **Location**: frontend/src/components/AppShell.tsx:42-50
- **Detail**: Sign out is disabled during the request, so keyboard focus falls to `<body>`. Its label doesn't change, and focus isn't moved to the sign-in form afterwards. This existed before the change.
- **Fix**: Defer to S-14 (feedback/toasts), which owns action feedback; no change in F-03.
- **Decision**: ACCEPTED — deferred to S-14 (action feedback); see follow-ups/review-fixes.md
