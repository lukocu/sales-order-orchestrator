<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Parser field eval

- **Plan**: context/changes/testing-parser-field-eval/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4
- **Date**: 2026-11-20
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 7 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Success criteria re-run: 88 field-eval tests pass, ruff check/format and mypy pass, no `TBD — see §3 Phase 2` left in test-plan. The full backend gate was not re-run here (it passed at the end of phases 3 and 4). All manual rows are ticked with evidence (committed baseline, §6.6 triage). Nothing outside the planned paths changed; the decision eval, `EvalReport`, `compare.py`, parser and `cases.json` are untouched.

## Findings

### F1 — Billed usage of failed calls is dropped

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/runner.py:106-117
- **Detail**: `ExtractionError.usage` is set when the provider answered (and billed) before the failure (`app/parsing/extractor.py:27-33`, `openai_compatible.py:89-97`). `_observe` records only the class name, so the token totals in the report under-count and failed-but-billed calls are invisible. Verified in code.
- **Fix**: Store `input_tokens`/`output_tokens` from `error.usage` on the failure observation and add a test.
- **Decision**: FIXED

### F2 — A mid-run crash discards a paid run

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/runner.py:90-100, backend/app/eval/fields/__main__.py:106-131, report.py `_paths`
- **Detail**: Any non-`ExtractionError` exception (a `build_parsed` bug, KeyboardInterrupt) aborts a roughly 10-minute, 126-call run and writes nothing. A `FileExistsError` from `_paths` is raised only after the whole run. The decision eval records per-call exceptions (`app/eval/runner.py:267`).
- **Fix A ⭐ Recommended**: Write a partial report when the run is interrupted or fails, and let the exception still propagate afterwards.
  - Strength: Keeps the paid observations; keeps bugs loud.
  - Tradeoff: A partial report must be clearly marked in the metadata.
  - Confidence: MED — small change, but the run/report shape needs a `partial` flag.
  - Blind spot: Behaviour of partial reports with the unstable-pair logic.
- **Fix B**: Only check up front that the report file name is free, and leave the rest.
  - Strength: Trivial; covers the cheapest failure.
  - Tradeoff: A mid-run crash still loses everything.
  - Confidence: HIGH — one call before the loop.
  - Blind spot: None significant.
- **Decision**: FIXED via Fix A (partial report, marked PARTIAL RUN; the original error is re-raised)

### F3 — Several tests could not catch the bug they name

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: tests/test_eval_fields_runner.py:143-158, tests/test_eval_fields_report.py:112,127-134, tests/test_eval_fields_scoring.py:233-249, tests/test_eval_fields_cases.py:110
- **Detail**:
  - The "error message stays out of the report" check asserts the word "timeout" is absent, but would not notice a leak of other message text; the report test checks only "boom". A unique sentinel in the message would be a real check on both JSON and Markdown.
  - Percentages are tested only with non-zero totals; the all-calls-failed run and a tag with zero units are never exercised.
  - The reference-day tests use one UTC-5 value; no DST day, and no assertion that `reference_day` equals `reference_date_of` (the copy in `cases.py:54-56` can drift from `parsing/service.py:126`).
  - No test of two tags mapping to the same field in one case.
- **Fix**: Add a sentinel leak test, an all-failed report test, `reference_day == reference_date_of` for the 2026-03-29 / 2026-10-25 transition days and the 22:59/23:00Z boundary, and a same-field double-tag summarize test.
  - Strength: Closes the silent-pass holes in exactly the parts that make the eval trustworthy.
  - Tradeoff: A few dozen test lines.
  - Confidence: HIGH — each hole was read in the test files.
  - Blind spot: `reference_date_of` is not DB-free importable; the equivalence test may need a pure helper or a stub.
- **Decision**: FIXED

### F4 — Empty text label accepted

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/cases.py:76-82, scoring.py:39-42
- **Detail**: `ExpectedText` accepts `value: ""`; `normalize_name("")` is empty, so the case would score `silent_wrong` forever.
- **Fix**: Reject empty or whitespace-only text values in the validator (and add a test).
- **Decision**: FIXED

### F5 — A tag with zero units disappears from the per-tag table

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/report.py:305-321
- **Detail**: The table is built from observed outcomes only, so a tag whose calls all failed is missing instead of showing 0.
- **Fix**: Iterate over the tags present in `run.cases`.
- **Decision**: FIXED

### F6 — A silent error caused only by a missing flag reads as a no-op

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/report.py:340-371
- **Detail**: When the value is correct but a required flag is missing, Got equals Expected, so the silent-errors row looks like nothing is wrong.
- **Fix**: Mark such rows "(not flagged)".
- **Decision**: FIXED

### F7 — Report claims inquiry text stays out, but the JSON embeds every case

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/runner.py (docstring), report.py, __main__.py `--cases`
- **Detail**: Only error messages stay out. The JSON stores each case's full subject and body (`FieldRun.cases`), plus parsed customer and phrases. Harmless for the committed synthetic set, but `--cases` accepts any file, so a run on real inquiries would write PII under `eval_reports/`.
- **Fix**: Reword the docstring and note it in the `--cases` help.
- **Decision**: FIXED

### F8 — Markdown table escaping is partial

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/report.py `_row`
- **Detail**: `|` and `\n` are escaped; `\r` and a trailing backslash are not, and model-controlled strings (customer, `deadline_text`, `price_text`) go in. The effect is a broken table or markup in a viewer. No test covers escaping.
- **Fix**: Strip `\r`, escape `\` before `|`, add one test.
- **Decision**: FIXED

### F9 — `--pause-seconds inf` hangs

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/fields/__main__.py (`--pause-seconds`)
- **Detail**: Negative values are harmless (the guard is `> 0`), `inf` sleeps forever. The decision eval does not validate it either.
- **Fix**: Parse as a finite non-negative float.
- **Decision**: FIXED

### F10 — Small drift from the plan text, and a docs leftover

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/eval/fields/report.py:177-205,340-371; context/foundation/test-plan.md §4
- **Detail**:
  - The SILENT ERRORS section comes right after the per-field table, not after the case table (a readability choice).
  - The case table shows "Got" for the first successful repeat only, with per-repeat outcome letters only for fields that are not a hit in every repeat.
  - The silent-errors table has no phrase column (the plan Overview mentions the phrase; the Phase 3 contract does not).
  - The §4 decision-eval row lost its trailing "rozszerzany w fazach 2–3" text and now ends with a dangling `;`.
  - Extras: a few additional validators, `FieldRun.cases`, an injectable `sleep`, one extra exclusion bullet in §6.2. All harmless.
- **Fix**: Repair the §4 row; either add the phrase column to the silent-errors table or note the choice in the plan; the rest needs no action.
- **Decision**: FIXED (test-plan §4 row repaired; phrase column skipped by choice)
