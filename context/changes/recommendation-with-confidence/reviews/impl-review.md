<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Recommendation with confidence

- **Plan**: context/changes/recommendation-with-confidence/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4, 5
- **Date**: 2026-11-11
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 5 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Automated gates were re-run on 2026-11-11 and all pass:

- `sh check.sh`: 520 passed.
- `alembic check`: no new operations.
- Frontend: lint, typecheck, 98 tests and build all pass.

Every Manual item has evidence. 5.8 was checked on Render: ACME `stock+ABC-110`, HIGH, 25.51%, `choose` 1684/645 tokens, $0.00064.

## Findings

### F1 — Two offers from one supplier collide on cost and option id

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/recommendation/service.py:248-256, backend/app/recommendation/options.py:206, :274, :286
- **Detail**:
  - `supplier_offers` has no UNIQUE constraint on (product_id, supplier_name) (0007:99-110).
  - `supplier_costs` is a dict keyed by (supplier, code), so it keeps the cost of the last offer, and every offer from that supplier is priced with it.
  - The options get the same id `stock+supplier:<name>`. This causes three problems:
    - duplicates in the LLM enum;
    - `validate_choice` takes the first match;
    - duplicate React keys.
  - The seed has one offer per supplier, so the bug is latent.
- **Fix A ⭐ Recommended**: Add a migration with UNIQUE (product_id, supplier_name) on supplier_offers.
  - Strength: Makes the code's assumption an invariant enforced by the database, at the cost of one constraint and no logic changes.
  - Tradeoff: A supplier cannot have two offers for one product (different lead times).
  - Confidence: HIGH — seed has 1 offer per supplier; the same pattern is used in product_substitutes.
  - Blind spot: Data on Render was not checked for duplicates before adding the constraint.
- **Fix B**: Carry `offer_id` in `SupplierDelivery` and key both costs and option ids by it.
  - Strength: Supports several offers from one supplier.
  - Tradeoff: Changes the schema of check results stored in JSONB (lessons.md → data migration) and the option ids.
  - Confidence: MED — broader change across checks and recommendation.
  - Blind spot: Effect on stored check results.
- **Decision**: FIXED (Fix A) — migracja 0010_supplier_offer_unique + UniqueConstraint w modelu SupplierOffer + test test_one_offer_per_supplier_and_product

### F2 — Customer history missing from RecommendationFacts

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/recommendation/schema.py:102
- **Detail**:
  - Plan (F4): facts include "requested, shortage, deadline, consent, history signal".
  - `RecommendationFacts` has no history field.
  - The LLM sees history only through the `history_*` signals on substitute options.
- **Fix**: Add the plan note "history is passed only as signals of substitute options" (it only matters for substitutes), or add a `history` field to facts.
- **Decision**: FIXED (dodane pole) — RecommendationFacts.customer_history, opis w prompcie LLM i README, test test_facts_carry_the_customer_history_signal

### F3 — Stale comment on `choice` and an unreachable "Rejected choice" branch

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/recommendation/schema.py:97, frontend/src/components/RecommendationSection.tsx:195-197
- **Detail**:
  - The comment says "kept also when the choice was rejected", but after the fix in phase 3 a rejected choice is not stored (`choice=None`).
  - The frontend's "Rejected choice: option X" branch can therefore never run.
- **Fix**: Change the comment to "None when the choice was rejected", and remove the dead branch together with its test (if there is one).
- **Decision**: FIXED — komentarz poprawiony, martwa gałąź „Rejected choice” i prop choice ErrorBox usunięte, test dostosowany (choice: null)

### F4 — Seed backfill invents costs for rows outside the seed

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/migrations/versions/0009_recommendation_data.py:60-69
- **Detail**:
  - The 0.7 / 0.8 × list price fallback is planned.
  - It is silent, though: on a database with non-seed products, margins and signals would rest on made-up costs.
  - This is acceptable for a demo app.
- **Fix**: Add a comment in the migration and the README that the fallback is for the demo / dev only.
- **Decision**: SKIPPED

### F5 — Undocumented extras compared with the plan

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/recommendation/confidence.py:84-85, backend/app/recommendation/llm_recommender.py:381-389, frontend/src/api/analysis.ts:354
- **Detail**:
  - Info signal `history_mixed`: absent from the plan's list. It does not lower the band.
  - The "Information" list in the UI.
  - `recommendation?` is optional in the frontend guard.
  - `Llm*` errors are re-raised `from error`, not `from None` as the plan says. This matches `llm_planner.py`, and the messages contain no content.
  - All of these are benign.
- **Fix**: Add a short "Deviations" section to plan.md, or leave as is.
- **Decision**: FIXED — sekcja ## Deviations w plan.md

### F6 — Manual re-run with 409 leaves an outdated recommendation in place

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/parsing/service.py:259-274
- **Detail**:
  - When `run_recommendation` raises `NothingToRecommend`, `rerecommend_inquiry` returns 409 without calling `_drop_outdated`; only the automatic path cleans up.
  - The UI hides the button in this state, and the view marks the row as stale.
- **Fix**: Call `_drop_outdated` before re-raising `NothingToRecommend`.
- **Decision**: FIXED — run_recommendation wywołuje _drop_outdated przed ponownym rzuceniem NothingToRecommend; test test_rerun_without_anything_to_recommend_drops_the_outdated_recommendation

### F7 — Invalid stored checks on the re-run reported as "Stored analysis is invalid"

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/recommendation/service.py:224-225, backend/app/api/analysis.py:266-267
- **Detail**: `_read_inputs` validates `CheckResults` without a guard. The `ValidationError` names the wrong table, which matches the existing re-orchestrate path.
- **Fix**: Leave as is (consistent with orchestration), or fix both paths in a separate change.
- **Decision**: SKIPPED — spójne z orchestracją

### F8 — Worst-case latency of a synchronous request is now about 3× the LLM timeout

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/parsing/service.py:112-169, backend/app/orchestration/service.py:122-140
- **Detail**:
  - Analyze/correct now runs extraction, the planner and the recommender one after another.
  - The automatic path gives the recommender 1 attempt (as planned).
  - The plan's Performance Considerations section accepts this.
- **Fix**: None needed; consider async/background work if latency on Render becomes a problem.
- **Decision**: ACCEPTED — zgodne z Performance Considerations planu
