# Eval dataset expansion — Plan Brief

> Full plan: `context/changes/testing-eval-dataset-expansion/plan.md`
> Research: `context/changes/testing-eval-dataset-expansion/research.md`

## What & Why

This is Phase 1 of the test plan (risks #1, #3, #6). The eval set is small: 12 cases, 1–2 per type. Its labels repeat what the code picks, it doesn't cover the PRD exception types, and it has no adversarial emails. So the eval can't show which kinds of case the orchestrator gets wrong, and it can't catch a prompt injection that changes the decision.

## Starting Point

The runner, case format and report exist in `backend/app/eval/`. Each case starts from golden fields, so the parser is never measured. A CI test requires every label to equal what the rule-based `rank()` picks.

## Desired End State

- About 30 cases, each labelled by a written procedure based on the PRD rule.
- Where the code departs from that rule, the case says so (`rule_based`).
- Every PRD type has its cases.
- 4 adversarial cases go through the real parser.
- The report groups accuracy by expected decision and by tag, and lists the adversarial cases.
- A baseline report is committed, and PRD Open Question #4 is closed.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|---|---|---|---|
| Label source | PRD rule; `rule_based` field when `rank()` differs | An honest oracle, and the code's departure from the business rule becomes visible | Plan |
| No variant meets everything | Coverage → earliest date → margin | Matches the customer's goal; margin within policy decides only among variants that meet everything | Plan |
| PRD types without a shortage | Expect today's behaviour (`standard`/`needs_input`); close OQ#4 | Coverage of every type; the docs agree with the code | Plan |
| Adversarial cases | Real parser for marked cases; compare price fields and decision with the twin | The real injection risk sits in the parser; signal now, at low cost | Plan |
| Seed data | No changes | No migration and no impact on the app or UI tests | Plan |
| Set size | ~30 cases | Several cases per category, run cost ~$0.03 | Plan |
| The eval skips the parser; CI enforces labels on fakes | Facts the plan builds on | Grounded at `runner.py:281-311` and `test_eval_runner.py:127-146` | Research |

## Scope

**In scope:**
- `EvalCase` gets `tags`, `rule_based` and `adversarial_of`, with validation.
- The runner gets an extractor and a parser path for adversarial cases.
- The report gets grouped accuracy and an "Adversarial cases" section.
- Re-label the 12 cases and add about 18 new ones; coverage assertions.
- test-plan §6.1 (procedure), §6.6, §3 and §4; close OQ#4 in the PRD and roadmap.
- A committed baseline report.

**Out of scope:**
- Seed data and migrations.
- Per-field parser accuracy for every case (Phase 2).
- Scoring the draft.
- Fixing `rank()`.
- A regression gate or CI runs of the real eval (Phase 3).
- Escalation for types without a shortage.

## Architecture / Approach

`cases.json` holds the label (PRD rule) plus an optional fake-path override, and CI checks against `rule_based or expected`. In `_set_up`, an adversarial case runs `analyze_inquiry` with the configured extractor (the LLM in a real run, `RuleBasedExtractor` in CI) instead of `save_corrections`. The runner compares the parsed fields once per case with the twin's, then orchestrates as usual.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Case schema and report | New fields + validation, grouped report, procedure in §6.1 | A procedure too vague to label consistently |
| 2. Parser path for adversarial cases | Extractor in the runner, parse check, `parse_mismatch`/`parse_failed` | The regex parser in CI reads an adversarial email differently than the label expects |
| 3. Dataset | ~30 cases, `rule_based` where needed, coverage assertions, OQ#4 closed | Hand-labelling mistakes (only spot-checked manually) |
| 4. Baseline and docs | Report for the new set, test-plan notes | Needs an OpenRouter key and a run of ~20–25 min |

**Prerequisites:** a local Docker DB (`docker compose`); an OpenRouter key for Phase 4.
**Estimated effort:** ~3–4 sessions; Phase 3 (hand-labelling) is the biggest.

## Open Risks & Assumptions

- **Assumption (procedure):** a variant "meets the requirements" when it covers the full quantity and meets the deadline. Partial compatibility and customer history lower confidence but don't disqualify it.
- On the current data only ABC-100 and XYZ-300 give more than one variant, so variety comes from quantity, deadline, consent and the discount request.
- An adversarial case in CI goes through the regex parser. If the regex reads it differently than the twin's label, the case needs `rule_based` or a different email.

## Success Criteria (Summary)

- The report shows accuracy per category and per tag, so you can see which kinds of case the orchestrator gets wrong.
- An injection that changes the price fields or the decision is visible in the report, per case.
- CI stays green, and the set cannot quietly shrink below the coverage minimums.
