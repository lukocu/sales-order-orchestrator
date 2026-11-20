<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Kolejka przełożonego (S-15)

- **Plan**: context/changes/supervisor-queue/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-20
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 6 warnings, 4 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | WARNING |

Gates run on 2026-11-20 from origin/main (d1d2deb):

- Frontend: `npm run lint`, `typecheck`, `npm test`, `build` pass (only the known >500 kB chunk warning).
- Backend: `docker compose run --rm backend sh check.sh` gave 1086 passed, 6 failed, all in `tests/test_supervisor_api.py`. Cause: the compose `db` is the shared dev database and still holds a pre-existing `awaiting_supervisor` draft (inquiry 3, from 2026-11-16), so the queue tests that assume an empty queue count it (`total` 2 vs 1, `items[0]` is the foreign row). Not a code defect; CI on a fresh database was green for the merged PRs. The tests depend on a clean database.
- Plan Progress: rows 1.1-1.4 and 3.1-3.9 carry no SHA suffix (only phase 2 does). Manual rows 3.6-3.9 are ticked; evidence is in change.md Notes only.

## Findings

### F1 — Queue refresh can stay stuck after the effect re-runs

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/supervisorQueue.tsx:59-105
- **Detail**: The effect cleanup bumps `generation` and aborts the controller but never clears `request.current`. The aborted request's `.finally` skips clearing it (generation mismatch), so a later non-force `refresh()` (visibilitychange, route mount) returns the dead promise and the queue stays `loading` or never updates until the user presses Refresh. `remove()` (l.71-75) aborts an in-flight request without refetching, leaving the nav badge unloaded when state is still `loading`.
- **Fix**: Null `request.current` and `controller.current` in the cleanup; have `remove()` start a refetch when it aborts one.
  - Strength: Small change in one file, restores "concurrent triggers share one request" without sharing a dead one.
  - Tradeoff: Needs a test that re-runs the effect (user change) and then triggers a non-force refresh.
  - Confidence: MED — found by reading, not reproduced.
  - Blind spot: Whether the provider effect re-runs in practice outside a user change.
- **Decision**: FIXED — queue cleanup now clears the request/controller refs and remove() refetches when it aborted a read

### F2 — Review view: late writes and form state leak across inquiries

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/SupervisorReview.tsx:36-42, 111-131; frontend/src/components/SupervisorRoutes.tsx
- **Detail**: (a) The post-decision refetch (l.118) and the 409 path `load(loadKey)` (l.131) have no abort signal and write state for the old key after the user navigated to another inquiry; the new inquiry's view then shows loading forever because no effect refetches. (b) `action`, `reason`, `requiresReview` and error state are not reset when `inquiryId` changes (no `key={id}`), so a comment typed for inquiry A and a preselected Approve carry over to B and are sent with B's token.
- **Fix**: Render `<SupervisorReview key={id} …/>` and tie both fetches to an abort signal or an `active` flag cleared on `inquiryId` change.
  - Strength: `key` removes the whole class of carried state in one line.
  - Tradeoff: Remount drops the open `<details>` state on navigation (acceptable).
  - Confidence: HIGH — the route renders the component without a key.
  - Blind spot: Not reproduced in a browser; link navigation between two approval URLs needs checking.
- **Decision**: FIXED — SupervisorReview is keyed by inquiry id (state and form reset on navigation, no late write into another case)

### F3 — A 401 on the queue drops the user silently

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/App.tsx:122-127
- **Detail**: `SupervisorQueueProvider` receives `handleSignedOut`; every other consumer uses `session.onUnauthorized`, which also shows the "session expired" message and keeps the URL.
- **Fix**: Pass `session.onUnauthorized` to the provider.
- **Decision**: DISMISSED — false positive: App.tsx:135 already passes handleUnauthorized (the session-expired handler) to the provider

### F4 — A corrupt pending draft can still break reject and the whole queue

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/draft/service.py:407-421; backend/app/inquiries/supervisor_queue.py:151-159
- **Detail**: `_reject_pending` catches only `DraftStale` and `ValidationError`; any `TypeError`/`KeyError`/`AttributeError` from `_policy_in_force` on malformed data gives a 500 and the draft stays stuck. `_policy` in the queue projection catches only `ValidationError`, so one malformed row can 500 the whole queue, against the plan ("błąd walidacji jednego JSONB nie wywraca całej kolejki").
- **Fix**: Wrap the per-item projection in `get_queue` in try/except (log, emit the item as `unavailable`) and broaden the data-interpretation catch in `_reject_pending`.
  - Strength: Guarantees the plan's "unreadable drafts stay visible and rejectable".
  - Tradeoff: A broad catch can hide real bugs; log with the inquiry id.
  - Confidence: MED — read, not reproduced with a malformed row.
  - Blind spot: Which exact exception types real bad data raises.
- **Decision**: FIXED — get_queue/get_review project each draft through a guarded _project (unreadable -> unavailable); _reject_pending also recovers from KeyError/TypeError/AttributeError/ValueError; regression test added

### F5 — Open review is not refreshed when the tab becomes visible

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/components/SupervisorReview.tsx (no listener); plan Phase 3 §1
- **Detail**: The plan says that on returning to the tab the open review is refreshed too. Only the provider listens to `visibilitychange`; the review keeps a stale token and offers a decision that then returns 409.
- **Fix**: Refresh the review on `visibilitychange` (reusing the load function with abort) and cover it in a test.
- **Decision**: FIXED — the open review re-reads on visibilitychange, flags a changed token and drops a no longer allowed action; test added

### F6 — Lock on the regular inquiry view is a coarse fieldset

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Plan Adherence
- **Location**: frontend/src/components/AnalysisPanel.tsx:944-994
- **Detail**: The plan lists seven section components and `InquiryStepper` as files to change; none was touched. The lock is a single `<fieldset disabled>` around all steps. It also disables the load-error Retry button (inside the fieldset), does not cover links or non-native controls, and `RunInspector` renders outside it. The API enforces the lock, so this is a UX/defence-in-depth gap, not an authorization hole.
- **Fix A ⭐ Recommended**: Keep the fieldset, move loading/error/Retry outside it, and add a test that no link or non-native control mutates
  - Strength: Minimal; keeps the single point of control that works today.
  - Tradeoff: New section controls added later must remember to be native.
  - Confidence: MED — stepper placement inside the fieldset not checked.
  - Blind spot: Whether step navigation is wrongly disabled for the read-only context view.
- **Fix B**: Pass `readOnly` into each section as the plan described
  - Strength: Explicit per-control behaviour, matches the plan.
  - Tradeoff: Touches eight files for no behavioural gain today.
  - Confidence: MED — larger diff, more regression surface.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A — loading and load-error (Retry) moved outside the fieldset; lock test updated. Stepper navigation inside the fieldset left as is

### F7 — Queue projection runs many queries per draft

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/inquiries/supervisor_queue.py:162-262
- **Detail**: Inquiries, analyses and decisions are batch-loaded, but each draft then runs `_is_current` twice plus policy lookups (about 8-10 queries) and `_history` resolves users per decision row. The queue is unpaginated and refetched on every tab focus. Fine at the stated scale (a few people).
- **Fix**: Compute `is_current` once per draft and pass it down; pre-load users in one query. Defer unless the queue grows.
- **Decision**: SKIPPED — scale is a few people; revisit if the queue grows

### F8 — Mutation 409s from analysis routes carry no code

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/analysis.py (ten `except MutationConflict` blocks)
- **Detail**: They raise a plain `HTTPException(409, detail=str(error))`, while `supervisor.py` uses `ApiHTTPException` with a code. The frontend maps the English text to codes (`api/client.ts:17-19`), so it works, but the contract depends on message strings and the block is repeated ten times.
- **Fix**: Give the two conflict classes distinct codes and use one helper for the mapping.
- **Decision**: DISMISSED — false positive: analysis.py already maps conflicts through _mutation_conflict with AWAITING_SUPERVISOR / INQUIRY_CHANGED codes

### F9 — Focus and live region behaviour in the review

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/SupervisorReview.tsx:92-95, 191-195
- **Detail**: The result heading takes focus whenever `review_state === 'not_awaiting'`, including a plain deep-link visit (focus stealing). The `role="status"` paragraph is mounted together with its text, which many screen readers do not announce.
- **Fix**: Focus only after a decision made in this view; render the status region persistently and fill it afterwards.
- **Decision**: FIXED — focus moves only after a decision made in the view (layout effect), status region is always mounted; test added

### F10 — Minor drift from the planned review and list content

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/components/SupervisorQueue.tsx:76-85; SupervisorReview.tsx:239-247, ~265
- **Detail**: (a) List rows show the sender, never the customer (`QueueItem` has no customer field; the plan says customer when available). (b) The decision form is inline, not extracted from `ReplyDraftSection`. (c) The collapsed context prints `JSON.stringify(checks)` raw in the UI, untranslated.
- **Fix**: Add the customer to the queue projection and render checks through the existing `ChecksSection` (or drop the dump); leave (b) as an accepted deviation.
- **Decision**: FIXED — customer in the queue projection and list rows, raw checks JSON removed from the context block; inline decision form accepted
