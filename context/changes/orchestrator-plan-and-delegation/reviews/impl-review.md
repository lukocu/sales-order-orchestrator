<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Plan orchestratora i delegowanie sprawdzeń

- **Plan**: context/changes/orchestrator-plan-and-delegation/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4, 5
- **Date**: 2026-11-11
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 5 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | WARNING |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Automated checks re-run on 2026-11-11:
- `check.sh`: 423 passed.
- `alembic check`: no new operations.
- Frontend lint, typecheck, 70 tests and build all passed.
- Not re-run: `docker build` (passed in phase 5), and the downgrade/upgrade round trip (passed in phase 1).

## Findings

### F1 — An orchestration result can overwrite a newer one at the same analysis version

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/orchestration/service.py:160, 345-373
- **Detail**:
  - `_store` checks only two things: the analysis version is the same, and `_current_outcome == "exception"`. `stale` compares only `analysis_version`.
  - A recheck at the same analysis version re-reads live stock, so it can change `shortage` without changing the version.
  - **Race:** a slow LLM-planned run started before that recheck stores its result last. That result came from older checks, yet it shows `stale=false`.
  - **Failed rerun:** if the post-recheck orchestration fails, which is only logged, the previous result stays and still looks fresh.
  - Today stock does not change in the demo, so the risk is latent.
- **Fix A ⭐ Recommended**: Store the `run_id` or `checked_at` of the checks row the result was built from in `inquiry_orchestrations`. Compare it under `FOR UPDATE` in `_store` and include it in `stale`.
  - Strength: closes the race and the "stale but shown as fresh" case. Same versioning idea as the plan's State sequencing.
  - Tradeoff: needs a new column and migration 0008, plus tests.
  - Confidence: HIGH — `_store` already holds the lock and reads the checks row.
  - Blind spot: how often stock changes in real use has not been checked.
- **Fix B**: Record it as a known limitation in the plan or README, and fix it with S-05/S-06 when stock starts changing.
  - Strength: no code change while demo stock is static.
  - Tradeoff: the latent bug stays.
  - Confidence: MED — depends on future slices.
  - Blind spot: none significant.
- **Decision**: FIXED (Fix A): checks_checked_at + migracja 0008_orchestration_checks_ref, warunek w _store i stale, 3 testy

### F2 — Analyze/correct requests wait for up to two planner LLM calls

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/orchestration/service.py:59, 277-295; backend/app/parsing/service.py (`_run_checks_after_save`)
- **Detail**:
  - `PLANNER_ATTEMPTS = 2` and `LLM_TIMEOUT_SECONDS` defaults to 30.
  - `orchestrate_after_checks` runs synchronously inside POST/PUT analysis. In the worst case the request takes about 60 s more on top of extraction.
  - The plan accepted "at most 2 attempts" (Performance Considerations), but it gave no total time cap for user requests.
- **Fix A ⭐ Recommended**: Use one planner attempt in the after-save path, and keep the retry only for the explicit `POST /orchestration`.
  - Strength: caps the extra Analyze latency at a single timeout. A user can still rerun manually.
  - Tradeoff: a transient error during analysis gives `failed` sooner, and needs a click on "Re-run orchestrator".
  - Confidence: HIGH — `run_orchestration` already takes keyword arguments as test seams.
  - Blind spot: a separate planner timeout shorter than the parser's has not been measured.
- **Fix B**: Leave it as is and document it in Performance Considerations.
  - Strength: no change; matches the accepted plan.
  - Tradeoff: worst-case latency stays at about 60 s.
  - Confidence: MED.
  - Blind spot: Render request timeouts.
- **Decision**: FIXED (Fix A): planner_attempts=1 w orchestrate_after_checks, test, README

### F3 — Pool timeout is retried as a transient error

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/orchestration/executor.py:29
- **Detail**:
  - `TRANSIENT_ERRORS` includes `PoolTimeoutError`.
  - When the pool (5+5) is exhausted, a retry 0.5 s later adds load to a pool that is already full and waits up to another 30 s.
  - The plan did list `TimeoutError` as transient, so this is a weakness in the plan itself.
- **Fix**: Retry only `OperationalError`, and update the plan and the executor test.
- **Decision**: FIXED: TRANSIENT_ERRORS = (OperationalError,), test, kontrakt w planie

### F4 — Second `_store` condition is untested

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/app/orchestration/service.py:370
- **Detail**: No test covers the case where the version is the same but the checks outcome is no longer `exception`. Only the version change is covered (`test_result_of_a_replaced_analysis_version_is_dropped`).
- **Fix**: Add a service test: change the checks outcome before `_store`, then assert that no orchestration row exists.
- **Decision**: FIXED: test_result_of_a_check_no_longer_an_exception_is_dropped

### F5 — Executor and planner logs have no inquiry id

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/orchestration/executor.py:78, backend/app/orchestration/service.py:295
- **Detail**: Both log only the step name and the error class. The project convention is error class plus id, as in `service.py:125` and the `api/analysis.py` helpers.
- **Fix**: Pass `inquiry_id` into `execute`/`_plan` and add it to these two logs.
- **Decision**: FIXED: inquiry_id w logach executora i plannera

### F6 — Unplanned additions in the service and executor

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/orchestration/service.py:183-197, 307-314; backend/app/orchestration/executor.py:33
- **Detail**: All harmless hardening that the plan does not describe:
  - planner error codes `not_configured`, `rate_limited`, `unavailable` and `failed`;
  - a guard against an agent result with the wrong capability (`UnexpectedResult`);
  - a defensive `NothingToOrchestrate` when the product or customer is missing.
- **Fix**: Add a short addendum to the plan listing these additions.
- **Decision**: FIXED: addendum w plan.md

### F7 — Plan criterion "wall time ≤ sum of steps" was wrong

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/orchestrator-plan-and-delegation/plan.md:432
- **Detail**:
  - The measurements contradict the criterion. On fake, wall time was 22.6 ms against 14.5 ms for the sum of steps. On Render with Groq, 2214 ms against 1957 ms.
  - The difference is the overhead of writing each step.
  - The user accepted 3.3, the README states it correctly, and parallelism is proven by the barrier test.
  - The plan still contains the criterion as written.
- **Fix**: Change the wording in the plan to "parallelism confirmed by the barrier test; wall time vs. sum of steps visible in the UI".
- **Decision**: FIXED: kryterium 3.3 przeformułowane w plan.md

### F8 — Progress row 5.8 has no SHA

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/orchestrator-plan-and-delegation/plan.md:696
- **Detail**:
  - The Render check had no code commit of its own; it verified the deploy of `6c4071d`.
  - `/10x-archive` will show this row as a warning.
- **Fix**: Append ` — 6c4071d` to the row (the deployed commit).
- **Decision**: FIXED: wiersz 5.8 ma SHA 6c4071d
