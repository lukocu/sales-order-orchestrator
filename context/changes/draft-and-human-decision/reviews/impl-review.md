<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Draft and human decision (S-07)

- **Plan**: context/changes/draft-and-human-decision/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4
- **Date**: 2026-11-12
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 5 warnings, 3 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Success criteria: `check.sh` 758 passed; frontend lint/typecheck/test (185)/build pass; image builds; manual 1.4, 2.3, 3.3, 4.7 (local) and 4.8 (Render: health `0012_drafts_decisions`, ACME draft `text_source=model`, Approve → `ready_to_send`) verified in this session. Plan-review fixes F1–F5 all present.

## Findings

### F1 — Edited offer keeps a verdict computed under old thresholds

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/draft/service.py:360-362, 782-783
- **Detail**: For an edited offer `get_draft_view` sets `policy_stale=False` and `_policy_in_force` returns the verdict stored at edit time. When `policy_rules` thresholds change after the edit, `POST /policy` re-evaluates only the stage verdict; Approve of the edited draft still uses the old verdict and can give `ready_to_send` under thresholds that would now require a supervisor. Upstream data changes are covered (new recommendation → DraftStale); threshold changes are not.
- **Fix A ⭐ Recommended**: In `decide`, re-evaluate an edited offer with `load_thresholds` under the same lock and use that verdict (store it in the snapshot).
  - Strength: The verdict in force always reflects current rules; one code path, no new state.
  - Tradeoff: The verdict shown in the UI before Approve can differ from the one applied, unless the view also re-evaluates.
  - Confidence: HIGH — `evaluate` is pure and cheap; inputs are rebuilt by `offer_policy_inputs`.
  - Blind spot: Whether the view should re-evaluate too (to keep display = decision).
- **Fix B**: Store a thresholds fingerprint in the draft result and mark the edited draft stale when it no longer matches.
  - Strength: The UI shows the staleness explicitly; forces a re-edit.
  - Tradeoff: New JSONB field (optional + default per lesson) and a stale path the user must resolve by re-editing.
  - Confidence: MED — more moving parts.
  - Blind spot: How the user clears the stale state without Regenerate losing the edit.
- **Decision**: FIXED — Fixed via Fix A (re-evaluated in decide and the view; test_edited_offer_is_judged_by_the_current_thresholds)

### F2 — Digit-only check lets URLs, emails and number words through

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/draft/drafter.py:174-182 (`validate_text`), backend/app/draft/service.py:522-532 (`DraftFacts`)
- **Detail**: `DraftFacts` passes customer-controlled text (subject, sender name, LLM justification) to the model. `validate_text` only rejects digits, empty and over-long paragraphs, so a prompt injection could produce `https://pay.example/x`, `x@y.pl` or "rabat dziesięć procent" in the intro/closing — terms the code never computed (FR-010 spirit). The human approval step reduces but does not remove the risk.
- **Fix**: Extend `validate_text` to reject `://`, `www.`, `@`, `%`, `procent` and a short list of Polish number words, with a new fallback error code; add tests.
  - Strength: Same mechanism as the digit rule; fallback text already exists.
  - Tradeoff: More fallbacks on Groq if the model uses such words innocently.
  - Confidence: HIGH — small pure function with tests in `test_draft_llm.py`.
  - Blind spot: Completeness of the number-word list.
- **Decision**: FIXED — validate_text also rejects number words, `%`, links and e-mail addresses (codes text_has_number_word, text_has_link); tests in test_draft_llm.py

### F3 — Edit and Reject accepted on a draft whose stage verdict is stale

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/draft/service.py:735-771 (`_locked_draft`)
- **Detail**: Plan: Edit/Decide only for non-stale drafts. `_locked_draft` checks status and recommendation currency but not the stage verdict's staleness, which `get_draft_view` does use for `stale`. Via the API, Edit/Reject succeed on a draft the UI shows as stale (Approve is safe: PolicyMissing).
- **Fix**: For an unedited offer, raise `DraftStale` in `_locked_draft` when the stage verdict is missing or of another `recommended_at`/stale, matching `get_draft_view`.
- **Decision**: FIXED — Edit and Reject raise DraftStale without a current verdict for an unedited offer (Approve keeps PolicyMissing); test_edit_or_reject_without_a_current_verdict_is_stale

### F4 — Decision history row silently dropped when its snapshot is unreadable

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/draft/service.py:412-420
- **Detail**: `DecisionSnapshot` (extra=forbid) embeds policy/recommendation types. A future schema change there that skips the JSONB lesson makes `get_decision_views` `continue`, hiding append-only audit rows without error.
- **Fix**: Keep the row with `snapshot=None` (optional field in `DecisionView`) instead of dropping it, and extend the lessons entry to name `inquiry_drafts.result` and `inquiry_draft_decisions.snapshot`.
- **Decision**: FIXED — unreadable snapshots stay in the history with `snapshot=None` (UI: "Details unavailable"); JSONB lesson extended to the draft tables

### F5 — Edited offer's policy evaluation is not traced

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/draft/service.py:285-288
- **Detail**: `edit_draft` calls `evaluate(...)` without `run(...)`/`traced.step("rules", kind="deterministic")`, unlike `policy.service.run_policy`. The verdict that sends an edited offer to the supervisor has no trace run.
- **Fix**: Wrap the evaluation in a traced run like `run_policy`.
- **Decision**: FIXED — edit evaluation wrapped in run(...)/traced.step("rules"); test_edit_traces_its_policy_evaluation

### F6 — Regenerate offered for a decided draft with a stale verdict

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: frontend/src/components/ReplyDraftSection.tsx:143-144; backend/app/draft/service.py:232-237
- **Detail**: The UI shows Regenerate for any stale draft; the backend refuses `ready_to_send`/`awaiting_supervisor` drafts of the current recommendation with 409 "Draft already decided".
- **Fix**: Show Regenerate for a stale draft only when its status is `draft` or `rejected`.
- **Decision**: FIXED — Regenerate for a stale draft only in status draft; frontend test

### F7 — New draft endpoints lack the catch-all JSON 500

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/analysis.py:425-483
- **Detail**: `edit` and `decide_draft` have no `except Exception` → logged JSON 500 like the other handlers; unexpected errors return Starlette's default 500.
- **Fix**: Add the same catch-all branch the other handlers use.
- **Decision**: FIXED — catch-all 500 "Decision failed" (_decision_failed) on both endpoints; test_unexpected_error_is_a_logged_500

### F8 — Plan lists test_policy_service.py changes that were not needed

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: N/A (plan Phase 2 §3)
- **Detail**: The drafter hook is called by callers of `policy_after_recommendation`/`run_policy`, not inside them, so `test_policy_service.py:363,386` needed no drafter argument. Sound adaptation; the plan line is outdated.
- **Fix**: No code change; note the adaptation (or skip).
- **Decision**: ACCEPTED — sound adaptation, the plan line is outdated
