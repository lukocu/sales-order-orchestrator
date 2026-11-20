---
date: 2026-11-20
researcher: Claude (Sonnet 5.5)
git_commit: 4d9376b26a1c049ebceb1a47ae67ee4813106b9f
branch: test/eval-dataset-expansion
repository: sales-order-orchestrator
topic: "Test-plan Phase 2 — parser field eval: what exists, what a per-field eval must ground, where it plugs in"
tags: [research, codebase, parsing, eval, test-plan, risk-4]
status: complete
last_updated: 2026-11-20
last_updated_by: Claude (Sonnet 5.5)
---

# Research: Parser field eval (test-plan §3 Phase 2, risk #4)

**Date**: 2026-11-20
**Git Commit**: 4d9376b (working tree: only `context/changes/testing-parser-field-eval/` untracked)
**Branch**: test/eval-dataset-expansion

## Research Question

Test-plan Phase 2: "Jakość odczytu każdego pola jest mierzona osobno i taniej niż pełny przepływ" (risk #4: parser misreads a field under a different phrasing and poisons the flow). The Risk Response Guidance row asks research to ground: the parser output contract, marking of uncertain fields, and the reference date for relative deadlines (`context/foundation/test-plan.md:63`). This document answers: what is the contract, what do existing tests/evals already measure, what could a field eval reuse, and which decisions remain for `/10x-plan`.

## Summary

1. **The parser has two halves with different testability.** A deterministic half (reference date, deadline resolution, uncertain-field rules, price/qty/text validation) lives in code (`analyze.py`, `deadline.py`), and an LLM half reads six fields from free text (`openai_compatible.py`). Unit tests already cover the deterministic half densely with hand-built inputs. The LLM half is covered only with a mock transport — no test judges extraction quality (`tests/test_parsing_extractors.py:185-300`, per subagent read). That quality gap is what risk #4 is about.
2. **The current eval does not measure the parser.** For every non-adversarial case the runner parses with the fake (regex) extractor and then overwrites the result with the golden fields (`runner.py:414-440`, subagent anchor). For the 4 adversarial cases the configured extractor runs once, and only 5 fields are compared (`price_kind`, `price_value`, `quantity`, `product_code`, `substitute_allowed`; `runner.py:85-91`, verified). `customer`, `deadline`, `deadline_text`, `price_text` are never compared, and a field difference alone is not scored as a miss (only a changed checks outcome is, `runner.py:384-396`).
3. **Golden labels exist but are an unsafe oracle for relative dates.** All 32 cases in `cases.json` carry the 9 `ParsedFields` golden values (`cases.py:69-88`). The `deadline_text` values in them are 12 distinct phrases (10 cases have `null`, counted by grep in `cases.json`); every non-null phrase is a form the deadline resolver recognises, except "jak najszybciej" (1 case, expected unresolved). They were written to feed the pipeline, not to stress phrasing. They cannot serve alone as a "different phrasing" set, and any expected date must be computed independently of `resolve_deadline` (test-plan anti-pattern, `test-plan.md:63`).
4. **A field eval is cheap and DB-free.** `extract()` → `build_parsed()` → compare needs no DB, no planner, no recommender (`extractor.py:48-52` protocol, `analyze.py:28`, `service.py:126-128`). Cost is one LLM call per case per repeat.
5. **It cannot reuse the existing report/compare machinery as-is.** `EvalReport`, `ArmRun`, `Score` and `compare.py` are decision/arm-shaped (`scoring.py:24`, `compare.py:54,178-187`). Reusable pieces: `cases_sha256`, the `Accuracy` model, report slug/row helpers (private). Editing `cases.json` forces a re-run and re-commit of the 36-minute full eval because of the CI consistency test (`tests/test_eval_compare.py:675-695`), so a separate case file for fields avoids coupling.
6. **Language/scope facts that bound the eval:** the parser handles Polish only (prompt, regexes, deadline grammar); deadline resolution does not recognise "w przyszłym tygodniu", English phrases, nominative weekdays or "na <day>". The fake extractor never produces `target_price` and always returns an empty `uncertain` list.

## Detailed Findings

### Output contract (what a field is)

- `ParsedFields` (`app/parsing/schema.py:24-53`; `extra="forbid"`, all required): `customer`, `product_code`, `quantity` (int ≥ 1), `deadline` (date), `deadline_text`, `substitute_allowed` (bool|None; None = not stated), `price_kind` ∈ {none, best_price, discount_percent, target_price}, `price_value` (Decimal), `price_text`. A validator ties `price_value` to the kind (discount 0<v≤100, target >0, finite).
- Raw extractor output `ModelExtraction` (`schema.py:63-81`): same text fields, plus `deadline_date` (ISO string computed by the model), `price_value` as float, and `uncertain: list[{field, reason}]`.
- User-visible fields are six (`FieldName`, `schema.py:14-16`): customer, product_code, quantity, deadline, substitute_allowed, price (deadline = deadline+deadline_text, price = kind+value+text; `service.py:75`).
- Uncertainty is marked by an empty value plus an `uncertain: dict[FieldName, str]` map built in `build_parsed` (`analyze.py:28-76`): "Missing" for blank customer/product/quantity; "Invalid quantity N"; truncation over 200 chars; "Not stated" for `substitute_allowed=None`; deadline reasons (rules vs model disagreement, ambiguous, "resolved by model only", "could not resolve"); price reasons (number missing/out of range → kind reset to `none`); model notes appended as "Model: …". `price_kind="none"` is never flagged. These are code rules, not model self-assessment (`context/archive/2026-11-10-parse-inquiry/plan.md:110-120`).

### Reference date and relative deadlines

- Reference date = `received_at` converted to Europe/Warsaw, taken in code (`service.py:126-128`, tz constant `:71`), then passed to the extractor and stored on the analysis (`service.py:140-172`). Decision source: parse-inquiry plan (research said "no document decides this", `context/archive/2026-11-10-parse-inquiry/research.md:33`); the PRD is silent.
- `resolve_deadline(text, reference)` (`deadline.py:36-41`) recognises, for Polish text only: "do końca tygodnia", "do końca miesiąca", "do <weekday genitive>", "w ciągu N dni", "za N dni", "w ciągu tygodnia", "jutro", "pojutrze", `D.M[.YYYY]`. Ambiguity flags: same weekday as the reference; end-of-week from a weekend; year rollover. Not recognised → `None`: English phrases, "w przyszłym tygodniu/roku", "jak najszybciej".
- When the phrase is recognised the code date always wins over the model date; the model date is a cross-check/fallback (`analyze.py:99-113`). So for deadline, the LLM's responsibility is **extracting the phrase verbatim** (`deadline_text`), not arithmetic. A field eval of `deadline` therefore has two separable questions: did the extractor copy the right phrase, and does the resolver map phrase+reference to the right date.
- The deadline resolver is already covered phrase by phrase in `tests/test_parsing_deadline.py` (references Mon 2026-11-02, Fri 11-06, Sat 11-07; all weekdays; month/year boundaries; unrecognised phrases). No test uses English or "next week".

### Extractors

- `RuleBasedExtractor` ("fake", deterministic; `fake.py:25-49`): regex for quantity+code (`(\d+)\s*szt\.?\s*([A-Z]{2,4}-\d{2,4})`, body then subject), deadline phrase, substitute yes/no phrases, price (`rabat N%` / `najlepsz* cen*` only), customer = last non-empty line unless a closing phrase; `uncertain` always `[]`. Never emits `target_price`.
- `OpenAICompatibleExtractor` (groq/openrouter; `openai_compatible.py:56-99`): Polish system prompt (`:27-53`) with injection guard, strict JSON schema, temperature 0; subject truncated to 500 and body to 8000 chars. Selected by `get_extractor(settings)` (`extractor.py:67-84`); no key → `UnconfiguredExtractor` raising. The eval baseline model is openrouter `qwen/qwen3-30b-a3b-instruct-2507` (report filenames in `backend/eval_reports/`), while the code default for openrouter is a different model (`app/llm/client.py` DEFAULT_MODELS, per subagent), so model is chosen by `LLM_MODEL`.
- No test covers LLM extraction quality, `target_price` extraction by an extractor, customer extraction beyond the 4 seed signatures, English text, or `substitute_allowed` beyond seed phrases (subagent gap list over `tests/test_parsing_*.py`).

### What the current eval measures about the parser

- Runner setup for non-adversarial cases: `analyze_inquiry` with the fake extractor, then `save_corrections` with golden `case.fields` (`runner.py:414-440`). Parser output is discarded.
- Adversarial cases only: configured extractor, `ParseCheck.differing` on 5 fields, recorded in `EvalRun.parse_checks`, shown as "matches"/field list (`report.py` `_adversarial`); report states "The parser is excluded from the comparison" (`report.py:412-417`). Baseline 2026-11-20: all 4 adversarial parse checks "matches" (`test-plan.md:208`).
- Explicit deferral: dataset-expansion plan assigns "scoring parser accuracy per field for every case" to this phase (`context/archive/2026-11-20-testing-eval-dataset-expansion/plan.md:48`).

### Eval harness plug-in points

- Cases: `EvalCase` has `fields: ParsedFields` golden values plus decision labels (`cases.py:69-88`); `load_cases` validates (`:121-134`). `cases.json` has 32 cases; `price_kind` distribution none 20 / discount_percent 8 / target_price 3 / best_price 1; `substitute_allowed` null 18 / true 8 / false 6 (grep counts in `cases.json`).
- Reports: `write_report` produces `<date>-<provider>-<model>.{md,json}` in `eval_reports/` (`report.py:131-159`). `compare.load_report` skips files that fail `EvalReport` validation with a warning (`compare.py:371-379`), and the CI test takes the newest valid report (`test_eval_compare.py:675-695`) — a differently shaped JSON in that directory would be skipped, not break either. Not verified by running.
- Reusable: `cases_sha256` (`runner.py:133`), `load_cases`, `Accuracy` (`scoring.py:93-103`). Not reusable as-is: `EvalReport`/`ArmRun`/`Score`/`Observation`, `compare` (key = (case, arm), `full_hit`).
- Gate coupling: CI test fails whenever `cases.json` changes until a new full decision-eval report is committed (README ~669-676; `test_eval_compare.py:675-695`). A field eval that appends cases to `cases.json` inherits that cost; a separate file does not.
- CI has no LLM secrets and does not run `app.eval` (`.github/workflows/ci.yml`, per subagent grep). Field eval against the real model would be a local, manual run like the decision eval; a deterministic subset (fake extractor, or recorded extractor outputs) is the only CI-capable form.
- A leftover `backend/tests/fixtures/synthetic_inquiries.jsonl` exists (4 records with `expected_extraction`/`expected_parsed`, per archive `context/archive/2026-11-13-workflow-vs-orchestrator-eval/research.md:164`); not opened this session, usage unknown (no consumer found by the history agent).

## Code References

- `backend/app/parsing/schema.py:14-93` — `FieldName`, `ParsedFields`, `ModelExtraction`, JSON schema
- `backend/app/parsing/analyze.py:28-136` — `build_parsed`, uncertain rules, `_deadline`, `_price`
- `backend/app/parsing/deadline.py:18-107` — phrase regex, `resolve_deadline`
- `backend/app/parsing/fake.py:15-91` — regex extractor
- `backend/app/parsing/openai_compatible.py:14-129` — prompt, limits and request
- `backend/app/parsing/extractor.py:18-84` — `ExtractionResult`, errors, `UnconfiguredExtractor`, `get_extractor`
- `backend/app/parsing/service.py:71-172` — reference timezone, `reference_date_of`, `analyze_inquiry`
- `backend/app/eval/runner.py:85-91,357-397,414-440` — parse-check fields, adversarial setup, golden-field overwrite
- `backend/app/eval/cases.py:69-156` — case model and validation
- `backend/app/eval/report.py:131-159,303-340,412-417` — report writing, parse-check rendering
- `backend/app/eval/compare.py:54,178-187,371-379` — unit, compatibility, report loading
- `backend/tests/test_eval_compare.py:675-695` — CI consistency test
- `backend/tests/test_parsing_{deadline,analyze,extractors,models}.py` — existing coverage

## Architecture Insights

- Parser = LLM reads text → deterministic `build_parsed` normalises, resolves dates and flags uncertainty. This split dictates the eval: LLM-reading fields (customer, product_code, quantity, deadline_text, substitute_allowed, price kind/value/text) need a real extractor and phrasing variety; date resolution and flagging are pure functions already unit-tested.
- Uncertainty marking is itself a measurable output: for a poorly specified phrasing the correct result may be "empty value + flag", not a value. A per-field score needs three outcomes (right value, correctly empty/flagged, wrong value silently accepted); the third is the risk-#4 failure ("poisons the flow"), the second is acceptable under PRD FR-002 ("niepewne pola są oznaczone", `prd.md:90`).
- The PRD sets no accuracy number for parsing; thresholds are a plan decision.
- Lesson on JSONB model changes (`context/foundation/lessons.md:5-9`) applies only if the plan changes `ParsedFields`; an eval that only reads it does not.

## Historical Context (from prior changes)

- `context/archive/2026-11-10-parse-inquiry/plan.md:51,89-120` — reference date = `received_at` in Europe/Warsaw; deadline resolved in code because LLM date arithmetic is weak (research.md:104); uncertainty by code rules. Supported.
- `context/archive/2026-11-10-parse-inquiry/plan-brief.md` — storage kept model fields vs current fields explicitly as eval material ("materiał dla ewaluacji S-10"). Supported (history agent read).
- `context/archive/2026-11-10-parse-inquiry/reviews/impl-review.md` F5 — regex customer = last body line; fixed so a closing phrase gives `None`. Partial: current fake still depends on the last line (`fake.py:83-91`).
- `context/archive/2026-11-14-test-mailbox-ingest/research.md:36,84-88` — regex parser assumes plain Polish text with signature last; real mail is normalised to plain text first. Supported as constraint on realistic phrasings.
- `context/archive/2026-11-20-testing-eval-dataset-expansion/plan.md:17,48,159-182` and `plan-brief.md:47` — parser deliberately skipped for non-adversarial cases (golden fields replace extraction), deferred to this phase; adversarial parse check built with 5 fields and no deadline. Supported by current `runner.py`.
- `context/archive/2026-11-20-testing-eval-dataset-expansion/research.md:54,234-238` — oracle problem; options included "a separate mode that runs the parser … overlaps Phase 2". Supported.
- Groq/Polish extraction quality "nie potwierdzona benchmarkiem" (`parse-inquiry/plan-brief.md` risks, per history agent): still unmeasured, which is this phase's gap.

## Related Research

- `context/archive/2026-11-20-testing-eval-dataset-expansion/research.md`
- `context/archive/2026-11-20-testing-eval-regression-gate/research.md` (baseline/compare design; parser only mentioned in passing)
- `context/archive/2026-11-10-parse-inquiry/research.md`

## Open Questions

Decisions for `/10x-plan` (research cannot settle them):

1. **Case source**: new dedicated file (e.g. `eval/field_cases.json`) with many phrasings per field vs. reusing the 32 golden `fields` in `cases.json`. Research favours a separate file (avoids the CI re-baseline coupling and the narrow-phrase problem) but this is a product/scope choice.
2. **Oracle for relative dates**: expected dates must be hand/independently derived from (phrase, reference date); the existing `resolve_deadline` cannot be the oracle. Which phrase set is in scope — only what the resolver supports, or also known-unsupported phrases ("w przyszłym tygodniu", "na piątek", English) as expected-unresolved/flagged?
3. **What "hit" means per field**: exact match; value-or-flagged; or three-way (correct / flagged-empty / silently wrong). How `deadline_text` (verbatim phrase) and `price_text` are compared (normalisation), and whether `customer` is in scope.
4. **Extractor under test**: real LLM only (local, manual, costs tokens), the fake regex extractor (deterministic, CI-capable but a different code path), or both. Number of repeats for the LLM (temperature 0 but model non-determinism unmeasured).
5. **Reporting and gating**: own report format vs. extending `EvalReport`; whether to extend `compare` (per field-case baseline) or leave Phase 2 as measurement only; whether a CI-run deterministic subset is wanted.
6. **Unmeasured**: LLM extraction quality on Polish (no data), actual run time/cost of a field eval, whether `tests/fixtures/synthetic_inquiries.jsonl` still has any role, whether golden `deadline` values were derived against the Warsaw reference date for all 32 cases.

Evidence gaps: no code was executed in this research. `schema.py`, `analyze.py`, `deadline.py`, `fake.py`, `openai_compatible.py`, `extractor.py`, `cases.py` and `eval/__main__.py` were re-read in full by the main agent while planning (line anchors above are from that read; the first subagent's line numbers had been wrong and were replaced). Claims about `tests/test_parsing_*.py` contents and `service.py` details beyond lines 71-172 are from subagent reads only.
