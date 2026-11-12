<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Werdykt polityki

- **Plan**: context/changes/policy-verdict/plan.md
- **Mode**: Deep
- **Date**: 2026-11-11
- **Verdict**: SOUND
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 5/5 paths ✓, 6/6 symbols ✓ (`lock_analysis`, `CENT`, `HUNDRED`, `get_recommendation_view`, `RunSummary`, `_view`), brief↔plan ✓

The code confirms the following:

- Fake choices and numbers for ACME, Omega and Delta: `test_recommendation_core.py:251-289` and `test_recommendation_service.py:151-175`.
- The test database is migrated with Alembic (`conftest.py:88-91`), so the seed rows in `policy_rules` will be present.
- The checks cover a single line per inquiry (`checks/schema.py:84-94`).
- No seed inquiry uses `target_price`.

## Findings

### F1 — Werdykt może powstać dla nieaktualnej rekomendacji

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Faza 2 §1–§2 (run_policy, NothingToEvaluate, PolicyView.stale)
- **Detail**:
  - `current_checks` (`checks/service.py:81`) is pinned only by `analysis_version`.
  - The plan never says what happens when `checks.checked_at` differs from the recommendation's pin.
  - `NothingToEvaluate` checks only `status` and `choice`.
  - `RecommendationView.stale` uses three pins (`recommendation/service.py:184-202`).
  - So when the recommender throws an unexpected exception, the old row stays in place and the policy evaluates it with `stale = False`.
- **Fix**:
  - Change to the plan:
    - `NothingToEvaluate` also fires when the checks are missing or when `checks.checked_at != rec.checks_checked_at`.
    - In `_view`, `policy.stale |= recommendation.stale`.
    - Add a test: a stale recommendation gives a stale verdict, and `POST /policy` returns 409.
  - Strength: the UI never shows "No approval needed" for an out-of-date recommendation, and the staleness logic is not duplicated.
  - Tradeoff: two small additions to the Phase 2 contract.
  - Confidence: HIGH — the pins and their callers are confirmed in the code.
  - Blind spot: none significant.
- **Decision**: FIXED (Fix in plan)

### F2 — Delta: kredyt „pass” obok „over_limit” z S-03

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Implementation Approach, reguła credit
- **Detail**: S-03 marks Delta `over_limit` for the full 500 units. The policy only looks at the value of the selected option (31 500 PLN) and returns `pass`, and both results show on the same screen.
- **Fix**: The credit rule's reason names its basis ("Balance + selected option value within limit"). The README gets one sentence explaining this.
- **Decision**: FIXED (Fix in plan)

### F3 — Drobne luki w kontrakcie

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Faza 1 §2, Faza 2 §1/§4, tabela reguł
- **Detail**:
  - (a) `PolicyView` adds an `outcome` field that already exists in `PolicyResult`.
  - (b) All tests share one database and `policy_rules` is not cleaned up between them.
  - (c) The plan does not describe what happens with a negative discount when the target price is at or above the list price.
- **Fix**:
  - Remove "+ outcome".
  - A test that changes a threshold restores it in a `finally` block.
  - Add "target price ≥ list price → discount ≤ 0, `pass`" to the plan.
- **Decision**: FIXED (Fix in plan)
