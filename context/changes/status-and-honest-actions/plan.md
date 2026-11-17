# Visible status and honest action labels Implementation Plan

## Overview

The user always sees one status of an inquiry: on the inbox list, in the header of the open inquiry, and as a message after every decision, announced to screen readers. When the policy requires supervisor approval, the salesperson's action is called "Wyślij do przełożonego" / "Send to supervisor", not "Zatwierdź" / "Approve". The plan also closes F6, which the F-03 review handed to S-14: focus is no longer lost while signing out. This is roadmap S-14: PRD FR-018, US-02, FR-011 and the NFR (WCAG 4.1.3 status messages).

## Current State Analysis

- `GET /api/inquiries` returns `InquirySummary` with `outcome` (the checks outcome, only while it is current) and `draft_status` (the raw stored draft status, also of a stale draft) (`backend/app/api/inquiries.py:24-68`). `InquiryDetail` extends it. Nothing tells whether an analysis exists: with no analysis and with stale checks, `outcome` is null in both cases. The query already outer-joins `inquiry_analyses` through `with_current_outcome` (`backend/app/checks/service.py:202-206`).
- Literals: checks `outcome` ∈ `standard | exception | needs_input`; draft `status` ∈ `draft | ready_to_send | awaiting_supervisor | rejected` (`backend/app/draft/schema.py:21`). A draft exists only for an exception (`frontend/src/components/inquirySteps.ts:18-37`).
- The inbox list shows two separate badges: "Czeka na przełożonego" from `draft_status` and the outcome badge (`frontend/src/components/Inbox.tsx:271-283`). There is no "new / analysed / ready to send / rejected" state (UX audit `context/audits/ux/2026-11-16-prism-analysis-flow.md:45`). The "awaiting only" filter uses `draft_status` (`Inbox.tsx:178-182`).
- The open inquiry header shows subject, sender and date only (`Inbox.tsx:305-316`).
- `AnalysisPanel` reports `onOutcome` and `onDraftStatus` after every load and change (`AnalysisPanel.tsx:313-314, 334-335, 361-362`), and the inbox updates the list item in place (`Inbox.tsx:113-148`).
- The salesperson's decision buttons are `common.approve` / `draft.editOffer` / `common.reject` whatever the verdict (`ReplyDraftSection.tsx:165-192`); the form's submit is `draft.form.confirmApproval` and its label `draft.form.approveDraft`. The backend sends an approved draft to `awaiting_supervisor` when the verdict in force is `requires_supervisor` (`backend/app/draft/service.py:327-340`). `ReplyDraftView.policy` is that same verdict in force (`frontend/src/api/analysis.ts:432-433`), so the label can follow it.
- After a decision only the rejection is announced (`steps.back.draftRejected` via `stepBackReason`, `inquirySteps.ts:63-78`; this covers the supervisor's rejection too). Approve, edit and the supervisor's approval set no notice (`AnalysisPanel.tsx:417-429`). The status region is rendered conditionally (`AnalysisPanel.tsx:914-925`), and the audit found it empty after "Confirm approval" (`prism-analysis-flow.md:38,166-169`).
- Sign out: the button is `disabled` while the request runs, so focus falls to `<body>`; the label stays "Sign out"; after sign-out focus is not moved (`AppShell.tsx:44-50`, `App.tsx:50-70`, `context/archive/2026-11-16-design-system-i18n-foundation/follow-ups/review-fixes.md:5-9`).
- S-12 and F-03 deferred exactly these items to S-14 (`context/archive/2026-11-16-inquiry-steps/plan.md:37`).

## Desired End State

- Every inbox row shows one status badge: Nowe, Przeanalizowane, Wyjątek, Wymaga uzupełnienia, Czeka na przełożonego, Gotowe do wysłania, Odrzucone (EN: New, Analysed, Exception, Needs input, Awaiting supervisor, Ready to send, Rejected). The mailbox badge stays. The header of the open inquiry shows the same badge next to the subject. Both change immediately after an analysis, a re-run or a decision, without reloading the list.
- When the verdict in force is `requires_supervisor`, the salesperson's primary action reads "Wyślij do przełożonego", its form is labelled accordingly, its submit reads "Potwierdź wysłanie do przełożonego", and a hint says the offer goes to the supervisor for approval. With `no_approval_needed` it stays "Zatwierdź".
- After every decision the status line at the top of the panel says what happened: "Wysłano do przełożonego", "Zatwierdzono — gotowe do wysłania (wysyłka jest symulowana)", "Zapisano zmiany oferty", "Przełożony zatwierdził — gotowe do wysłania". A rejection keeps its S-12 step-back message. Screen readers announce each message.
- While signing out, the button keeps focus, reads "Wylogowywanie…" and is `aria-disabled`. After sign-out the sign-in heading has focus.

### Key Discoveries:

- One rule, in priority order, gives the status (decided in planning): draft `awaiting_supervisor` → awaiting supervisor; `ready_to_send` → ready to send; `rejected` → rejected; else outcome `exception` → exception; `needs_input` → needs input; else analysed when an analysis exists; else new. A draft status outranks the outcome because a draft exists only for an exception. A stale draft keeps its raw status, as the "awaiting only" filter already does.
- `ReplyDraftView.policy` is the verdict the backend's `decide()` will use, including for an edited offer, so the label is honest by construction.
- `stepBackReason` already announces both the salesperson's and the supervisor's rejection; the new notices must not duplicate it.

## What We're NOT Doing

- No status field computed in the API: the backend only adds `analyzed`. The S-15 queue will reuse the frontend rule.
- No status history: after "Wygeneruj ponownie" a rejected inquiry shows its current status (exception), not "rejected".
- No staleness check of the draft on the list (raw `draft_status`, as today).
- No toasts and no sonner dependency; messages use the existing `role="status"` line.
- No change to the supervisor's buttons (Zatwierdź / Odrzuć), to the "awaiting only" filter, or to permissions (S-15).
- No live refresh of the list for changes made in another session.
- No migration and no change to stored JSONB.

## Implementation Approach

The backend gains one boolean on the list and detail responses. A pure frontend function derives the status from `analyzed`, `outcome` and `draft_status`, and both the list and the header use it. The panel's two callbacks are merged into one that reports all three facts, so the list item and the header stay in step. Phase 2 changes labels and notices inside the decision flow, and phase 3 handles the sign-out focus, which is independent.

## Critical Implementation Details

- **Live region must stay mounted**: a `role="status"` element inserted together with its text is often not announced. The notice container in `AnalysisPanel` (`:914`) is rendered always (empty when there is nothing to say, without visual padding when empty), and only its content changes.
- **Notice vs step-back message**: after a decision, set the notice only when `stepBackReason` returns null for that transition; a rejection is already announced by the step-back message.
- **Header facts**: the header reads the facts of the list item with the open id when the list has it, else the detail's own fields (list error or not yet loaded). The panel's callback updates both, so neither shows an old status.

## Phase 1: Inquiry status on the list and in the header

### Overview

Add `analyzed` to the API, derive one status in the frontend, and show it as one badge on each list row and in the open inquiry's header.

### Changes Required:

#### 1. API: analysis exists

**File**: `backend/app/api/inquiries.py`, `backend/tests/test_inquiries_api.py`

**Intent**: Tell the client whether an inquiry has an analysis, so "new" and "analysed" can be told apart.

**Contract**: `InquirySummary.analyzed: bool` (default `False`), inherited by `InquiryDetail`. `_inquiry_rows()` selects an "analysis row exists" expression on the `InquiryAnalysis` join that `with_current_outcome` already adds (no new join); `_with_outcome` sets it. Tests: the field list includes `analyzed`; false without an analysis, true with one (also when the checks are stale and `outcome` is null).

#### 2. Frontend type

**File**: `frontend/src/api/inquiries.ts`

**Intent**: Carry the new field and validate it.

**Contract**: `InquirySummary.analyzed: boolean`; the type guard checks it is a boolean. Update fixtures that build `InquirySummary` (`Inbox.test.tsx`, `kitchen-sink.tsx`, any other).

#### 3. Status rule and labels

**File**: `frontend/src/components/inquiryStatus.ts` (new), `inquiryStatus.test.ts` (new), `pl.json`, `en.json`

**Intent**: One pure function and one badge mapping used wherever a status is shown.

**Contract**: `type InquiryStatus = 'new' | 'analyzed' | 'exception' | 'needs_input' | 'awaiting_supervisor' | 'ready_to_send' | 'rejected'`; `inquiryStatus(facts: { analyzed: boolean; outcome: Outcome | null; draft_status: ReplyDraftStatus | null }): InquiryStatus` implementing the priority order in Key Discoveries. A `STATUS_VARIANT` record maps each status to an existing `Badge` variant (text always present, colour never alone; e.g. warning for awaiting supervisor, destructive-outline for exception and rejected, warning-outline for needs input, success for ready to send, success-outline for analysed, outline for new). New keys `inquiryStatus.<status>` in both locales (PL: Nowe, Przeanalizowane, Wyjątek, Wymaga uzupełnienia, Czeka na przełożonego, Gotowe do wysłania, Odrzucone; EN: New, Analysed, Exception, Needs input, Awaiting supervisor, Ready to send, Rejected) and `inquiryStatus.label` ("Status" / "Status") for an sr-only prefix. Tests cover every branch, including `draft` status with an exception, stale checks with an analysis (analysed), and awaiting supervisor outranking exception.

#### 4. Inbox list and header

**File**: `frontend/src/components/Inbox.tsx`, `Inbox.test.tsx`

**Intent**: Replace the awaiting and outcome badges with the one status badge, and show the same badge in the open inquiry's header.

**Contract**: each row renders the mailbox badge (unchanged) and one status badge with an sr-only "Status:" prefix. The header `<article>` shows the badge next to the subject, using the list item's facts when present, else the detail's. `inbox.badgeAwaiting` and `outcome.*` are removed from both locales if nothing else uses them (grep first). Tests: one badge per row with the expected text for each of the seven statuses; the header badge matches the row; the "awaiting only" filter still counts and filters as before.

#### 5. One callback for the facts

**File**: `frontend/src/components/AnalysisPanel.tsx`, `Inbox.tsx`, `AnalysisPanel.test.tsx`

**Intent**: Report all status facts together so the list item and the header change at once.

**Contract**: `onOutcome` and `onDraftStatus` are replaced by `onStatusFacts?: (inquiryId: number, facts: { analyzed: boolean; outcome: Outcome | null; draft_status: ReplyDraftStatus | null }) => void`, called at the three existing call sites with `analyzed: analysis !== null`. `Inbox` updates the list item and the detail in place (no refetch). Existing tests of the two callbacks are adapted.

#### 6. Kitchen sink

**File**: `frontend/src/kitchen-sink.tsx`

**Intent**: Show all seven statuses on the list and one in the header.

**Contract**: the `INQUIRIES` fixture covers the seven statuses (with `analyzed` set); `NONE_AWAITING` keeps working. Not added to `build.rollupOptions.input`.

### Success Criteria:

#### Automated Verification:

- Backend list API tests pass: `uv run pytest tests/test_inquiries_api.py` (from `backend/`)
- Backend lint, format and types pass: `uv run ruff check . && uv run ruff format --check . && uv run mypy app tests` (from `backend/`)
- Status rule tests pass: `npm test -- inquiryStatus` (from `frontend/`)
- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)
- The AGENTS.md colour scan prints nothing

#### Manual Verification:

- Kitchen sink, PL and EN (DOM/ARIA first): every row has exactly one status badge with the right text, the open inquiry's header shows the same status, and the badges are legible in light and dark mode

**Implementation Note**: After automated verification passes, pause for manual confirmation before the next phase.

---

## Phase 2: Honest decision label and a message after every decision

### Overview

Name the salesperson's action after what it does, and say what happened after every decision in a status line that screen readers announce.

### Changes Required:

#### 1. "Send to supervisor" label

**File**: `frontend/src/components/ReplyDraftSection.tsx`, `ReplyDraftSection.test.tsx`, `pl.json`, `en.json`

**Intent**: When `draft.policy?.outcome === 'requires_supervisor'`, the approve action, its form and its submit say that the offer goes to the supervisor; otherwise they stay as today.

**Contract**: new keys `draft.sendToSupervisor` ("Wyślij do przełożonego" / "Send to supervisor"), `draft.form.sendToSupervisorDraft` (form label, "Wyślij szkic do przełożonego" / "Send draft to supervisor"), `draft.form.confirmSendToSupervisor` ("Potwierdź wysłanie do przełożonego" / "Confirm sending to supervisor"), and `draft.sendToSupervisorHint` ("Polityka wymaga akceptacji przełożonego — oferta trafi do niego do zatwierdzenia." / "The policy requires supervisor approval — the offer goes to the supervisor for approval."), shown next to the decision buttons in that case. The action value sent to the API stays `approve`. With `policy` null the label stays "Approve" (the backend answers 409 "Policy verdict missing"). Tests: button names are `['Send to supervisor','Edit offer','Reject']` with `requires_supervisor` and `['Approve','Edit offer','Reject']` with `no_approval_needed`; the form and submit names follow; the hint is present only in the first case.

#### 2. Messages after decisions

**File**: `frontend/src/components/AnalysisPanel.tsx`, `AnalysisPanel.test.tsx`, `pl.json`, `en.json`

**Intent**: After every successful decision, show and announce what happened.

**Contract**: `NoticeKey` gains `decision.sentToSupervisor` ("Wysłano do przełożonego." / "Sent to supervisor."), `decision.approved` ("Zatwierdzono — gotowe do wysłania (wysyłka jest symulowana)." / "Approved — ready to send (sending is simulated)."), `decision.edited` ("Zapisano zmiany oferty." / "Offer changes saved."), `decision.supervisorApproved` ("Przełożony zatwierdził — gotowe do wysłania." / "Approved by the supervisor — ready to send."). `decideOnReplyDraft` sets the notice from the action and the resulting draft status (sales approve → `awaiting_supervisor` gives sentToSupervisor, `ready_to_send` gives approved; edit gives edited; supervisor approve gives supervisorApproved), and sets none when `stepBackReason` announces the transition (rejections). The `role="status"` container stays mounted (see Critical Implementation Details). Tests: each decision yields its message in the status region; a rejection yields only the step-back message; a 409 still yields `analysis.draftReloaded`.

#### 3. Kitchen sink

**File**: `frontend/src/kitchen-sink.tsx`

**Intent**: Show the Akceptacja step with a `requires_supervisor` verdict, so the label and hint can be checked.

**Contract**: one panel case/cell with a `draft` status draft whose policy is `requires_supervisor` (reuse an existing fixture if one exists).

### Success Criteria:

#### Automated Verification:

- Decision tests pass: `npm test -- ReplyDraftSection AnalysisPanel` (from `frontend/`)
- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)
- The AGENTS.md colour scan prints nothing

#### Manual Verification:

- Kitchen sink, PL and EN: with `requires_supervisor` the action reads "Wyślij do przełożonego" with the hint; with `no_approval_needed` it reads "Zatwierdź"
- In the real app with the backend: approving a `requires_supervisor` draft shows "Wysłano do przełożonego" at the top of the panel and the status badge changes to "Czeka na przełożonego" on the list and in the header; the status region's text is present in the accessibility tree

**Implementation Note**: After automated verification passes, pause for manual confirmation before the next phase.

---

## Phase 3: Focus while signing out (F6)

### Overview

Keep focus on Sign out while it runs, say that it is running, and move focus to the sign-in heading afterwards.

### Changes Required:

#### 1. Sign-out button

**File**: `frontend/src/components/AppShell.tsx`, `pl.json`, `en.json`, `AppShell` or `App` tests

**Intent**: The in-progress button keeps keyboard focus and tells what is happening.

**Contract**: while `signingOut`, the button has `aria-disabled="true"` instead of `disabled`, ignores clicks, and reads `inbox.signingOut` ("Wylogowywanie…" / "Signing out…").

#### 2. Focus after sign-out

**File**: `frontend/src/App.tsx`, `frontend/src/components/LoginForm.tsx`, `App.test.tsx`

**Intent**: After the app goes from authenticated to anonymous, the sign-in heading receives focus.

**Contract**: `LoginForm` gets an optional `focusHeading` prop; its `<h2>` has `tabIndex={-1}` and is focused on mount when the prop is set. `App` passes it when the anonymous state follows an authenticated one (sign-out or session loss), not on the first load. Tests: after sign-out, `document.activeElement` is the sign-in heading; during sign-out the button stays focused with `aria-disabled="true"` and the "Signing out…" name; a second click does not call logout twice.

### Success Criteria:

#### Automated Verification:

- Frontend tests pass: `npm test` (from `frontend/`)
- Type checking passes: `npm run typecheck` (from `frontend/`)
- Lint passes: `npm run lint` (from `frontend/`)
- Build passes: `npm run build` (from `frontend/`)
- The AGENTS.md colour scan prints nothing

#### Manual Verification:

- In the browser with the keyboard only: Tab to Sign out, press Enter; focus stays on the button while it reads "Wylogowywanie…", then lands on the sign-in heading (check `document.activeElement`)

**Implementation Note**: After automated verification passes, pause for manual confirmation.

---

## Testing Strategy

### Unit Tests:

- `inquiryStatus`: all seven results and the priority between draft status and outcome.
- `Inbox`: one badge per row, header badge, in-place update via `onStatusFacts`, the awaiting filter unchanged.
- `ReplyDraftSection`: label, form name, submit and hint by verdict.
- `AnalysisPanel`: notice after each decision kind, none duplicated for rejections, region always mounted.
- `App` / `AppShell`: sign-out focus and the in-progress button.
- Backend: `analyzed` in the list and detail responses.

### Manual Testing Steps:

1. Kitchen sink: inbox rows with all seven statuses, header badge, PL/EN, light/dark.
2. Kitchen sink: Akceptacja with `requires_supervisor` and with `no_approval_needed`.
3. Real app: analyse a new inquiry (New → Analysed or Exception), approve a `requires_supervisor` draft (message, badge), approve it as the supervisor (message, Ready to send).
4. Keyboard-only sign-out.

## Performance Considerations

One extra boolean per list row from a join the query already makes. No new requests.

## Migration Notes

None. No schema or JSONB change; `analyzed` is derived at read time (lessons.md JSONB rule does not apply).

## References

- Roadmap: `context/foundation/roadmap.md` (S-14)
- PRD: `context/foundation/prd.md` FR-018, FR-011, US-02
- UX audit: `context/audits/ux/2026-11-16-prism-analysis-flow.md:38,45,112,166-169`
- Deferrals: `context/archive/2026-11-16-inquiry-steps/plan.md:37`, `context/archive/2026-11-16-design-system-i18n-foundation/follow-ups/review-fixes.md:5-9`
- Decision logic: `backend/app/draft/service.py:327-340`
- Step derivation: `frontend/src/components/inquirySteps.ts:18-78`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Inquiry status on the list and in the header

#### Automated

- [x] 1.1 Backend list API tests pass — 1391cf8
- [x] 1.2 Backend lint, format and types pass — 1391cf8
- [x] 1.3 Status rule tests pass — 1391cf8
- [x] 1.4 Frontend tests pass — 1391cf8
- [x] 1.5 Type checking passes — 1391cf8
- [x] 1.6 Lint passes — 1391cf8
- [x] 1.7 AGENTS.md colour scan prints nothing — 1391cf8

#### Manual

- [x] 1.8 Kitchen sink PL/EN: one status badge per row, matching header badge, legible in light and dark — 1391cf8

### Phase 2: Honest decision label and a message after every decision

#### Automated

- [x] 2.1 Decision tests pass — 10fe0cf
- [x] 2.2 Frontend tests pass — 10fe0cf
- [x] 2.3 Type checking passes — 10fe0cf
- [x] 2.4 Lint passes — 10fe0cf
- [x] 2.5 AGENTS.md colour scan prints nothing — 10fe0cf

#### Manual

- [x] 2.6 Kitchen sink PL/EN: "Wyślij do przełożonego" with hint for requires_supervisor, "Zatwierdź" otherwise — 10fe0cf
- [ ] 2.7 Real app: approving a requires_supervisor draft shows the message and updates the badge on list and header

### Phase 3: Focus while signing out (F6)

#### Automated

- [x] 3.1 Frontend tests pass — c0b0326
- [x] 3.2 Type checking passes — c0b0326
- [x] 3.3 Lint passes — c0b0326
- [x] 3.4 Build passes — c0b0326
- [x] 3.5 AGENTS.md colour scan prints nothing — c0b0326

#### Manual

- [x] 3.6 Keyboard-only sign-out: focus stays on the button while "Wylogowywanie…", then lands on the sign-in heading — c0b0326
