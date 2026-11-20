# Parser field eval Implementation Plan

## Overview

Test-plan §3 Phase 2 (risk #4): measure how well the inquiry parser reads each field, separately from and cheaper than the full orchestration flow. A new, DB-free eval runs the configured extractor over a hand-labelled set of phrasings, passes the result through the real `build_parsed`, and scores each of the six user-visible fields as `hit`, `flagged_miss` (wrong but marked uncertain, acceptable under PRD FR-002) or `silent_wrong` (wrong and not marked — the risk-#4 failure). It reports accuracy per field and per tag and lists every silent error. It is a measurement, not a gate.

## Current State Analysis

- The decision eval does not measure the parser. For non-adversarial cases the runner parses with the regex extractor and then overwrites the result with golden fields (`backend/app/eval/runner.py:400-440`). For the 4 adversarial cases the configured extractor runs once and only `price_kind`, `price_value`, `quantity`, `product_code`, `substitute_allowed` are compared (`runner.py:85-91`, `:357-397`); a field difference alone is not a miss, and `customer`, `deadline`, `deadline_text`, `price_text` are never compared. The dataset-expansion plan explicitly deferred per-field scoring to this phase (`context/archive/2026-11-20-testing-eval-dataset-expansion/plan.md:48`).
- The parser is an LLM reading six fields plus a deterministic `build_parsed` that resolves deadlines from the phrase and the reference date, validates values and flags uncertainty (`backend/app/parsing/analyze.py:28-136`, `deadline.py:36-107`). Deterministic pieces have dense unit tests (`tests/test_parsing_deadline.py`, `test_parsing_analyze.py`); LLM extraction quality has none (tests use a mock transport).
- The parser needs no DB: `InquiryExtractor.extract(subject, body, reference_date) -> ExtractionResult(extraction, usage)` (`app/parsing/extractor.py:18-52`), then `build_parsed(extraction, reference_date) -> (ParsedFields, uncertain)`. Reference date is `reference_date_of(received_at)` = Warsaw day (`app/parsing/service.py:126-128`).
- `EvalReport`, `ArmRun`, `Score` and `compare.py` are decision/arm-shaped and not reusable here (`app/eval/scoring.py`, `compare.py:54,178-187`). `compare` loads `eval_reports/*.json` non-recursively and skips what is not an `EvalReport`; the CI test `test_latest_report_matches_the_case_file` forces a new full decision-eval report whenever `cases.json` changes (`tests/test_eval_compare.py:675-695`).
- Golden `fields` in `cases.json` use 12 distinct deadline phrases, nearly all inside the resolver's grammar, so they cannot stress phrasing.

## Desired End State

`python -m app.eval.fields` (no database) runs the extractor selected by `LLM_PROVIDER` over `backend/app/eval/fields/cases.json` for N repeats and writes `<date>-<provider>-<model>.{md,json}` to `backend/eval_reports/fields/`. The report shows hit / flagged-miss / silent-wrong per field and per tag, the case table, every silent error with the case id, phrase and values, unstable (case, field) pairs across repeats, and failed extractor calls. A first real-LLM baseline is committed. test-plan §6.2 documents how to add a field case. Verify: the new tests pass, `sh check.sh` is green, a `--allow-fake` run writes a report, and the committed baseline was produced by a real provider.

### Key Discoveries:

- Risk #4's anti-pattern is "expected dates computed by the same code that is tested" (`context/foundation/test-plan.md:63`); labels here are hand-derived and the loader checks only independent invariants (calendar weekday, not-before-reference).
- When the resolver recognises the phrase its date always wins over the model date (`analyze.py:99-113`), so for `deadline` the extractor is responsible for the verbatim phrase, and an unsupported phrase ends as `Resolved by model only` (flagged) or `Could not resolve` (flagged, empty).
- `substitute_allowed=None` is always flagged "Not stated", `customer`/`product_code`/`quantity` empty is always flagged "Missing", `price_kind="none"` and an absent deadline are never flagged (`analyze.py:42-56`, `:95-98`, `:125-136`).
- The regex extractor never produces `target_price` and always returns `uncertain=[]` (`app/parsing/fake.py:25-49,68-75`); it is a different code path from the LLM, so it is only a smoke-test extractor here.
- Importing `cases_sha256` from `app.eval.runner` is DB-free (`runner.py:133`).

## What We're NOT Doing

- No regression gate or baseline comparison for fields (a field-level `compare` waits for data on LLM variability; the decision gate from Phase 3 is untouched).
- No change to `cases.json`, `EvalReport`, `compare.py` or the decision eval (so the CI re-baseline coupling is not triggered).
- No English inquiries, HTML or quoted-reply mails: the parser is Polish-only plain text (`openai_compatible.py:27-53`, `context/archive/2026-11-14-test-mailbox-ingest/research.md:36,84-88`).
- No cases whose correct reading is itself a product decision (e.g. "10 dni roboczych" calendar vs business days, "za całość" price vs per unit). They are skipped, not guessed.
- No scoring of `deadline_text` / `price_text` (shown in the case table for diagnosis only) and no change to the parser, its prompt or `ParsedFields`.
- No CI run of the LLM eval; CI only runs the pure and stubbed-extractor tests.

## Implementation Approach

A self-contained package `backend/app/eval/fields/` beside the decision eval, reusing only `ParsedFields`/`build_parsed`/`get_extractor`/`reference_date_of`/`cases_sha256`. Four phases: pure schema+scoring first (testable without data), then the hand-labelled dataset, then runner/report/CLI, then docs and the first real baseline. Label discipline mirrors the decision eval: every case has a `rationale` that shows the arithmetic, and loading rejects inconsistent labels.

## Phase 1: Case schema, loader and field scoring

### Overview

The pure core: what a field case is, how it is validated, and how one parsed field is classified. No LLM, no dataset size requirement.

### Changes Required:

#### 1. Case model and loader

**File**: `backend/app/eval/fields/cases.py` (new), `backend/app/eval/fields/__init__.py` (new)

**Intent**: Define `FieldCase` (`id` kebab-case, `subject`, `body`, `received_at` aware datetime, `expected`, `rationale`, `tags`) and a loader that rejects bad labels at load time, like `app/eval/cases.py`.

**Contract**:
- `expected` has one entry per user-visible field: `customer`, `product_code`, `quantity`, `deadline`, `substitute_allowed` (each `value` nullable plus `flagged: bool = False`) and `price` (`kind: PriceKind`, `value: Decimal | None`, `flagged`). `deadline` additionally takes an optional `weekday` (monday..sunday).
- `flagged=True` means the correct outcome is a value that the parser must also mark uncertain (e.g. an ambiguous phrase labelled `value: null, flagged: true`); `flagged=False` means the flag is ignored for a hit.
- Validators: `id` kebab-case; ids unique across the file (`DuplicateCaseId`-style error); tags unique and from a closed `FieldTag` literal (deadline_supported, deadline_unsupported, deadline_absent, weekend_reference, year_rollover, substitute_stated, substitute_absent, price_target, price_discount, price_best, price_absent, customer_signature, customer_missing, quantity_variant); deadline `value`, when set, is not before the Warsaw day of `received_at`; deadline `weekday`, when set, equals the calendar weekday of `value`; price `value` follows the `ParsedFields` rules (valued kinds need a positive value, 0 < v ≤ 100 for discount, other kinds none); a `null` value requires `flagged=true` except for `deadline` and `price` (absent is legitimately unflagged); `rationale` non-empty.
- `FIELD_CASES_PATH = Path(__file__).with_name("cases.json")`; `load_cases(path | None) -> list[FieldCase]`. The loader never calls `resolve_deadline`.

#### 2. Field scoring

**File**: `backend/app/eval/fields/scoring.py` (new)

**Intent**: Classify each of the six fields of one parse against its expectation, and aggregate.

**Contract**:
- `FieldOutcome = Literal["hit", "flagged_miss", "silent_wrong"]`.
- `score_case(case, parsed: ParsedFields, uncertain: dict[FieldName, str]) -> dict[FieldName, FieldOutcome]`.
- A field is a `hit` when its value equals the label (`customer`: the label's words after `normalize_name` (`app/checks/rules.py:66-69`) appear as a contiguous run in the result's normalised words, the same rule `match_customer` uses to match a record name (`app/checks/rules.py:72-76,108-110`), so "Zakupy, ACME" and "ACME Sp. z o.o." both hit a label "ACME"; a `null` label needs a `null` result; `product_code`: compared after strip, case-insensitive, as the stock check does (`app/checks/rules.py:118`); `quantity`, `deadline`, `substitute_allowed`: equality; `price`: kind equal and value equal as Decimal) and, if `flagged=True`, the field is in `uncertain`. Otherwise `flagged_miss` when the field is in `uncertain`, else `silent_wrong`. A correct value that lacks a required flag is `silent_wrong`.
- `summarize(...)`: counts per field over (case, repeat, field) units, as hits / flagged misses / silent wrongs / total. Per tag, counts only the field the tag is about (a fixed map: `deadline_*`, `weekend_reference`, `year_rollover` → `deadline`; `price_*` → `price`; `substitute_*` → `substitute_allowed`; `customer_*` → `customer`; `quantity_variant` → `quantity`), so a price error is not diluted by the other five fields.

### Success Criteria:

#### Automated Verification:

- Case schema and loader tests pass (valid case, each rejected label, duplicate id, weekday and not-before-reference invariants): `docker compose run --rm backend uv run pytest tests/test_eval_fields_cases.py -q`
- Scoring tests pass (all three outcomes per field, required-flag rule, null labels, price equality, normalisation): `docker compose run --rm backend uv run pytest tests/test_eval_fields_scoring.py -q`
- Lint and format pass: `docker compose run --rm backend sh -c "uv run ruff check . && uv run ruff format --check ."`
- Type check passes: `docker compose run --rm backend uv run mypy app tests`

#### Manual Verification:

- Review the validator list against the label rules in the plan: no validator calls the deadline resolver.

**Implementation Note**: Pause for confirmation of the manual item before Phase 2. (Use `POSTGRES_HOST_PORT=55433` for compose when 5432 is taken.)

---

## Phase 2: Labelled case set

### Overview

The oracle: `backend/app/eval/fields/cases.json` of at least 40 hand-labelled phrasings, each with a rationale showing the arithmetic. Labels come from the written rules and calendar arithmetic, never from running the parser.

### Changes Required:

#### 1. The case file

**File**: `backend/app/eval/fields/cases.json` (new)

**Intent**: One short Polish inquiry per case (subject + body), varied in sentence structure, covering every field and the deadline phrasings that matter, including phrasings the resolver does not support.

**Contract**:
- Reference dates (`received_at`, Warsaw): at least Monday 2026-11-02, Thursday 2026-11-05, Friday 2026-11-06, a weekend day (2026-11-07), a December date for a year rollover, and a February date in a non-leap year for end-of-month.
- Deadline: ≥ 8 distinct supported phrases in varied sentences (e.g. `do piątku`, `do końca tygodnia`, `do końca miesiąca`, `w ciągu 14 dni`, `za 3 dni`, `jutro`, `pojutrze`, `do 20.11`); ≥ 4 unsupported or ambiguous phrases with the correct hand-derived label (`na piątek` → date; `w przyszłym tygodniu`, `na święta`, `jak najszybciej` → `null`, `flagged: true`); ≥ 2 cases with no deadline.
- Quantity: forms such as `80 szt.`, `80 sztuk`, a number written out in words, quantity absent (`null`, flagged). Product code in body and in subject only.
- Substitute: ≥ 3 stated-yes, ≥ 3 stated-no (different wordings, e.g. `tylko oryginał`, `bez zamienników`), ≥ 3 not stated.
- Price: none, best price, ≥ 2 discount percent (incl. a comma decimal), ≥ 2 target price per unit.
- Customer: signature with department, signature with a person and company, closing phrase only (`null`, flagged), company named in the body.
- Exclusion rule: a case whose correct reading needs a product decision is not added (see "What We're NOT Doing").

#### 2. Coverage test

**File**: `backend/tests/test_eval_fields_cases.py`

**Intent**: Extend the Phase 1 tests with checks on the built-in file.

**Contract**: the built-in set loads; ≥ 40 cases; the coverage minimums above hold (counted from tags and expected values); every case has a rationale; at least one case per `FieldTag`.

### Success Criteria:

#### Automated Verification:

- Built-in set loads and the coverage test passes: `docker compose run --rm backend uv run pytest tests/test_eval_fields_cases.py -q`
- Lint, format and types still pass: `docker compose run --rm backend sh -c "uv run ruff check . && uv run ruff format --check . && uv run mypy app tests"`

#### Manual Verification:

- Hand-check the label arithmetic of at least 10 cases chosen across deadline, price and customer (weekday and date in the rationale match a calendar), and confirm none was copied from a run of the parser.

---

## Phase 3: Runner, report and CLI

### Overview

Run the extractor over the set and write the report. DB-free.

### Changes Required:

#### 1. Runner

**File**: `backend/app/eval/fields/runner.py` (new)

**Intent**: For each case and repeat call the extractor, build the parsed fields with the real `build_parsed`, score them.

**Contract**:
- `run_field_eval(cases, extractor, *, repeats, pause_seconds, provider, model, cases_version) -> FieldRun`.
- Reference date from `reference_date_of(case.received_at)`; `extractor.extract(subject, body, reference_date)`; `build_parsed(result.extraction, reference_date)`; `score_case`.
- `ExtractionError` is recorded as a failed observation (class name, never message or inquiry text), counted separately and never as a hit; other exceptions propagate.
- `FieldObservation` keeps case id, repeat, the six outcomes, the parsed values (incl. `deadline_text`, `price_text`), the uncertain field names, duration in ms and token usage when `result.usage` is present. `FieldRun` keeps `started_at`, `finished_at`, `provider`, `model`, `extractor` name, `repeats`, `cases_sha256` (`app.eval.runner.cases_sha256`), observations.

#### 2. Report

**File**: `backend/app/eval/fields/report.py` (new)

**Intent**: JSON and Markdown report, comparable in spirit to the decision report but its own shape.

**Contract**: `write_report(run, out_dir) -> (md_path, json_path)` named `<date>-<provider>-<model>` (a `-HHMMSS` suffix on collision, like `app/eval/report.py`). Markdown sections: metadata; accuracy per field (hit / flagged miss / silent wrong); accuracy per tag; case table (phrase, expected, got, outcome per repeat); silent errors (case id, field, expected vs got); unstable (case, field) pairs with differing outcomes across repeats; failed extractor calls; methodology (the three-outcome rule and the oracle policy).

#### 3. CLI

**File**: `backend/app/eval/fields/__main__.py` (new)

**Intent**: `python -m app.eval.fields`.

**Contract**: flags `--repeats` (default 3), `--pause-seconds` (default 1.0), `--cases`, `--only CASE_ID...`, `--out` (default `eval_reports/fields`), `--allow-fake` (permits running when the provider is `fake` or has no key, exactly like `app/eval/__main__.py:84`; it does not force the regex extractor, which comes from `LLM_PROVIDER=fake`). Exit 2 when the provider is `fake` or has no key without `--allow-fake`, or for unknown `--only` ids; exit 0 otherwise even if some calls failed (like `app/eval/__main__.py`). Model name as in `app/eval/__main__.py:109-110`. No database access, no `--allow-remote-db`.

### Success Criteria:

#### Automated Verification:

- Runner, report and CLI tests pass with a scripted stub extractor (outcomes, failed call not a hit, unstable pairs, report files, exit codes, no DB): `docker compose run --rm backend uv run pytest tests/test_eval_fields_runner.py tests/test_eval_fields_report.py -q`
- Smoke run on the built-in set writes both files: `docker compose run --rm -e LLM_PROVIDER=fake backend uv run python -m app.eval.fields --allow-fake --repeats 1 --out /tmp/fields` (`-e LLM_PROVIDER=fake` keeps a key in `.env` from making this a paid LLM run)
- Lint, format and types pass: `docker compose run --rm backend sh -c "uv run ruff check . && uv run ruff format --check . && uv run mypy app tests"`
- Full backend gate passes on a temporary database: `docker compose exec -T db psql -U postgres -c "CREATE DATABASE check_tmp"`, then `docker compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@db:5432/check_tmp backend sh check.sh`, then `docker compose exec -T db psql -U postgres -c "DROP DATABASE check_tmp"`

#### Manual Verification:

- Read the Markdown of the smoke run: silent errors are easy to find and the per-field table is readable.

---

## Phase 4: Documentation and first baseline

### Overview

Make the eval usable by the next person and record what it found on the real model.

### Changes Required:

#### 1. Cookbook, README, test-plan status

**File**: `context/foundation/test-plan.md`, `README.md`

**Intent**: Replace the `TBD` in §6.2 with the procedure for adding a field case (label from rules, show the arithmetic in the rationale, the three outcomes, the exclusion rule, how to run). Update §3 row 2 (status, change folder `context/changes/testing-parser-field-eval/`), correct the change-folder paths of rows 1 and 3 to their archive paths, and update the §4 eval row. Add a §6.6 note for Phase 2 with the baseline result. Add a short README "Parser field eval" subsection under Quality gates (command, no DB, local only, not a gate).

**Contract**: §6.2 states that this eval is a measurement, that CI runs only stubbed tests, and that a change to the parser prompt (`app/parsing/openai_compatible.py`) or `app/parsing/{analyze,deadline}.py` should be followed by a run and a look at silent errors.

#### 2. First baseline report

**File**: `backend/eval_reports/fields/<date>-<provider>-<model>.{md,json}` (generated)

**Intent**: One real-provider run, 3 repeats, committed as the reference for later runs.

**Contract**: produced by the CLI with a configured provider (not `--allow-fake`); every silent error in it is triaged in §6.6 as either a label correction (fix `cases.json`, re-run) or a recorded parser gap (no parser change in this change).

### Success Criteria:

#### Automated Verification:

- No `TBD` remains in §6.2 and §3 row 2 is updated: `grep -n "TBD — see §3 Phase 2" context/foundation/test-plan.md` prints nothing
- Full backend gate still passes (including `test_latest_report_matches_the_case_file`): `docker compose exec -T db psql -U postgres -c "CREATE DATABASE check_tmp"`, then `docker compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@db:5432/check_tmp backend sh check.sh`, then `docker compose exec -T db psql -U postgres -c "DROP DATABASE check_tmp"`

#### Manual Verification:

- Run the real-provider eval and commit the report: `docker compose run --rm backend uv run python -m app.eval.fields --repeats 3` (needs `LLM_PROVIDER` and `LLM_API_KEY`).
- Triage the silent errors in the baseline and record the outcome in test-plan §6.6.

---

## Testing Strategy

### Unit Tests:

- Case validators (each rejected label), scoring outcomes per field, required-flag rule, price equality, normalisation, summaries.
- Runner with a scripted stub extractor (the pattern of `tests/test_eval_runner.py:59-74`): outcomes, failed calls, repeats, unstable pairs, no DB.
- Report content and file naming; CLI exit codes.

### Integration Tests:

- The regex extractor over the full built-in set runs without exceptions (pipeline smoke, not an accuracy assertion).

### Manual Testing Steps:

1. Hand-check label arithmetic of 10 cases against a calendar.
2. Run the real-provider eval and read the silent-error list.

## Performance Considerations

One LLM call per case per repeat (about 40 cases × 3 repeats = 120 calls, no orchestrator or recommender), far cheaper than the ~36-minute decision eval; the pause between calls bounds rate-limit risk. Real run time and cost are unmeasured until the baseline.

## Migration Notes

None: no schema, no `ParsedFields` change (the JSONB lesson in `context/foundation/lessons.md:5-9` does not apply), no change to existing reports or tests.

## References

- Related research: `context/changes/testing-parser-field-eval/research.md`
- Test plan: `context/foundation/test-plan.md` (§2 risk #4, §3 row 2, §6.2)
- Decision eval pattern: `backend/app/eval/{cases,runner,report,__main__}.py`
- Parser: `backend/app/parsing/{extractor,analyze,deadline,schema}.py`
- Archived parser build: `context/archive/2026-11-10-parse-inquiry/plan.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Case schema, loader and field scoring

#### Automated

- [x] 1.1 Case schema and loader tests pass
- [x] 1.2 Scoring tests pass
- [x] 1.3 Lint and format pass
- [x] 1.4 Type check passes

#### Manual

- [x] 1.5 No validator calls the deadline resolver

### Phase 2: Labelled case set

#### Automated

- [ ] 2.1 Built-in set loads and the coverage test passes
- [ ] 2.2 Lint, format and types still pass

#### Manual

- [ ] 2.3 Label arithmetic of at least 10 cases hand-checked against a calendar

### Phase 3: Runner, report and CLI

#### Automated

- [ ] 3.1 Runner, report and CLI tests pass with a stub extractor
- [ ] 3.2 Smoke run on the built-in set writes both files
- [ ] 3.3 Lint, format and types pass
- [ ] 3.4 Full backend gate passes on a temporary database

#### Manual

- [ ] 3.5 Smoke-run Markdown is readable and silent errors are easy to find

### Phase 4: Documentation and first baseline

#### Automated

- [ ] 4.1 No TBD remains in test-plan §6.2 and §3 row 2 is updated
- [ ] 4.2 Full backend gate still passes

#### Manual

- [ ] 4.3 Real-provider baseline run committed
- [ ] 4.4 Silent errors in the baseline triaged and recorded in test-plan §6.6
