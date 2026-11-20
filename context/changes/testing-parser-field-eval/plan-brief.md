# Parser field eval — Plan Brief

> Full plan: `context/changes/testing-parser-field-eval/plan.md`
> Research: `context/changes/testing-parser-field-eval/research.md`

## What & Why

Test-plan Phase 2 (risk #4): a misread field ("do piątku" → wrong date, a missed substitute refusal) poisons the whole flow, and today nothing measures the parser's quality. We add a cheap, DB-free eval that scores each parsed field against hand-made labels and, above all, finds the cases where the parser is wrong **and does not say so**.

## Starting Point

The decision eval skips the parser: golden fields replace the parse for 28 of 32 cases, and the 4 adversarial cases compare only 5 fields without counting a difference as a miss. Deterministic parsing code has unit tests; LLM extraction quality has none (tests use a mock).

## Desired End State

`python -m app.eval.fields` runs the real extractor over ≥ 40 labelled Polish phrasings and writes a report: hit / flagged miss / silent wrong per field and per tag, every silent error listed, unstable pairs and failed calls shown separately. A first real-LLM baseline is committed, and test-plan §6.2 explains how to add a case.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Case source | Separate `fields/cases.json` | Avoids the CI re-baseline coupling of `cases.json` and the narrow phrase set of golden fields | Plan (research input) |
| What a hit is | Three outcomes: hit / flagged miss / silent wrong | PRD FR-002 accepts "marked uncertain"; the silent error is risk #4 | Plan |
| Extractor | Real LLM, local run; regex only for smoke | Quality of Polish extraction is the unmeasured gap; CI has no secrets | Plan |
| Date oracle | Hand labels + independent invariants (weekday, not-before-reference) | Testing code must not be its own oracle (test-plan §2 #4) | Research / Plan |
| Customer match | Label's normalised words contained in the result | Same rule the customer check uses; "ACME" vs "ACME Sp. z o.o." is not an error | Plan review |
| Phrase scope | Supported and unsupported Polish phrases | Shows whether a resolver gap ends as a flag or as a wrong date | Plan |
| Reporting | Own report, no gate | Phase 2 is measurement; no data yet on LLM variability | Plan |
| Reference date | `received_at` Warsaw day via the real helper | Same as production (parse-inquiry plan) | Research |

## Scope

**In scope:** new `app/eval/fields/` package (cases, scoring, runner, report, CLI), ≥ 40 hand-labelled cases, tests, test-plan §6.2/§3/§6.6, README, first real baseline.

**Out of scope:** regression gate for fields; changes to `cases.json`, `EvalReport`, `compare.py`, the parser or its prompt; English, HTML or quoted mails; cases that need a product decision; scoring `deadline_text`/`price_text`.

## Architecture / Approach

Per case and repeat: `extractor.extract(subject, body, reference_date)` → real `build_parsed` → `score_case` against the labels. No DB, no orchestrator. Labels carry a rationale with the arithmetic and the loader rejects inconsistent ones, mirroring the decision eval.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Schema and scoring | `FieldCase`, loader with independent validators, three-outcome scorer | Label rules too loose or too strict |
| 2. Case set | ≥ 40 hand-labelled phrasings with coverage test | Label mistakes; a case that needs a product decision |
| 3. Runner, report, CLI | `python -m app.eval.fields`, report with silent errors | Report shape hides the silent errors |
| 4. Docs and baseline | §6.2 cookbook, README, first real-LLM report | Needs an API key; unknown run time and cost |

**Prerequisites:** a configured LLM provider for the Phase 4 baseline; `POSTGRES_HOST_PORT=55433` for compose when 5432 is taken.
**Estimated effort:** ~3-4 sessions across 4 phases; Phase 2 (labels) is the most careful work.

## Open Risks & Assumptions

- Labels are the oracle: a wrong label looks like a parser bug. Mitigation: rationale per case and a manual arithmetic check of 10 cases.
- LLM non-determinism at temperature 0 is unmeasured; repeats and the unstable list expose it, but a threshold for later gating needs data first.
- Qwen via OpenRouter is the model used so far; results are specific to the configured model.

## Success Criteria (Summary)

- The report names every field the parser got wrong silently, per case.
- Adding a field case follows a documented procedure and the loader rejects bad labels.
- A real-provider baseline exists, and nothing about the decision eval or its CI test changed.
