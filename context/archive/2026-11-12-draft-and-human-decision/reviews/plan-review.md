<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Draft and human decision (S-07)

- **Plan**: context/changes/draft-and-human-decision/plan.md
- **Mode**: Deep
- **Date**: 2026-11-12
- **Verdict**: REVISE → SOUND after triage (all 5 findings fixed in plan)
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | WARNING |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 9/9 paths ✓, 6/6 symbols ✓, brief↔plan ✓ (Progress 4/4 phases, 18/18 rows)

## Findings

### F1 — A no-op edit can turn a failing discount rule into a pass

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Phase 1 §3 „Rabat w ofercie dla polityki”, Critical Implementation Details
- **Detail**: For an unedited offer the plan uses the S-06 stage verdict, whose discount rule judges the customer's request (Delta: requested 25% → fail, `rules.py:65-110`). For an edited offer, `offered_discount_percent` replaces the request, so a discount is judged only from the offered prices. An edit that changes nothing (or only the quantity) evaluates the standard discount, so the discount rule passes. For an inquiry where only the discount fails, Approve then gives READY TO SEND without a supervisor. That breaks the roadmap risk „edycja nie może obejść polityki”.
- **Fix A ⭐ Recommended**: When `offered_discount_percent` is set, the discount rule fails if either the S-06 value (request or standard) or the offered discount exceeds the maximum, and reports the larger value.
  - Strength: A no-op edit gives the same verdict as the stage verdict, and lowering a price can only make it worse. S-06 is unchanged when the field is `None`.
  - Tradeoff: A rep cannot clear a customer's discount request by offering the standard price. That still goes to the supervisor, which matches S-06.
  - Confidence: HIGH — `evaluate_discount` is a small pure function with existing tests in `test_policy_core.py`.
  - Blind spot: Whether the business wants „we offered less than asked” to need a supervisor was not confirmed.
- **Fix B**: Evaluate every draft offer (edited or not) with the offered discount only, and stop using the stage verdict for Approve.
  - Strength: One consistent rule: policy judges what goes out in the reply.
  - Tradeoff: Two different verdicts on screen for the same unedited offer (Delta stage: discount fail; draft: pass), which is confusing and changes the meaning of S-06.
  - Confidence: MED — the semantics are defensible, but they conflict with the S-06 decision recorded in the archive.
  - Blind spot: Effect on the S-10 evaluation labels.
- **Decision**: FIXED — Fixed via Fix A

### F2 — Store of an auto-generated draft can overwrite an edit or decision

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 2 §2 `generate_draft` / `draft_after_policy`
- **Detail**: The plan checks „szkic dla bieżącego recommended_at istnieje → nic” before the LLM call, but the store happens after the call (up to two attempts). The established store pattern (`policy/service.py:233-250`, `recommendation/service.py:404-416`) re-checks only the inputs under `lock_analysis`, never the target row. Without an extra guard, a draft edited or decided during the LLM call would be overwritten back to `draft`, wiping the status of a recorded decision.
- **Fix**: In the store under `lock_analysis`, re-check that the recommendation is still current with the same `recommended_at`. Skip the write when a draft row for that `recommended_at` already exists, unless the call is an explicit `regenerate_draft` that read that row's `updated_at` and finds it unchanged.
- **Decision**: FIXED — Fixed in plan

### F3 — Hook threading misses call sites

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 §3 „Podpięcie w łańcuchu i API”
- **Detail**: Phase 2 §3 names `recommendation/service.py` and `parsing/service.py`. The `drafter` parameter also has to pass through `orchestration/service.py:140`, which calls `recommend_after_orchestration`. Direct test calls that need a drafter argument:
  - `test_policy_service.py:363,386`
  - `test_recommendation_service.py:257`
  - `test_orchestration_service.py:570`
  - `test_parsing_models.py:62`

  The 6 API handlers, `api/analysis.py:158-296`, also need it. HTTP tests are covered by a `get_drafter` override in conftest.
- **Fix**: List these files in Phase 2 §3 and add `tests/test_orchestration_service.py tests/test_parsing_models.py` to the 2.2 pytest command.
- **Decision**: FIXED — Fixed in plan

### F4 — Decision history hidden in UI once the inquiry leaves the exception path

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: End-State Alignment
- **Location**: Phase 4 §2
- **Detail**: `DraftSection` sits inside the `checks.outcome === 'exception'` branch of `ChecksSection.tsx:333-364`. After a correction that makes the inquiry standard, `AnalysisView.decisions` still holds the history, but the UI no longer shows it.
- **Fix**: Render the decision history as its own block in `AnalysisPanel`, outside the exception guard, whenever `decisions` is non-empty.
- **Decision**: FIXED — Fixed in plan

### F5 — Frontend name clash with `Draft`

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 4 §1–2
- **Detail**: `AnalysisPanel.tsx:110` already defines a local `Draft` type for the correction form. New types `DraftView`/`DraftStatus` are fine, but a component state named `draft` would be ambiguous.
- **Fix**: Name the frontend types and state `ReplyDraft…` / `replyDraft`.
- **Decision**: FIXED — Fixed in plan
