# Inquiry steps (S-12) Implementation Plan

## Overview

The inquiry view becomes a four-step flow — **Zapytanie → Warianty → Akceptacja → Odpowiedź** — shown one step at a time. Each step shows the data needed for its decision first and then one distinguished primary action, visible without scrolling at 1440×900. Destructive actions are visually distinct, every piece of information appears once, and a move back to an earlier step is announced. All UI text of the view goes through `t()` (PL default, EN in tests). This is roadmap S-12 (north star of M-2), PRD FR-016, US-01, FR-002, FR-010, FR-011 and the WCAG reading-order / 375 px NFRs.

## Current State Analysis

- The view is one long stack. `Inbox` renders the full e-mail (`<article>` with subject, sender, body) above `AnalysisPanel` in the right column (`frontend/src/components/Inbox.tsx:309-331`). `AnalysisPanel` renders the corrections form, then `ChecksSection`, then `DecisionHistory` (`AnalysisPanel.tsx:466-637`).
- `ChecksSection` hosts the four exception sections — Orchestration, Recommendation, Policy, ReplyDraft — between its banner and the individual check list, and only when `checks.outcome === 'exception'` (`ChecksSection.tsx:354-415`). The check results the decision depends on are therefore rendered after the decision buttons (audit WCAG 1.3.2).
- A standard inquiry ends at the checks (banner `checks.standard`), and `needs_input` shows a reasons list; neither has variants, policy or a draft (PRD FR-004).
- There is no overall inquiry status. State has to be derived from: `fetchAnalysis` → `null` (not analysed, `api/analysis.ts:1131`); `checks` null / `stale` / `outcome` (`'standard'|'exception'|'needs_input'`, `analysis.ts:78`); `orchestration.status`; `recommendation` (`status`, `stale`); `policy` (`stale`); `draft.status` (`'draft'|'ready_to_send'|'awaiting_supervisor'|'rejected'`, `analysis.ts:378`) and `draft.stale`. Nothing sends a reply; `ready_to_send` is the end state.
- Draft gating already lives in `ReplyDraftSection`: `offerRegenerate`, `canDecide`, `awaiting`, `supervisorActions` (four-eyes: the submitter may only reject) (`ReplyDraftSection.tsx:125-172`). Backend rules: approve → `ready_to_send` or `awaiting_supervisor` depending on the policy in force; reject → `rejected`; regenerate refused for decided drafts; every draft write carries `updated_at` (409 `DRAFT_CHANGED`).
- Duplicates: "Why this recommendation?" in `RecommendationSection.tsx:165` and again in `ReplyDraftSection.tsx:354-367`; the policy table in `PolicySection.tsx:164-195` and again as `VerdictInForce` in `ReplyDraftSection.tsx:375-419`; `OUTCOME`/`RULE`/`VERDICT` maps copied (`PolicySection.tsx:34-58`, `ReplyDraftSection.tsx:74-90`); `errorMessage` in all five files; `deadlineText` and `sourceText` twice.
- Text: nearly everything in `AnalysisPanel` and the five sections is hard-coded English; `PolicySection` has no `t()` at all. `i18n.test.ts` enforces equal key sets and non-empty values in `pl.json`/`en.json`. Tests run in English (`src/test/setup.ts`).
- Tests (~70 tests, ~3 000 lines across `AnalysisPanel.test.tsx` and five section tests) query by English role names, region names derived from the `h4` headings, and exact texts; `ChecksSection.test.tsx` relies on Orchestration being nested inside it (`:263-306`).
- UI kit: `ui/` has badge, button, card, input, label, sheet, table — no tabs. `radix-ui` (unified package) is already a dependency, so the shadcn `tabs` component needs no new npm package.
- The detail `<section>` in `Inbox` carries `aria-live="polite"` (`Inbox.tsx:297`), so any change inside the whole panel is announced.

## Desired End State

Opening an analysed exception inquiry at 1440×900 shows a compact header (subject, sender, date), a step bar with four numbered steps and their state, and the panel of the active step whose primary action is above the fold. The salesperson can open completed steps to review them; future steps are disabled; for a standard inquiry the last three steps read "not needed". Approve / Edit offer / Reject (and the supervisor's decision) sit in Akceptacja next to the chosen variant, the policy verdict in force and the e-mail preview; Odpowiedź shows the ready-to-send result. Rejecting, re-analysing or a stale result moves the flow back with a status message saying why. Every text of the view exists in Polish and English. At 375 px there is no horizontal page scroll.

Verify: `npm run lint && npm run typecheck && npm test && npm run build` in `frontend/`; the manual DOM gate in Phase 5 (bounding box of each step's primary action at 1440×900, `scrollWidth` at 375 px).

### Key Discoveries:

- The step can be a pure function of `Analysis | null` plus nothing else; all needed flags already arrive in one `GET /analysis` response (`AnalysisPanel.tsx:271`).
- `AnalysisPanel` already owns every handler and the shared `busy` state; sections only render and call back (`AnalysisPanel.tsx:323-405`), so moving sections between steps does not move any API logic.
- Keeping the English wording in `en.json` while moving to `t()` leaves most text-based test assertions valid, so translation goes first and the layout rewrite touches tests once.
- shadcn `tabs` on `radix-ui` gives roving focus and arrow-key navigation; disabled triggers model locked future steps.

## What We're NOT Doing

- Step or tab in the URL, `?redirect=` (S-17).
- Readable variant names and side-by-side variant comparison (S-13); the edit form's interim `{kind} · {value}` label stays.
- Renaming "Approve" to "Send to supervisor", inbox status badges, post-decision toast/status beyond the step-back message, sign-out focus (S-14).
- Supervisor queue and restricting the supervisor's editing/re-analysis rights (S-15); in S-12 the supervisor decides in Akceptacja exactly as today.
- Translating backend-produced texts by code — check reasons from the API, policy rule reasons, confidence signals (S-16). UI-side wording of statuses and labels is in scope.
- Any backend or API change; any new step-status field in the API.
- A 3-pane layout; E2E tests in CI.

## Implementation Approach

1. Move every UI text of the view into the locale files without changing English wording, and extract the copied policy maps and helpers into one module. Behaviour and tests stay as they are.
2. Introduce `inquirySteps(analysis)` (pure, tested) and a stepper (shadcn Tabs) inside `AnalysisPanel`. Lift the four exception sections out of `ChecksSection` and place them into steps; move the e-mail body from `Inbox` into the Zapytanie step.
3. Rebuild the content of Zapytanie and Warianty: data before actions, one primary action per state, re-runs secondary, orchestration findings collapsible.
4. Rebuild Akceptacja and Odpowiedź: split the decision out of `ReplyDraftSection`, remove the duplicated justification and policy table, put the decision history in Akceptacja.
5. Kitchen-sink states, manual DOM gate, AGENTS.md scan list, dead legacy CSS.

## Critical Implementation Details

- **Step derivation (the contract every phase relies on).** `inquirySteps(analysis)` returns the active step and a state per step (`done | active | locked | not_needed`). Active step:
  - `analysis === null`, `checks === null`, `checks.stale`, or `outcome === 'needs_input'` → **inquiry**;
  - `outcome === 'standard'` → **inquiry** is `done` and is the shown step; variants/approval/reply are `not_needed`;
  - `outcome === 'exception'` and the recommendation is missing, `failed` or `stale` (incl. orchestration missing/not completed) → **variants**;
  - exception with a current recommendation and the draft missing, `stale`, `draft`, `awaiting_supervisor` or `rejected` → **approval**;
  - draft `ready_to_send` and not stale → **reply**.
  Steps before the active one are `done`; steps after it are `locked`.
- **Viewed vs active step.** `AnalysisPanel` keeps `viewedStep` (initially the active step). When the active step changes after a load or an action: moving forward selects the new active step; moving backward (e.g. reject, re-analysis, stale result) selects it and sets a `role="status"` message naming the step and the reason. A user's own click on a `done` step does not produce a message. Loading another inquiry resets both (the panel is keyed by inquiry id).
- **Live region.** The detail `<section aria-live="polite">` in `Inbox` would announce the whole step panel on every switch; drop `aria-live` there and keep announcements to the explicit `role="status"` / `role="alert"` messages.
- **Primary action per state** uses the default `Button` variant; all other actions are `outline` (or `ghost` for "back"/disclosure); Reject, "Re-analyze anyway" and the supervisor's Reject are `destructive`. Exactly one default-variant button is visible per step panel at a time.

## Phase 1: Teksty widoku zapytania przez t()

### Overview

Every UI string in `AnalysisPanel` and the five sections goes through `t()`, with Polish translations and English values equal to today's wording. The copied policy maps and helpers move to one shared module. No layout or behaviour change.

### Changes Required:

#### 1. Locale files

**File**: `frontend/src/i18n/locales/pl.json`, `frontend/src/i18n/locales/en.json`

**Intent**: Add keys for all headings, buttons, labels, notes, banners, form validation messages, `aria-label`s, status/action/rule/verdict/outcome labels and interpolated lines of the inquiry view. English values reproduce the current strings exactly (so existing tests keep passing); Polish values are written fresh.

**Contract**: Namespaces per component (`analysis.*`, `checks.*`, `orchestration.*`, `recommendation.*`, `policy.*`, `draft.*`, `decisionHistory.*`), extending existing keys rather than renaming them. Interpolation via `{{name}}`. Plurals via i18next `_one/_few/_many/_other` where a count is shown. Both files keep identical key sets (`i18n.test.ts`).

#### 2. Components

**File**: `frontend/src/components/AnalysisPanel.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `RecommendationSection.tsx`, `PolicySection.tsx`, `ReplyDraftSection.tsx`

**Intent**: Replace hard-coded text with `t()`, including module-level label maps (`PRICE_KIND_LABEL`, `SUBSTITUTE_LABEL`, `INPUT_LABEL`, `STATUS`, `ACTION`, …) which become key maps resolved at render time; the "Something went wrong" fallback becomes a key.

**Contract**: Backend-produced free text (check reasons from the API, rule reasons, signal texts, model justification, e-mail subject/body) is rendered as received — not translated (S-16).

#### 3. Shared policy and formatting helpers

**File**: `frontend/src/components/policyLabels.ts` (new), `frontend/src/components/format.ts`

**Intent**: One source for rule/verdict/outcome label keys and threshold formatting used by PolicySection and the draft's verdict-in-force; one `errorMessage`, `deadlineText`, `sourceText` in `format.ts`. Removes the copies listed in Current State.

**Contract**: Pure functions/maps; no React. Remove the now-unused `stepCost`/`totalCost`/`totalDuration` from `format.ts` only if nothing imports them (they were flagged unused after S-11).

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Locale key parity and non-empty values pass: `cd frontend && npx vitest run src/i18n/i18n.test.ts`
- No duplicated policy maps remain: `grep -nE "^const (OUTCOME|RULE|VERDICT)\b" frontend/src/components/*.tsx` prints nothing
- `PolicySection.tsx` uses translations: `grep -c "useTranslation" frontend/src/components/PolicySection.tsx` prints a number ≥ 1

#### Manual Verification:

- With the language switch on PL the whole inquiry view (form, checks, all four exception sections, decision forms, decision history) reads in Polish; on EN it reads as before

---

## Phase 2: Model kroków i stepper

### Overview

Add the step model and the step bar; reorganise the existing sections into four step panels and move the e-mail into the Zapytanie step. Section contents stay as they are in this phase (Phases 3–4 rebuild them).

### Changes Required:

#### 1. Step model

**File**: `frontend/src/components/inquirySteps.ts` (new), `inquirySteps.test.ts` (new)

**Intent**: Pure derivation of the active step and per-step state from `Analysis | null`, per the rules in Critical Implementation Details, plus the step-back reason used for the status message.

**Contract**: `type StepId = 'inquiry' | 'variants' | 'approval' | 'reply'`; `type StepState = 'done' | 'active' | 'locked' | 'not_needed'`; `inquirySteps(analysis: Analysis | null): { active: StepId; states: Record<StepId, StepState> }`; `stepBackReason(prev: Analysis | null, next: Analysis | null): string | null` returning an i18n key (e.g. draft rejected, analysis replaced, result outdated). Unit tests cover every row of the derivation table, standard and needs_input, stale at each stage, awaiting_supervisor, rejected, ready_to_send.

#### 2. Tabs component

**File**: `frontend/src/components/ui/tabs.tsx` (via `npx shadcn@latest add tabs`)

**Intent**: The step bar primitive.

**Contract**: Apply the AGENTS.md post-`shadcn add` checklist (imports from `@/lib/utils`, no `cn` package, no `.dark`, solid `focus-visible:ring-ring`).

#### 3. Stepper in the panel

**File**: `frontend/src/components/InquirySteps.tsx` (new), `frontend/src/components/AnalysisPanel.tsx`

**Intent**: `InquirySteps` renders the step bar (number, name, state as text — not colour alone — and `not needed` / disabled for locked steps) and the panel of the viewed step. `AnalysisPanel` holds `viewedStep`, derives steps on every `show()`, sets the step-back status message, and places: form + checks → inquiry; orchestration + recommendation → variants; policy + reply draft + decision history → approval; reply draft result → reply (temporarily the same `ReplyDraftSection` until Phase 4).

**Contract**: Radix Tabs controlled by `viewedStep`; triggers of `locked`/`not_needed` steps are `disabled`. The run-inspector link stays in the panel header.

#### 4. Sections leave ChecksSection

**File**: `frontend/src/components/ChecksSection.tsx`, `ChecksSection.test.tsx`

**Intent**: `ChecksSection` renders only the checks (banner, uncertain inputs, individual checks, re-run). The four exception sections are rendered by `AnalysisPanel` in their steps; their props move with them.

**Contract**: `ChecksSection` props shrink to `inquiryId, analysis, disabled, running, onRerun, onUnauthorized`. Nesting assertions in `ChecksSection.test.tsx` move to `AnalysisPanel.test.tsx`.

#### 5. E-mail in the Zapytanie step

**File**: `frontend/src/components/Inbox.tsx`, `AnalysisPanel.tsx`

**Intent**: The detail area keeps a compact header (subject, sender, date); the e-mail body is passed to `AnalysisPanel` and shown in the Zapytanie step above the parsed fields. In other steps it is available as a collapsed "Pokaż mail" disclosure. Remove `aria-live` from the detail section.

**Contract**: `AnalysisPanel` gains `inquiry: { body: string }` (or the body string) as a prop; `Inbox` stops rendering `.detail__body`.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Step derivation tests pass: `cd frontend && npx vitest run src/components/inquirySteps.test.ts`
- Panel tests cover: active step on load for each state, locked steps disabled, clicking a done step, step-back status message after reject and after re-analysis: `cd frontend && npx vitest run src/components/AnalysisPanel.test.tsx`
- `ChecksSection` no longer imports the exception sections: `grep -nE "import (Orchestration|Recommendation|Policy|ReplyDraft)Section" frontend/src/components/ChecksSection.tsx` prints nothing

#### Manual Verification:

- Arrow keys move between enabled step tabs; disabled steps are skipped; focus ring visible on every tab
- After rejecting a draft the view shows Akceptacja with a status message, and a screen-reader-visible `role="status"` text is present in the DOM

---

## Phase 3: Kroki Zapytanie i Warianty

### Overview

Order each step's content as data → primary action and make exactly one action primary for each state.

### Changes Required:

#### 1. Zapytanie step

**File**: `frontend/src/components/AnalysisPanel.tsx` (or an extracted `InquiryStep.tsx`), `ChecksSection.tsx`

**Intent**: Order: e-mail, parsed fields (with uncertainty marks), check results (banner, individual checks), then the action bar. Primary action by state: not analysed → "Analyze request"; unsaved corrections or reviewed marks → "Save corrections"; checks missing/stale → "Re-run checks"; exception with current checks → "Next: Variants" (selects the step); standard → no primary action, the banner states the inquiry is standard and needs no further steps; needs_input → "Save corrections" once the user edits, otherwise the reasons list tells what to fill. "Re-analyze" is secondary; its confirmation's "Re-analyze anyway" is `destructive`.

**Contract**: Exactly one default-variant `Button` in the step panel at a time (asserted in tests).

#### 2. Warianty step

**File**: `frontend/src/components/RecommendationSection.tsx`, `OrchestrationSection.tsx`, step composition in `AnalysisPanel`/`InquirySteps`

**Intent**: Order: recommended variant with "Why this recommendation?" and signals, other options, then a collapsed "Findings" disclosure with the orchestration results, then the action bar. Primary action: current recommendation → "Next: Approval"; recommendation missing/failed/stale → its re-run becomes primary; orchestration failed/partial → "Re-run orchestrator" primary. Re-runs otherwise appear only in the states where they appear today.

**Contract**: Section headings stay `h4` with `aria-labelledby`, so region queries keep working; disclosure via native `<details>`/`<summary>` styled with tokens.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Tests assert check results precede the action bar in DOM order and exactly one primary button per state in Zapytanie and Warianty: `cd frontend && npx vitest run src/components/AnalysisPanel.test.tsx src/components/ChecksSection.test.tsx src/components/RecommendationSection.test.tsx src/components/OrchestrationSection.test.tsx`
- AGENTS.md colour scan (with the new view files added) prints nothing

#### Manual Verification:

- Standard inquiry: Zapytanie shows the standard banner and the three other steps read "not needed"
- Needs-input inquiry: the reasons list sits above the action bar and saving a correction re-derives the step

---

## Phase 4: Kroki Akceptacja i Odpowiedź

### Overview

Put the decision next to the data that justifies it and remove the duplicates.

### Changes Required:

#### 1. Akceptacja step

**File**: `frontend/src/components/ReplyDraftSection.tsx` (split), `PolicySection.tsx`, new `ApprovalStep.tsx` if the split warrants it

**Intent**: Order: chosen variant summary (value, margin, coverage — no justification), the single policy table (the verdict in force: the draft's `policy` when a draft exists, otherwise the policy evaluation, labelled "edited offer" when the offer was edited), the e-mail preview (subject + body, collapsible if long), then the decision bar. Salesperson on a current `draft`: Approve (primary), Edit offer (outline), Reject (destructive), with the existing forms. Awaiting supervisor: non-supervisor sees "Waiting for a supervisor decision" and no primary action; supervisor sees Approve (primary, unless four-eyes forbids) / Reject (destructive). Rejected or stale draft: "Regenerate draft" primary with the reason shown. Policy missing/stale: "Re-run policy" primary. Decision history as a collapsed list at the end of the step.

**Contract**: Gating logic (`offerRegenerate`, `canDecide`, `awaiting`, `supervisorActions`) is reused unchanged; only placement changes. `VerdictInForce` and the draft's "Why this recommendation?" are deleted; PolicySection renders whichever verdict is in force.

#### 2. Odpowiedź step

**File**: `frontend/src/components/ReplyStep.tsx` (new) or the result part of `ReplyDraftSection`

**Intent**: For `ready_to_send`: status "Ready to send (sending is simulated)", the final e-mail, the approver and time from the last decision. No primary action (the flow is finished); the inspector link stays in the header.

**Contract**: Reads `draft` and the last entry of `decisions`; no API call.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- "Why this recommendation?" and the policy table each render once in a full exception analysis: `cd frontend && npx vitest run src/components/AnalysisPanel.test.tsx`
- Decision tests (approve → awaiting/ready, reject → back to Akceptacja with message, supervisor four-eyes, 409 draft-changed reload) pass: `cd frontend && npx vitest run src/components/ReplyDraftSection.test.tsx src/components/AnalysisPanel.test.tsx`
- No verdict-in-force copy remains: `grep -n "VerdictInForce" frontend/src` prints nothing

#### Manual Verification:

- As `sales` on the ACME inquiry: approve leads to Akceptacja "waiting for supervisor"; as `supervisor` approve leads to Odpowiedź
- Reject is visibly destructive and the reject reason is required

---

## Phase 5: Stany, bramka i porządki

### Overview

Make every step state reviewable in the kitchen sink, prove the success criterion in a browser, and clean up.

### Changes Required:

#### 1. Kitchen sink

**File**: `frontend/src/kitchen-sink.tsx`

**Intent**: Add stubbed analyses for: not analysed, needs_input, standard, exception at Warianty (failed recommendation), Akceptacja (draft), awaiting supervisor (as sales and as supervisor), rejected, ready_to_send — each rendered in the step view within the 7-state matrix where it applies.

**Contract**: Dev only; nothing added to `build.rollupOptions.input`.

#### 2. Docs and CSS

**File**: `AGENTS.md`, `frontend/src/styles/legacy.css`

**Intent**: Add `InquirySteps.tsx` and any new step components plus `AnalysisPanel.tsx`, `ChecksSection.tsx` and the four section files to the colour-scan list; delete legacy rules whose selectors no longer occur in `frontend/src` (no new legacy rules).

**Contract**: The AGENTS.md scan command, with the extended file list, prints nothing.

### Success Criteria:

#### Automated Verification:

- Lint, typecheck, tests and build pass: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- AGENTS.md colour scan with the extended list prints nothing
- Kitchen sink is not in the production build: `grep -n "kitchen-sink" frontend/vite.config.ts` shows no `rollupOptions.input` entry

#### Manual Verification:

- At 1440×900, for the ACME exception inquiry in each of Zapytanie, Warianty, Akceptacja and Odpowiedź (and the supervisor's Akceptacja), the primary action's `getBoundingClientRect().bottom` ≤ 900 with the page scrolled to the top (measured via DOM, not screenshots)
- At 375 px wide, `document.documentElement.scrollWidth` ≤ 375 in every step; the policy table does not hide columns without a signal
- Keyboard-only pass through all four steps: reading order is data → action; focus always visible
- One final screenshot per breakpoint as the visual check

---

## Testing Strategy

### Unit Tests:

- `inquirySteps.test.ts`: every derivation row, `stepBackReason` for reject / re-analysis / stale.
- Section tests keep their English role/text queries (EN wording unchanged); nesting assertions move from `ChecksSection.test.tsx` to `AnalysisPanel.test.tsx`.
- "Exactly one primary button per step state" helper assertion (by `data-variant` or class from `buttonVariants`).

### Integration Tests:

- `AnalysisPanel.test.tsx` with the router: load each state → correct active step; full approve/reject/supervisor paths; 409 reload keeps or moves the step correctly.

### Manual Testing Steps:

1. Log in as `sales`, open the ACME exception inquiry, walk Zapytanie → Warianty → Akceptacja, approve; check the waiting message.
2. Log in as `supervisor`, approve; check Odpowiedź.
3. Reject a draft; check the step-back message and Regenerate as primary.
4. Open a standard inquiry; check the "not needed" steps.
5. Switch PL/EN on every step.

## Performance Considerations

None: all data still comes from one analysis response; step derivation is a pure function per render.

## Migration Notes

No data or API change. Users with an open inquiry get the stepper on reload.

## References

- Roadmap item: `context/foundation/roadmap.md` (S-12)
- PRD: `context/foundation/prd.md` (FR-016, US-01, FR-002, FR-010, FR-011, NFR WCAG / 375 px)
- UX audit: `context/audits/ux/2026-11-16-prism-analysis-flow.md`
- Previous slice: `context/archive/2026-11-16-run-inspector-and-system-page/plan.md`
- Lessons: `context/foundation/lessons.md` (UI verification via ARIA/DOM first)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Teksty widoku zapytania przez t()

#### Automated

- [x] 1.1 Lint, typecheck, tests and build pass — 01f103f
- [x] 1.2 Locale key parity and non-empty values pass — 01f103f
- [x] 1.3 No duplicated policy maps remain — 01f103f
- [x] 1.4 PolicySection.tsx uses translations — 01f103f

#### Manual

- [x] 1.5 Inquiry view reads fully in Polish on PL and as before on EN — 01f103f

### Phase 2: Model kroków i stepper

#### Automated

- [x] 2.1 Lint, typecheck, tests and build pass — 171b92a
- [x] 2.2 Step derivation tests pass — 171b92a
- [x] 2.3 Panel tests cover active step, locked steps, done-step click, step-back message — 171b92a
- [x] 2.4 ChecksSection no longer imports the exception sections — 171b92a

#### Manual

- [x] 2.5 Arrow-key navigation skips disabled steps with visible focus — 171b92a
- [x] 2.6 Rejecting a draft returns to Akceptacja with a role=status message — 171b92a

### Phase 3: Kroki Zapytanie i Warianty

#### Automated

- [x] 3.1 Lint, typecheck, tests and build pass
- [x] 3.2 Data precedes actions and one primary button per state in Zapytanie and Warianty
- [x] 3.3 AGENTS.md colour scan prints nothing

#### Manual

- [x] 3.4 Standard inquiry shows the standard banner and three not-needed steps
- [x] 3.5 Needs-input reasons above the action bar; saving re-derives the step

### Phase 4: Kroki Akceptacja i Odpowiedź

#### Automated

- [ ] 4.1 Lint, typecheck, tests and build pass
- [ ] 4.2 Justification and policy table render once
- [ ] 4.3 Decision tests pass
- [ ] 4.4 No VerdictInForce copy remains

#### Manual

- [ ] 4.5 Sales approve waits for supervisor; supervisor approve reaches Odpowiedź
- [ ] 4.6 Reject is visibly destructive and requires a reason

### Phase 5: Stany, bramka i porządki

#### Automated

- [ ] 5.1 Lint, typecheck, tests and build pass
- [ ] 5.2 AGENTS.md colour scan with the extended list prints nothing
- [ ] 5.3 Kitchen sink is not in the production build

#### Manual

- [ ] 5.4 Primary action within 900 px at 1440×900 in every step
- [ ] 5.5 No horizontal scroll at 375 px in every step
- [ ] 5.6 Keyboard-only pass: data before action, focus always visible
- [ ] 5.7 One final screenshot per breakpoint
