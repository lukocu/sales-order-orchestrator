<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Porównanie stałego workflow z orchestratorem (S-10)

- **Plan**: context/changes/workflow-vs-orchestrator-eval/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-14
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 5 warnings, 4 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Automated gates at 22bec55: `check.sh` passed (ruff, ruff format, mypy, alembic, pytest 864 passed); `pytest tests/test_eval_*.py` passed (51). Manual Progress rows 1.5, 2.5 and 3.4–3.6 are checked; the real report is committed in 7bda4b3 and contains no API key.

## Findings

### F1 — Stale recommendation or verdict can be scored for the wrong arm

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/scoring.py:130-207
- **Detail**: `recommend_after_orchestration` (backend/app/recommendation/service.py:131-148) never raises; on an unclassified recommender error it leaves the stored recommendation as it was. That row belongs to the previous arm run (or the setup's FakeRecommender) and is exposed as `stale=True`; the policy is marked stale too (parsing/service.py:480). `observe` and `_decision_failure` never read `stale`, so the orchestrator arm can inherit the workflow arm's option and verdict, count its cost again, and score a hit. All scoring test fixtures use `stale=False`. The 2026-11-14 run logged no such error (only 2 PlannerFailed), so the committed numbers are not affected.
- **Fix**: In `_decision_failure`, return a failure (e.g. `stale_result`) when the orchestration, recommendation or policy view is stale, drop its decision, cost and run from the observation, and add a scoring test with `stale=True`.
  - Strength: Uses the staleness signal the views already carry; makes the scoring match what the user sees in the UI.
  - Tradeoff: A new failure code in the report; small change in `observe`.
  - Confidence: HIGH — the code path is visible in service.py and scoring.py.
  - Blind spot: Have not checked whether orchestration views can be stale after `reorchestrate_inquiry` in practice.
- **Decision**: FIXED — stale stages score as `stale_result`, drop decision and cost; tests added

### F2 — Leftover sweep and test cleanup check are global, so concurrent runs interfere

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/runner.py:111-114, backend/tests/test_eval_runner.py:87-99
- **Detail**: The startup sweep deletes every inquiry whose subject starts with `[eval] `, including those of an eval run still in progress. The tests call `run_eval` on the same database as the CLI, so running pytest (or a second CLI) during a paid eval deletes the live run's inquiries; it then fails with `InquiryNotFound` and writes no report. `_assert_clean` likewise checks for any new `TraceRun` with `subject_type="inquiry"` in the whole database, which can fail when the dev server creates runs at the same time. tests/conftest.py:33-38 uses per-process markers precisely to avoid this.
- **Fix A ⭐ Recommended**: Hold a Postgres advisory lock for the duration of `run_eval` (fail fast with a clear message if taken), and scope the test checks to the ids of the inquiries the run created.
  - Strength: Small change; keeps the `[eval] ` prefix and the sweep semantics; a second run is refused instead of corrupting the first.
  - Tradeoff: Runs cannot overlap at all, which is fine for an author-run CLI.
  - Confidence: MED — advisory locks are standard in Postgres, but not used elsewhere in this repo yet.
  - Blind spot: Tests running in parallel with a live CLI would then fail on the lock instead.
- **Fix B**: Give each run its own prefix (`[eval:<uuid8>] `) and sweep only leftovers older than a few hours.
  - Strength: Runs can coexist; mirrors the conftest per-process marker pattern.
  - Tradeoff: Age-based sweep needs a timestamp filter and a threshold to choose.
  - Confidence: MED — straightforward, but more moving parts.
  - Blind spot: An interrupted run's rows stay until the threshold passes.
- **Decision**: FIXED via Fix A — Postgres advisory lock for the run (`EvalAlreadyRunning`, CLI exit 1); test cleanup checks scoped to the run's own inquiry ids

### F3 — "Local database only" is not enforced

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/__main__.py (engine from `get_engine()`), backend/app/eval/runner.py:111-114
- **Detail**: The plan (What We're NOT Doing) and the module docstring say the eval runs only on the local container database, but the CLI uses whatever `DATABASE_URL` is set. app/tracing/demo.py documents pointing a CLI at the Supabase pooler and render.yaml sets a deployed URL. Against a shared database the eval would insert visible `[eval] ` inquiries, make paid calls, and delete every `[eval] `-prefixed inquiry.
- **Fix**: Refuse to run unless the database host is local (`localhost`, `127.0.0.1`, `db`), with an explicit `--allow-remote-db` override, and test the refusal.
  - Strength: Turns a documented rule into a guard, like the existing `--allow-fake` guard.
  - Tradeoff: One more flag; host check must parse the URL.
  - Confidence: HIGH — same pattern as the provider guard in __main__.py.
  - Blind spot: A local tunnel to a remote database would still pass.
- **Decision**: FIXED — CLI refuses a non-local DB host without `--allow-remote-db` (exit 2); test added

### F4 — One unexpected error discards the whole run

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/runner.py:146-167, backend/app/eval/__main__.py (call to `run_eval`)
- **Detail**: `reorchestrate_inquiry` re-raises unexpected planner errors and DB errors are not caught. The exception leaves `run_eval`; cleanup runs, but `main` never writes the report, so every paid observation so far is lost and the user gets a traceback. The cleanup test covers deletion, not the lost results.
- **Fix**: Catch `Exception` per arm call and record it as an observation `unexpected:<ClassName>` (class name only, as the services do), and wrap the run in `main` with `SQLAlchemyError` handling returning 1, like auth/demo_accounts.py.
- **Decision**: FIXED — arm call errors recorded as `unexpected:<ClassName>`; CLI returns 1 on SQLAlchemyError; tests added

### F5 — Plan not updated for three deviations

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: context/changes/workflow-vs-orchestrator-eval/plan.md
- **Detail**: (1) The real run used OpenRouter with `qwen/qwen3-30b-a3b-instruct-2507` instead of Groq (Groq free tier returned 429 on almost every call); this is recorded only in commit 7bda4b3, and Progress row 3.4 still reads "Przebieg z Groq". (2) `run_eval` has three extra required keyword arguments (`provider`, `model`, `cases_version`). (3) The report counts accuracy over all runs, but failures, cost, time and tokens over orchestrated runs only (`ArmReport`); this is explained in the report's methodology notes, not in the plan.
- **Fix**: Add a short "Deviations" note to change.md listing the three points (Progress titles stay unchanged).
- **Decision**: FIXED — Deviations note added to change.md

### F6 — Missing duration silently counts as 0 ms

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/scoring.py:204
- **Detail**: `round(sum(r.duration_ms or 0.0 ...))` adds 0 for a run without a duration (still running, or tracing could not finish it), and `cost_complete` stays true, so the mean time is understated without any signal.
- **Fix**: Treat a run without `duration_ms` like a missing run for completeness (set `cost_complete=False` or a separate time flag).
- **Decision**: FIXED — a run without duration makes cost_complete false; test added

### F7 — Planner failure reason is not kept

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/scoring.py:135-137
- **Detail**: Both failures in the committed report are `orchestration_failed:failed`. `Observation` keeps only the error code, so the report cannot say why the planner failed (e.g. invalid JSON vs. plan rejected).
- **Fix**: Keep the orchestration error's class/kind next to the code in the failure string when available.
- **Decision**: FIXED — `failure_detail` (stage error kind and message) in observations and the report's failure table

### F8 — CLI guard tested only for the fake provider

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/tests/test_eval_runner.py (CLI tests)
- **Detail**: The exit-2 guard is tested for `llm_provider=fake`, not for a real provider with an empty `LLM_API_KEY`, which is the case the author hit while setting up the real run.
- **Fix**: Add a CLI test with `llm_provider=groq` and an empty key expecting exit code 2.
- **Decision**: FIXED — CLI test for a real provider with an empty key

### F9 — Unrelated tracing fix lands in the change's date range

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: backend/app/tracing/recorder.py (commit 9ccff5f)
- **Detail**: 9ccff5f (step `started_at` from a monotonic clock) sits between p2 and p3 but is a separate fix for a flaky test, reviewed in PR lukocu/sales-order-orchestrator#1. The eval does not depend on step ordering (it uses run totals and run-level `duration_ms`).
- **Fix**: No change needed; mention it in the change.md deviations note so the archive does not attribute it to S-10.
- **Decision**: FIXED — documented in change.md (Deviations, via F5); no code change

## Triage

Triage completed 2026-11-14: F1–F9 fixed. `check.sh` passes (873 tests); break-checks for F1 (stale), F2 (lock) and F3 (remote DB) turned the new tests red on broken code and the code was restored.
