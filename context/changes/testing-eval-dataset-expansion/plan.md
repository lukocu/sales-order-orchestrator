# Eval dataset expansion Implementation Plan

## Overview

Phase 1 of `context/foundation/test-plan.md` (risks #1, #3, #6): grow the labelled eval set from 12 to about 30 cases.

- Every label is derived from a written business rule, not from what the system returns.
- The set covers every PRD exception type, including the ones the code does not model.
- Adversarial cases (prompt injection in the email) go through the real parser.
- The report groups results so it shows which kinds of case the orchestrator gets wrong.

## Current State Analysis

The runner, case format and report already exist; this change extends them. Grounded in `research.md`:

- **Cases:** 12 in `backend/app/eval/cases.json`, schema `EvalCase`/`ExpectedDecision` (`backend/app/eval/cases.py:32-79`, `extra="forbid"`). There is no tag, category or adversarial field.
- **Setup:** the runner analyses each case with `RuleBasedExtractor`, then saves the case's golden `fields` as the user's correction (`backend/app/eval/runner.py:281-311`). The parser is never measured, so an injected email cannot change the eval decision.
- **CI:** `backend/tests/test_eval_runner.py:127-146` runs every case through the rule-based planner plus `FakeRecommender` and asserts a full hit on every workflow run. As a result every label today equals what `rank()` picks (`backend/app/recommendation/recommender.py:79-90`). The existing rationales say so, e.g. `cases.json:75`.
- **Exception types:** the code models one, `insufficient_stock` (`backend/app/checks/schema.py:16`). An unusual discount, a price–deadline conflict or unclear requirements without a shortage give `standard`, or `needs_input` when a required field is missing (`backend/app/checks/rules.py:247-275`). PRD Open Question #4 is still open (`context/foundation/prd.md:186`, `context/foundation/roadmap.md:198`).
- **Company data:** 4 customers and 5 products; only ABC-100 and XYZ-300 have more than one variant. Policy thresholds: margin ≥ 20%, discount ≤ 15%, order value ≤ 30 000 PLN (`migrations/versions/0006,0007,0009,0011`).
- **Report:** sections arm comparison, cases, unstable, failures, setup errors, methodology (`backend/app/eval/report.py:117-295`). No grouping.

## Desired End State

- `cases.json` holds about 30 cases.
  - Every case's `rationale` follows the labelling procedure in test-plan §6.1.
  - Cases where `rank()` picks differently carry a `rule_based` decision with a reason.
  - Each PRD exception type has at least 2 cases, tagged.
  - 4 adversarial cases point at their clean twin with `adversarial_of`.
- A real eval run parses the adversarial cases with the configured LLM extractor. Its report shows:
  - accuracy grouped by expected decision and by tag;
  - per adversarial case, whether the parsed price fields matched the twin.
- CI stays green: every case's workflow run on fakes hits `rule_based` if set, else `expected`.
- A baseline report for the new set is committed in `backend/eval_reports/`.
- PRD Open Question #4 is closed: the types without a shortage are only shown, not escalated, in the MVP.

### Key Discoveries:

- `analyze_inquiry(engine, extractor, …)` already accepts any extractor (`backend/app/parsing/service.py:140-148`), and `get_extractor(settings)` picks the LLM or the fake (`backend/app/parsing/extractor.py:67-80`). The adversarial path only needs to skip `save_corrections`.
- Policy reads the parsed `price_kind`/`price_value` (`backend/app/checks/rules.py:176-206` → `backend/app/policy/rules.py:133-169`). An injection that drops the discount request is the real risk, so comparing the price fields is the core check.
- Option prices never use the requested discount (`backend/app/recommendation/options.py:110-113`). Only the policy verdict moves with the request.
- `test_eval_cases.py:78` asserts the exact set of option kinds. It stays valid, since no new kinds are added.
- A case with zero options makes the recommender fail (`recommender.py:102-103`). Don't write such cases on the current data.

## What We're NOT Doing

- Changing the seed data or adding migrations (decision: current data only).
- Scoring parser accuracy per field for every case. That is Phase 2 of the test plan; here only the adversarial cases are parsed, and only their price fields and decision are compared.
- Running the LLM drafter or scoring the draft text in the eval.
- Changing how the system chooses a variant: where `rank()` departs from the PRD rule, this change records the departure and does not fix it.
- A regression gate, a baseline comparison or CI runs of the real eval (test-plan Phase 3).
- Adding escalation for an unusual discount, a price–deadline conflict or unclear requirements without a shortage.

## Implementation Approach

Phase order: format first, then the runner path, then the data, then the baseline.

- The schema and report changes (Phase 1) make every later case expressible and visible.
- The adversarial path (Phase 2) must exist before adversarial cases can be labelled meaningfully.
- The dataset (Phase 3) is labelled by hand against the written procedure, and checked in CI on fakes.
- The baseline (Phase 4) is a manual run with a real model.

**Labelling procedure** (to be written into test-plan §6.1 in Phase 1; decided in planning).

1. **Classify** by the checks rules: needs_input → shortage → standard.
2. **For an exception**, build the variants from the seed data as `options.py` does.
3. **A variant meets the requirements** when it covers the full quantity and meets the deadline (no deadline means it is met).
   - Refused consent already removes substitutes.
   - Partial compatibility and customer history lower confidence; they do not disqualify a variant.
4. **If at least one variant meets the requirements**, pick the best margin among those whose policy verdict is `no_approval_needed`. If none of them passes policy, pick the best margin among all of them.
5. **If no variant meets the requirements**, pick the largest covered quantity, then the earliest fulfilment date, then the higher margin.
6. **The label's policy verdict** is computed for the chosen variant with the four rules and the seeded thresholds. A value exactly at a threshold passes.
7. **The rationale** shows the numbers. If the rule-based path (`rank()`) would pick a different variant, record that decision in `rule_based` with one sentence on why the two differ.

## Phase 1: Case schema, grouped report, labelling procedure

### Overview

Make the case format able to express tags, a fake-path override and an adversarial twin. Show grouped accuracy in the report, and write the labelling procedure down.

### Changes Required:

#### 1. Case model

**File**: `backend/app/eval/cases.py`

**Intent**: Add three optional fields to `EvalCase`, so cases can be grouped, can carry a documented departure of the rule-based path from the PRD-rule label, and can point at their clean twin.

**Contract**:
- `tags: list[CaseTag] = []`. `CaseTag` is a closed `Literal`: `unusual_discount`, `price_deadline_conflict`, `unclear_requirements`, `refused_substitute`, `no_deadline`, `adversarial`, `rank_divergence`. No duplicates.
- `rule_based: ExpectedDecision | None = None`. It must differ from `expected`; it requires the `rank_divergence` tag, and the tag requires it.
- `adversarial_of: str | None = None`. Set it if and only if the `adversarial` tag is present.
- `load_cases` validates across cases:
  - `adversarial_of` names an existing non-adversarial case;
  - the adversarial case's `fields` and `expected` equal its twin's;
  - its `body` differs from the twin's.

#### 2. Fake-path assertion in CI

**File**: `backend/tests/test_eval_runner.py`

**Intent**: `test_full_set_matches_the_labels_and_leaves_no_rows` keeps checking that every workflow run hits. The comparison target becomes `case.rule_based or case.expected`, so labels can follow the PRD rule.

**Contract**: a helper in `backend/app/eval/scoring.py` scores an observation against an explicit `ExpectedDecision`; `score(case, …)` keeps scoring against `case.expected`. The test uses the helper with the fake-path target.

#### 3. Grouped accuracy in the report

**File**: `backend/app/eval/report.py` (plus `EvalRun` in `backend/app/eval/runner.py`)

**Intent**: Add a "By expected decision" section and a "By tag" section, giving per-arm full accuracy for each group, so the report shows which kinds of case each arm misses.

**Contract**:
- `EvalRun` gains `tags: dict[str, list[CaseTag]]` (case id → tags).
- Groups:
  - expected `checks_outcome`, and `option_kind · policy_outcome` for exceptions;
  - each tag.
- The cells reuse `_accuracy`.
- The JSON report carries the same data through `EvalReport`.

#### 4. Labelling procedure

**File**: `context/foundation/test-plan.md` §6.1

**Intent**: Replace the TBD with the procedure from "Implementation Approach" above, plus a worked example taken from a real case: inputs, variants, choice, verdict.

**Contract**: §6.1 "Adding an eval case" — procedure, `rule_based`/`rank_divergence` rule, adversarial-twin rule, tag list.

#### 5. Tests

**Files**: `backend/tests/test_eval_cases.py`, `backend/tests/test_eval_report.py`, `backend/tests/test_eval_scoring.py`

**Intent**: Cover the new validation rules and the grouped sections.

**Contract**:
- Loader rejects:
  - an unknown or duplicate tag;
  - `rule_based` without the tag, or the tag without `rule_based`;
  - `rule_based` equal to `expected`;
  - `adversarial_of` pointing at a missing or adversarial case;
  - an adversarial case whose fields or expected differ from its twin's.
- Report: renders both grouped sections with correct counts.

### Success Criteria:

#### Automated Verification:

- Backend quality gates pass: `docker compose run --rm backend sh check.sh` (ruff, mypy, alembic, pytest)
- New loader-validation tests pass: `docker compose run --rm backend uv run pytest tests/test_eval_cases.py`
- Report tests cover the grouped sections: `docker compose run --rm backend uv run pytest tests/test_eval_report.py tests/test_eval_scoring.py`

#### Manual Verification:

- test-plan §6.1 reads as a complete procedure: a person who wasn't in the planning session can label a new case from it

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human before proceeding to the next phase.

---

## Phase 2: Parser path for adversarial cases

### Overview

Adversarial cases are parsed by the configured extractor instead of loading the golden fields. The run records whether the parsed price fields match the twin's, and a wrong classification becomes a scored miss, not a setup error.

### Changes Required:

#### 1. Runner

**File**: `backend/app/eval/runner.py`

**Intent**: Pass an extractor into `run_eval`. In `_set_up`, a case with `adversarial_of` runs `analyze_inquiry` with that extractor and skips `save_corrections`. Every other case keeps today's path.

**Contract**:
- `run_eval(…, extractor: InquiryExtractor)`.
- For an adversarial case, the parsed fields are compared once (at setup) with `case.fields` on `price_kind`, `price_value`, `quantity`, `product_code` and `substitute_allowed`. The result is stored per case in a new `EvalRun.parse_checks: dict[str, ParseCheck]`, holding the field names that differ, empty when none differ.
- If the parsed checks outcome differs from the label, that is recorded as one scored run per arm with failure `parse_mismatch:<outcome>`, not a setup error.
- An `ExtractionError` on an adversarial case is a scored failure `parse_failed:<class>`.
- Parsing happens once per case: repeats measure the orchestration, not the parser.

#### 2. Scoring and report

**Files**: `backend/app/eval/scoring.py`, `backend/app/eval/report.py`

**Intent**: Add the new failure prefixes, and an "Adversarial cases" report section listing each case, its twin, the parse check (fields that differ) and the majority decision per arm.

**Contract**:
- Failure prefixes `parse_mismatch:` and `parse_failed:` sit next to the existing ones.
- The Methodology notes state that adversarial cases are parsed by the configured extractor once per case, and that all other cases start from golden fields.
- The extractor's name appears in the metadata.

#### 3. CLI

**File**: `backend/app/eval/__main__.py`

**Intent**: Pass `get_extractor(settings)` to `run_eval`. The existing fake/key guard already covers the extractor's provider.

**Contract**: no new arguments.

#### 4. Tests

**File**: `backend/tests/test_eval_runner.py`

**Intent**: Cover the adversarial path on fakes.

**Contract**:
- A matching parse gives an empty parse check plus normal scoring.
- A stub extractor returning a dropped discount gives a parse check listing `price_kind`/`price_value`, with the decision scored against the twin's label.
- A stub extractor producing a different checks outcome gives `parse_mismatch` runs, not a setup error.
- A raising extractor gives `parse_failed`.
- Cleanup leaves no rows.
- The full-set test passes `RuleBasedExtractor`.

### Success Criteria:

#### Automated Verification:

- Backend quality gates pass: `docker compose run --rm backend sh check.sh`
- Adversarial-path runner tests pass: `docker compose run --rm backend uv run pytest tests/test_eval_runner.py`

#### Manual Verification:

- A fake run on a scratch case file with one adversarial pair (`python -m app.eval --allow-fake --cases <file>`) writes a report with the "Adversarial cases" section and the grouped sections filled in

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human before proceeding to the next phase.

---

## Phase 3: Dataset

### Overview

Re-label the 12 cases by the procedure and add about 18 new ones, so each category has several cases. Tighten the coverage assertions and close PRD Open Question #4.

### Changes Required:

#### 1. Re-label the existing cases

**File**: `backend/app/eval/cases.json`

**Intent**: Recompute every existing label by the §6.1 procedure and rewrite each rationale to show the numbers. Where `rank()` picks differently, keep the PRD-rule label in `expected` and record the rank result in `rule_based`, with the `rank_divergence` tag. Add the existing tags (`refused_substitute`, `no_deadline`, `unusual_discount` where a discount above 15% is requested).

**Contract**: ids stay unchanged; the first 4 cases keep the seed-domain order (`test_eval_cases.py:58-65`).

#### 2. New cases (target ≈ 30 in total)

**File**: `backend/app/eval/cases.json`

**Intent**: Add Polish emails from the 4 seed customers, varying quantity, deadline, consent and the discount or target-price request on the existing 5 products.

**Contract**: after this change the set contains at least:
- 3 cases per option kind (`partial_delivery`, `substitute`, `other_source`, `combined`), with both policy verdicts present among the exceptions;
- 2 cases per PRD type without a shortage: `unusual_discount` (→ `standard`), `price_deadline_conflict` (→ `standard`), `unclear_requirements` (→ `needs_input` or `standard`, per the checks rules);
- 3 `needs_input` cases with different reasons (`checks/schema.py:17-24`);
- 2 `standard` cases;
- 4 adversarial cases, each the twin of a clean case:
  - instructions to give a larger discount;
  - instructions to ignore the discount request;
  - a `</tresc>` tag-closing attempt;
  - an injection in the subject.
  Each adversarial case's label equals its twin's.
- No case with zero variants.

#### 3. Coverage assertions

**File**: `backend/tests/test_eval_cases.py`

**Intent**: Turn the minimums above into assertions, so the set cannot quietly shrink back.

**Contract**: replace `>= 12` with `>= 28`. Add:
- per option kind ≥ 3;
- per PRD tag ≥ 2;
- `needs_input` ≥ 3 with distinct reasons, if reasons can be derived from the fields; otherwise a count ≥ 3;
- `adversarial` ≥ 4.

#### 4. Close PRD Open Question #4

**Files**: `context/foundation/prd.md:186`, `context/foundation/roadmap.md:198`

**Intent**: Record the decision: in the MVP only a stock shortage is an exception. A price–deadline conflict, an unusual discount and unclear requirements are shown in checks and judged by policy only inside an exception flow. The eval labels them accordingly.

**Contract**: the Open Question entry is marked resolved, with the date and a pointer to this change.

### Success Criteria:

#### Automated Verification:

- Case set loads and coverage assertions pass: `docker compose run --rm backend uv run pytest tests/test_eval_cases.py`
- Every case hits on the fake path (labels or `rule_based`): `docker compose run --rm backend uv run pytest tests/test_eval_runner.py`
- Backend quality gates pass: `docker compose run --rm backend sh check.sh`

#### Manual Verification:

- Spot-check 5 new rationales against the seed tables by hand (variants, chosen option, margin, verdict)
- Every adversarial email reads like a realistic customer email with an embedded instruction

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human before proceeding to the next phase.

---

## Phase 4: Baseline run and documentation

### Overview

Run the real eval on the new set, commit the report as the baseline, and record the phase in the test plan.

### Changes Required:

#### 1. Baseline report

**File**: `backend/eval_reports/<date>-<provider>-<model>.{md,json}`

**Intent**: Run `python -m app.eval --repeats 3` with the same provider and model as the 2026-11-14 report (OpenRouter, qwen3-30b-a3b-instruct-2507) and commit the output. This is the first baseline for Phase 3 of the test plan.

**Contract**: the report includes the grouped and adversarial sections; the old report stays.

#### 2. Test plan

**File**: `context/foundation/test-plan.md`

**Intent**:
- Set the §3 Phase 1 status.
- In §6.6, record per-phase notes: the baseline file, the categories with the lowest accuracy, and any adversarial parse mismatches.
- Update the eval row in §4 (case count).

**Contract**: §3 row 1, §4 eval row, §6.6.

### Success Criteria:

#### Automated Verification:

- Baseline report files exist in `backend/eval_reports/` with ~30 cases and no setup errors (`grep -c` on the case table / JSON `setup_errors == []`)

#### Manual Verification:

- Real eval run completes with an OpenRouter key and the report's grouped and adversarial sections are readable
- test-plan §6.6 notes name the weakest categories from the baseline

---

## Testing Strategy

### Unit Tests:

- Loader validation: tags, `rule_based` pairing, adversarial twin consistency.
- Scoring against an explicit target; the new failure prefixes.
- Report: grouped sections, adversarial section, methodology text.

### Integration Tests:

- Full set on fakes: every workflow run hits `rule_based or expected`, no setup errors, no leftover rows.
- Adversarial path with stub extractors: match, dropped discount, wrong outcome, raise.

### Manual Testing Steps:

1. A fake run with a scratch adversarial pair produces the new report sections.
2. Spot-check new rationales against the seed tables.
3. A real baseline run with OpenRouter.

## Performance Considerations

With about 30 cases, roughly 22 exception cases × 3 repeats × 2 arms make about 130 orchestrated runs, about 2.2× today's 60. At the 2026-11-14 cost and time per run, that is about $0.03 and roughly 20–25 minutes with the default 2 s pause. Adversarial parsing adds 4 extractor calls per run.

## Migration Notes

None. `cases.json` is not stored in the database, and the new `EvalCase` fields are optional with defaults, so older case files still load. The JSONB lesson (`context/foundation/lessons.md`) does not apply.

## References

- Research: `context/changes/testing-eval-dataset-expansion/research.md`
- Test plan: `context/foundation/test-plan.md` §2 (risks #1, #3, #6), §3 Phase 1, §6.1
- Prior eval change: `context/archive/2026-11-13-workflow-vs-orchestrator-eval/plan.md`
- Runner setup: `backend/app/eval/runner.py:281-311`; CI fake test: `backend/tests/test_eval_runner.py:127-146`
- Ranking: `backend/app/recommendation/recommender.py:79-90`; PRD rule: `context/foundation/prd.md:156`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Case schema, grouped report, labelling procedure

#### Automated

- [x] 1.1 Backend quality gates pass: `docker compose run --rm backend sh check.sh` (ruff, mypy, alembic, pytest) — 6dd2e9e
- [x] 1.2 New loader-validation tests pass: `docker compose run --rm backend uv run pytest tests/test_eval_cases.py` — 6dd2e9e
- [x] 1.3 Report tests cover the grouped sections: `docker compose run --rm backend uv run pytest tests/test_eval_report.py tests/test_eval_scoring.py` — 6dd2e9e

#### Manual

- [x] 1.4 test-plan §6.1 reads as a complete procedure: a person who wasn't in the planning session can label a new case from it — 6dd2e9e

### Phase 2: Parser path for adversarial cases

#### Automated

- [x] 2.1 Backend quality gates pass: `docker compose run --rm backend sh check.sh` — ce7905b
- [x] 2.2 Adversarial-path runner tests pass: `docker compose run --rm backend uv run pytest tests/test_eval_runner.py` — ce7905b

#### Manual

- [x] 2.3 A fake run on a scratch case file with one adversarial pair writes a report with the "Adversarial cases" section and the grouped sections filled in — ce7905b

### Phase 3: Dataset

#### Automated

- [x] 3.1 Case set loads and coverage assertions pass: `docker compose run --rm backend uv run pytest tests/test_eval_cases.py` — da59cfb
- [x] 3.2 Every case hits on the fake path (labels or `rule_based`): `docker compose run --rm backend uv run pytest tests/test_eval_runner.py` — da59cfb
- [x] 3.3 Backend quality gates pass: `docker compose run --rm backend sh check.sh` — da59cfb

#### Manual

- [x] 3.4 Spot-check 5 new rationales against the seed tables by hand (variants, chosen option, margin, verdict) — da59cfb
- [x] 3.5 Every adversarial email reads like a realistic customer email with an embedded instruction — da59cfb

### Phase 4: Baseline run and documentation

#### Automated

- [x] 4.1 Baseline report files exist in `backend/eval_reports/` with ~30 cases and no setup errors — PHASE4SHA

#### Manual

- [x] 4.2 Real eval run completes with an OpenRouter key and the report's grouped and adversarial sections are readable — PHASE4SHA
- [x] 4.3 test-plan §6.6 notes name the weakest categories from the baseline — PHASE4SHA
