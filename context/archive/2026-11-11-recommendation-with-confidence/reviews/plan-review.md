<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Rekomendacja z uzasadnieniem i pewnością

- **Plan**: context/changes/recommendation-with-confidence/plan.md
- **Mode**: Deep
- **Date**: 2026-11-11
- **Verdict**: REVISE → SOUND (after triage)
- **Findings**: 1 critical, 2 warnings, 1 observation

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | FAIL    |

## Grounding

7/8 paths ✓ (tests/test_parsing_service.py ✗), 6/6 symbols ✓, seed ✓ (ACME 25,51%, Omega 23,75%, Delta 14,29% recomputed from 0006/0007), brief↔plan ✓

## Findings

### F1 — Phase 3 test command points at a file that does not exist

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 — Success Criteria (row 3.2)
- **Detail**: The command runs `tests/test_parsing_service.py`, which does not exist, so pytest fails on the path before any test runs. The chain is tested by `test_parsing_models.py` (direct calls) and by `test_analysis_api.py` and `test_orchestration_api.py` (through the API).
- **Fix**: Use `tests/test_recommendation_service.py tests/test_orchestration_service.py tests/test_parsing_models.py tests/test_orchestration_api.py tests/test_analysis_api.py`.
- **Decision**: FIXED (Fix in plan)

### F2 — task_failed / not_checked risks have no stated scope

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 2 — confidence.py
- **Detail**:
  - The plan does not say which options receive `task_failed:<cap>` and `not_checked:<cap>`.
  - If they go on every option, an LLM planner that skips `supplier-availability` for ACME puts a supplier risk on stock+ABC-110, an option that uses no supplier. That option drops from HIGH to MEDIUM.
  - The same applies to `customer-history`, which only matters for substitutes.
  - Bands would then depend on which capabilities the planner chose to run, not on the option's own risk.
- **Fix**: Scope these risks to the options that use the capability:
  - `substitute-*` and `customer-history` apply to options with a substitute.
  - `supplier-availability` applies to options with a supplier.
  - A capability the option does not use becomes an info signal `alternative_not_checked:<cap>`, which does not lower the band.
  - Strength: The band describes the risk of this option, and the fake and LLM planners give the same band for ACME.
  - Tradeoff: One more signal kind, plus a capability-to-source mapping in confidence.py.
  - Confidence: HIGH — the planner can skip capabilities (planning.py:165-205).
  - Blind spot: The UI must show info signals, so that a skipped check stays visible.
- **Decision**: FIXED (Fix in plan)

### F3 — Deleting the recommendation row is not under the lock

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 3 — recommend_after_orchestration
- **Detail**:
  - The plan says the row is deleted when there is nothing to recommend, but gives no lock and no condition.
  - Race: run A, on an older version, decides to delete. Meanwhile run B stores a fresh orchestration and recommendation. A's delete then removes B's correct row.
  - `_store` and `_drop_unless_exception` (orchestration/service.py:417-438) already guard against this by acting under `_lock_analysis`.
- **Fix**: Delete under `_lock_analysis`, and only in either of these cases:
  - the row's pins (`analysis_version`, `checks_checked_at`, `orchestrated_at`) differ from the current values;
  - the current orchestration is failed or missing.
  - Strength: Uses the same pattern as `_store` and `_drop_unless_exception`.
  - Tradeoff: About a dozen more lines and one race test.
  - Confidence: HIGH — this mirrors F1 from the S-04 review.
  - Blind spot: None significant.
- **Decision**: FIXED (Fix in plan)

### F4 — The strict schema could constrain option_id and cited_signals

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 4 — llm_recommender.py
- **Detail**: `chat_json` takes its payload per call (llm/client.py:68), and the planner already uses an enum (llm_planner.py:104). The recommender schema can do the same: `option_id` as an enum of this request's option ids, and `cited_signals` items as an enum of the union of signal codes.
- **Fix**: Build the schema per request with these enums, and keep `validate_choice` as the second line of defence.
- **Decision**: FIXED (Fix in plan)
