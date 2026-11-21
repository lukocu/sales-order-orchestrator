<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Parser field eval

- **Plan**: context/changes/testing-parser-field-eval/plan.md
- **Mode**: Deep
- **Date**: 2026-11-20
- **Verdict**: REVISE (after fixes: SOUND)
- **Findings**: 0 critical, 3 warnings, 1 observation

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

5/5 paths ✓, 6/6 symbols ✓ (cases_sha256, reference_date_of, build_parsed, get_extractor, LlmUsage, non-recursive report glob in compare.py:374 and test_eval_compare.py:683), brief↔plan ✓

## Findings

### F1 — "Correct customer" is undefined

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — Field scoring
- **Detail**: Exact string comparison turns "ACME" vs "ACME Sp. z o.o." into a silent_wrong, while the only consumer, `match_customer` (`app/checks/rules.py:100-110`), matches by email and then by normalised name-word containment.
- **Fix A ⭐ Recommended**: customer is a hit when the label's `normalize_name` words appear as a contiguous run in the result's.
  - Strength: "Correct" means what the next step needs; no extra label fields.
  - Tradeoff: Uses a checks helper (not parser code, so not self-oracling).
  - Confidence: HIGH — `app/checks/rules.py:66-76,108-110`.
  - Blind spot: None significant.
- **Fix B**: an `aliases` list in the customer label.
  - Strength: Full per-case control.
  - Tradeoff: Every label must anticipate variants.
  - Confidence: MED.
  - Blind spot: None significant.
- **Decision**: FIXED (Fix A)

### F2 — Tag accuracy dilutes across all six fields

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1 — summarize; Phase 3 — report
- **Detail**: Per-tag counts over all six fields of a case dilute a price or deadline error about six times.
- **Fix**: Map each tag to its field and count tag accuracy on that field only.
- **Decision**: FIXED

### F3 — --allow-fake does not force the regex extractor

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 3 — CLI contract, criterion 3.2
- **Detail**: In `app/eval/__main__.py:84` the flag only permits a fake/keyless provider; compose passes `LLM_PROVIDER`/`LLM_API_KEY` from `.env` (`docker-compose.yml:56-58`), so the smoke run could call the real LLM.
- **Fix**: Keep the decision-eval semantics; run the smoke command with `-e LLM_PROVIDER=fake`.
- **Decision**: FIXED

### F4 — Temporary-database gate has no create step

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Criteria 3.4 and 4.2
- **Detail**: `DATABASE_URL=…/check_tmp` is used but never created.
- **Fix**: CREATE DATABASE before and DROP after, in both criteria.
- **Decision**: FIXED
