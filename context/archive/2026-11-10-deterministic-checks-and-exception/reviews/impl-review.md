<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: S-03 deterministic-checks-and-exception

- **Plan**: context/changes/deterministic-checks-and-exception/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-10
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 3 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Success criteria were re-run on 9d7b588 and all passed:
- `check.sh`: 282 passed
- `alembic check`: no new operations
- frontend lint, typecheck, test and build: all exit 0

All manual rows (1.4, 2.3, 3.7, 3.8) have recorded evidence in this session.

## Findings

### F1 — An unexpected rule error in POST /checks gives an opaque 500

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/analysis.py:158-171 (`recheck`), backend/app/checks/rules.py (`check_price`)
- **Detail**:
  - `recheck` catches only InquiryNotFound, NoAnalysis, ValidationError and SQLAlchemyError. Any other exception reaches Starlette, which returns a plain-text "Internal Server Error". Uvicorn logs the full traceback, which breaks the rule of logging only the class name.
  - The bug is reachable today: `ParsedFields.quantity` has no upper bound. With a quantity around 10**30, `(unit_price * quantity).quantize(CENT)` raises `decimal.InvalidOperation`.
  - After a PUT with that quantity the result stays stale for good, and every "Re-run checks" returns a 500.
  - No test covers a rule error on the `/checks` route.
- **Fix A ⭐ Recommended**: In `recheck`, add an `except Exception` that logs the class name and inquiry id and returns a JSON 500 "Checks failed". In the price and credit rules, catch `InvalidOperation`. Add a test with monkeypatched `check_price` on POST /checks.
  - Strength: Fixes both the error path and the concrete trigger without changing the JSONB schema, so the lesson does not apply.
  - Tradeoff: The quantity limit still lives only in the rules. Absurd quantities will still pass analysis validation.
  - Confidence: HIGH — follows the pattern of `_run_checks_after_save`.
  - Blind spot: How the UI shows such a quantity before saving.
- **Fix B**: Add `le=` (e.g. 1 000 000 000) to `ParsedFields.quantity`, plus the same catch-all in `recheck` and a test.
  - Strength: Stops absurd values at the input.
  - Tradeoff: This changes a model read from JSONB, so per the lesson it needs a migration or a check of existing rows. A bound in the model would also affect the analysis and the LLM output.
  - Confidence: MED — on Render the stored values are small, but this was not checked across all rows.
  - Blind spot: Behaviour of Groq output for a quantity above the bound.
- **Decision**: FIXED (Fix A) — catch-all w `recheck` (JSON 500 „Checks failed”, log tylko klasy i id), `check_price` łapie `InvalidOperation` → `skipped`; testy `test_recheck_with_failing_check_is_json_500`, `test_absurd_quantity_skips_price_and_credit`

### F2 — A late re-run response can overwrite a newer analysis in the panel

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: frontend/src/components/AnalysisPanel.tsx:251-262 (`showChecked`), frontend/src/components/ChecksSection.tsx:274-285
- **Detail**:
  - The `running` state lives only in ChecksSection, so "Save corrections" and "Re-analyze" stay active during a re-run.
  - Sequence: Re-run, then Save. The save returns first, then the re-run response returns. The re-run closure still holds the old analysis, so `setLoad` puts v1 back. The badge in the inbox also falls back to the old outcome.
  - Switching to another inquiry is safe, because the panel has `key={inquiry.id}`.
- **Fix**: Move the in-flight state of the re-run into AnalysisPanel as `busy = 'checking'`, so Save and Re-analyze are disabled during a re-run. Add a test with a deferred `rerunChecks` promise.
  - Strength: Same pattern as the existing `busy` for analyze and save. Removes the race at the source.
  - Tradeoff: The re-run button and the form share one busy state, so the user waits a few ms.
  - Confidence: HIGH — `busy` already blocks the other buttons.
  - Blind spot: None significant.
- **Decision**: FIXED — `busy = 'checking'` w AnalysisPanel blokuje zapis i ponowną analizę podczas ponowienia; test z odroczonym fetch (break-check: czerwony)

### F3 — No test for skipping the write after a version change

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/checks/service.py:116-126
- **Detail**: The logic is correct (`FOR UPDATE`, then a version comparison, then a return). However, no test covers the path where the analysis changes during the run. The plan's test list did not require one, but it is the heart of the "Version and race" rule.
- **Fix**: Add a service test. Monkeypatch `check_credit` so that it bumps `corrected_at` in its own session. Then assert that the `inquiry_checks` row was not written and that the run exists.
- **Decision**: FIXED — `test_result_of_a_replaced_analysis_version_is_dropped` (break-check: czerwony bez porównania wersji)

### F4 — Stored checks that no longer match the schema block the whole analysis view

- **Severity**: 💡 OBSERVATION
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/checks/service.py:139
- **Detail**:
  - When `inquiry_checks.results` stops matching `CheckResults` (`extra="forbid"`), GET /analysis returns a 500 "Stored analysis is invalid", and the panel shows only an error.
  - "Re-run checks" does not appear, even though POST /checks would overwrite the row.
  - The plan explicitly required this 500, and a test enforces it. This is a remark on the plan's contract, not a drift from it.
- **Fix**: In `get_checks_view`, catch `ValidationError`, log the class name, and return `None`. The panel then offers "Re-run checks". Update the test.
  - Strength: The UI can recover by itself after a schema change; the analysis itself stays readable.
  - Tradeoff: Departs from the plan contract. A broken result is hidden instead of reported, though it is logged.
  - Confidence: MED — depends on whether you prefer a loud error or self-repair.
  - Blind spot: Monitoring of such logs on Render.
- **Decision**: FIXED — `get_checks_view` łapie `ValidationError`, loguje klasę i zwraca `None`, panel proponuje „Re-run checks”; test `test_stored_result_not_matching_schema_can_be_rechecked` (odejście od kontraktu planu za zgodą użytkownika)

### F5 — A target price without a product shows "Within standard"

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/checks/rules.py:183-188
- **Detail**: With `target_price` and no product, the unit price is unknown, but the discount status is `ok`, so the UI shows "Within standard". The outcome is already `needs_input`, so the result is not affected, but the line is misleading. The plan does not list discount as skipped without a product, so this is a gap in the plan.
- **Fix**: Return `skipped` for discount when `price_kind == target_price` and the unit price is unknown. Add a rule test.
- **Decision**: FIXED — `check_discount` zwraca `skipped` dla ceny docelowej bez ceny standardowej; test `test_target_price_without_a_standard_price_is_skipped`

### F6 — Inbox duplicates formatDate

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: frontend/src/components/Inbox.tsx:34-39
- **Detail**: The change moved `formatDate` into `components/format.ts`, but Inbox still keeps an identical local copy.
- **Fix**: Import `formatDate` from `./format` and remove the local copy.
- **Decision**: FIXED — Inbox importuje `formatDate` z `./format`
