<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Eval regression gate

- **Plan**: context/changes/testing-eval-regression-gate/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-20
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 6 warnings, 2 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Success criteria run: ruff, ruff format, mypy (147 files), `pytest tests/test_eval_compare.py` (44 passed), `--help`; full `check.sh` (1163 passed) and the break-check ran earlier in phase 3.
Plan drift: none. Cosmetic: the CI consistency test message is in English (plan quoted Polish); `load_report` uses `json.loads` + `model_validate` instead of `model_validate_json` (needed: computed `rate`).

## Findings

### F1 — Unequal run counts per pair are not detected

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:143-153
- **Detail**: `repeats` is compared, but the number of runs per (case, arm) is not. Baseline 3/3 against current 2/2 is neither a regression nor an improvement; a report truncated to one run per pair passes. Silent false negative.
- **Fix**: Treat `len(after) != len(before)` as a blocking regression (or an incompatibility).
- **Decision**: FIXED

### F2 — Baseline-unstable pair can drop to 0 hits without blocking

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:150-151
- **Detail**: A pair at 2/3 in the baseline that falls to 0/3 lands in "Noise" (exit 0). This is the decided design, but it is the largest false-negative surface and has no test pinning it.
- **Fix A ⭐ Recommended**: Block when current hits are 0 on a pair that had hits.
  - Strength: Keeps tolerance for 1-hit wobble, catches total collapse.
  - Tradeoff: Deviates from the rule decided in planning (small).
  - Confidence: MED — depends on how noisy real 3-repeat runs are.
  - Blind spot: No data on real variance of the unstable pairs.
- **Fix B**: Keep the design, add a test that pins the behaviour and document it in §6.3.
  - Strength: No behaviour change.
  - Tradeoff: Total collapse of a flaky pair stays non-blocking.
  - Confidence: HIGH — trivial.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A

### F3 — `--out` write failure ends with a traceback and exit 1

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:305-307
- **Detail**: `mkdir`/`write_text` are not guarded. An unwritable `--out` raises after stdout is printed; Python's uncaught-exception exit code 1 reads as "blocking regression".
- **Fix**: Catch `OSError`, log it and return `EXIT_UNUSABLE`.
- **Decision**: FIXED

### F4 — Mixed naive/aware `started_at` crashes baseline selection

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:330, 342, 349
- **Detail**: `started_at` is a plain `datetime`; one file with an offset and one without makes `max`/`<` raise `TypeError` (traceback, exit 1).
- **Fix**: Normalise in `load_report` (naive → UTC) or reject with `ValueError`.
- **Decision**: FIXED

### F5 — Explicit `--baseline`/`--current` are not sanity-checked

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:334-335
- **Detail**: Same-file and "older than current" rules apply only to auto-selection. `--baseline X --current X` compares a file with itself and exits 0.
- **Fix**: Exit 2 when the resolved paths are equal.
- **Decision**: FIXED

### F6 — `--cost-factor` accepts `nan` and `inf`

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:252-256
- **Detail**: `float("nan") <= 1` is False, so it passes validation; `nan` makes every metric warn, `inf` none.
- **Fix**: Also reject non-finite values with `math.isfinite`; add them to the parametrised test.
- **Decision**: FIXED

### F7 — Decode errors do not name the file

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/compare.py:106
- **Detail**: `UnicodeDecodeError` is a `ValueError` (exit 2 holds) but `load_report` does not wrap it, so the message lacks the path promised by the docstring.
- **Fix**: Add `UnicodeDecodeError` to the except tuple.
- **Decision**: FIXED

### F8 — Misleading test comment and missing edge-case tests

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_eval_compare.py:232-240
- **Detail**: Comment says "2/3 -> 2/3" but data is 0/3 -> 2/3 and `improvements` is not asserted. No tests for F1, F3, F4, F5, non-UTF8 input or an arm missing from `summaries`.
- **Fix**: Fix the comment, assert the improvement, add tests alongside the fixes above.
- **Decision**: FIXED
