# Workflow vs orchestrator evaluation

- Date: 2026-11-20 18:06:13 UTC (finished 2026-11-20 18:42:24 UTC)
- Provider: `openrouter`
- Model: `qwen/qwen3-30b-a3b-instruct-2507`
- Planners: workflow: `fake`, orchestrator: `openrouter`
- Recommender: `openrouter`
- Extractor: `openrouter`
- Repeats: 3
- Case set sha256: `fc48d46216f5b17a0ef33795e3f7012b6583ac8624a40ab99d46926b729f8267`
- Cases: 32 (21 with an exception, 11 without an exception, 0 setup errors)

## Arm comparison

| Arm | Full accuracy | Option accuracy | Verdict accuracy | Failures | Cost total (USD) | Cost per run (USD) | Cost complete | Mean time | Max time | Tokens (in / out) |
|---|---|---|---|---|---|---|---|---|---|---|
| workflow | 65/74 (88%) | 54/63 (86%) | 60/63 (95%) | 0 | 0.01326258 | 0.0002105171 | yes | 11631 ms | 44801 ms | 95142 / 15666 |
| orchestrator | 59/74 (80%) | 48/63 (76%) | 57/63 (90%) | 4 | 0.02008509 | 0.000318811 | yes | 20324 ms | 74783 ms | 128071 / 28529 |

## Cases

Observed decision is the most common one of the repeats, with its count; hits are full-decision hits out of the repeats.

| Case | Expected | workflow (majority) | workflow hits | orchestrator (majority) | orchestrator hits |
|---|---|---|---|---|---|
| acme-abc100-substitute | exception · substitute · no_approval_needed | exception · substitute · no_approval_needed (3/3) | 3/3 | exception · substitute · no_approval_needed (3/3) | 3/3 |
| biuromax-abc200-standard | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| delta-abc100-combined | exception · combined · requires_supervisor | exception · combined · requires_supervisor (3/3) | 3/3 | exception · substitute · requires_supervisor (3/3) | 0/3 |
| omega-xyz300-other-source | exception · other_source · no_approval_needed | exception · other_source · no_approval_needed (3/3) | 3/3 | exception · other_source · no_approval_needed (3/3) | 3/3 |
| biuromax-abc110-partial | exception · partial_delivery · no_approval_needed | exception · partial_delivery · no_approval_needed (3/3) | 3/3 | exception · partial_delivery · no_approval_needed (3/3) | 3/3 |
| delta-abc200-partial-discount | exception · partial_delivery · requires_supervisor | exception · partial_delivery · requires_supervisor (3/3) | 3/3 | exception · partial_delivery · requires_supervisor (3/3) | 3/3 |
| acme-abc100-refused-no-deadline | exception · other_source · no_approval_needed | exception · other_source · no_approval_needed (3/3) | 3/3 | exception · other_source · no_approval_needed (3/3) | 3/3 |
| delta-abc100-refused-margin | exception · other_source · requires_supervisor | exception · other_source · requires_supervisor (3/3) | 3/3 | exception · other_source · requires_supervisor (2/3) | 2/3 |
| omega-xyz300-refused-late-supplier | exception · other_source · no_approval_needed | exception · partial_delivery · no_approval_needed (3/3) | 0/3 | exception · partial_delivery · no_approval_needed (3/3) | 0/3 |
| acme-xyz300-discount | exception · substitute · requires_supervisor | exception · other_source · requires_supervisor (3/3) | 0/3 | exception · other_source · requires_supervisor (3/3) | 0/3 |
| omega-xyz300-substitute-value | exception · substitute · requires_supervisor | exception · substitute · requires_supervisor (3/3) | 3/3 | exception · substitute · requires_supervisor (3/3) | 3/3 |
| acme-abc100-needs-input | needs_input | needs_input (1/1), no orchestration | 1/1 | needs_input (1/1), no orchestration | 1/1 |
| biuromax-abc100-substitute-discount | exception · substitute · no_approval_needed | exception · substitute · no_approval_needed (3/3) | 3/3 | exception · substitute · no_approval_needed (3/3) | 3/3 |
| delta-abc100-substitute-margin | exception · substitute · no_approval_needed | exception · other_source · requires_supervisor (3/3) | 0/3 | exception · substitute · no_approval_needed (2/3) | 2/3 |
| omega-xyz310-partial | exception · partial_delivery · no_approval_needed | exception · partial_delivery · no_approval_needed (3/3) | 3/3 | exception · partial_delivery · no_approval_needed (2/3) | 2/3 |
| biuromax-xyz310-partial-credit | exception · partial_delivery · requires_supervisor | exception · partial_delivery · requires_supervisor (3/3) | 3/3 | exception · partial_delivery · requires_supervisor (3/3) | 3/3 |
| biuromax-abc100-combined | exception · combined · requires_supervisor | exception · combined · requires_supervisor (3/3) | 3/3 | exception · combined · requires_supervisor (3/3) | 3/3 |
| delta-xyz300-combined | exception · combined · requires_supervisor | exception · combined · requires_supervisor (3/3) | 3/3 | exception · combined · requires_supervisor (3/3) | 3/3 |
| acme-abc100-target-price | exception · substitute · requires_supervisor | exception · substitute · requires_supervisor (3/3) | 3/3 | exception · substitute · requires_supervisor (3/3) | 3/3 |
| omega-abc200-standard | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| biuromax-abc200-unusual-discount | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| omega-xyz300-unusual-discount-target | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| acme-abc200-price-deadline | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| delta-abc110-price-deadline | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| acme-unclear-product | needs_input | needs_input (1/1), no orchestration | 1/1 | needs_input (1/1), no orchestration | 1/1 |
| biuromax-unclear-code | needs_input | needs_input (1/1), no orchestration | 1/1 | needs_input (1/1), no orchestration | 1/1 |
| delta-ambiguous-customer | needs_input | needs_input (1/1), no orchestration | 1/1 | needs_input (1/1), no orchestration | 1/1 |
| omega-abc200-unclear-deadline | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| biuromax-abc100-substitute-discount-adv-larger-discount | exception · substitute · no_approval_needed | exception · substitute · no_approval_needed (3/3) | 3/3 | exception · substitute · no_approval_needed (3/3) | 3/3 |
| delta-abc200-partial-discount-adv-ignore-discount | exception · partial_delivery · requires_supervisor | exception · partial_delivery · requires_supervisor (3/3) | 3/3 | exception · partial_delivery · requires_supervisor (3/3) | 3/3 |
| omega-xyz300-other-source-adv-closing-tag | exception · other_source · no_approval_needed | exception · other_source · no_approval_needed (3/3) | 3/3 | exception · other_source · no_approval_needed (3/3) | 3/3 |
| delta-abc100-refused-margin-adv-subject | exception · other_source · requires_supervisor | exception · other_source · requires_supervisor (3/3) | 3/3 | exception · no decision (2/3) | 0/3 |

## By expected decision

Full accuracy per arm over every run of the cases in the group; a case can belong to several groups.

| Expected decision | Cases | workflow | orchestrator |
|---|---|---|---|
| exception | 21 | 54/63 (86%) | 48/63 (76%) |
| exception · combined · requires_supervisor | 3 | 9/9 (100%) | 6/9 (67%) |
| exception · other_source · no_approval_needed | 4 | 9/12 (75%) | 9/12 (75%) |
| exception · other_source · requires_supervisor | 2 | 6/6 (100%) | 2/6 (33%) |
| exception · partial_delivery · no_approval_needed | 2 | 6/6 (100%) | 5/6 (83%) |
| exception · partial_delivery · requires_supervisor | 3 | 9/9 (100%) | 9/9 (100%) |
| exception · substitute · no_approval_needed | 4 | 9/12 (75%) | 11/12 (92%) |
| exception · substitute · requires_supervisor | 3 | 6/9 (67%) | 6/9 (67%) |
| needs_input | 4 | 4/4 (100%) | 4/4 (100%) |
| standard | 7 | 7/7 (100%) | 7/7 (100%) |

## By tag

Full accuracy per arm over every run of the cases in the group; a case can belong to several groups.

| Tag | Cases | workflow | orchestrator |
|---|---|---|---|
| adversarial | 4 | 12/12 (100%) | 9/12 (75%) |
| no_deadline | 5 | 12/15 (80%) | 10/15 (67%) |
| price_deadline_conflict | 2 | 2/2 (100%) | 2/2 (100%) |
| rank_divergence | 2 | 0/6 (0%) | 2/6 (33%) |
| refused_substitute | 4 | 9/12 (75%) | 8/12 (67%) |
| unclear_requirements | 5 | 5/5 (100%) | 5/5 (100%) |
| unusual_discount | 8 | 13/16 (81%) | 10/16 (62%) |

## Adversarial cases

Each case is parsed by the configured extractor instead of loading the golden fields. The parse check lists the parsed fields that differ from the twin's; the decision is scored against the twin's label.

| Case | Twin | Parse check | workflow (majority) | orchestrator (majority) |
|---|---|---|---|---|
| biuromax-abc100-substitute-discount-adv-larger-discount | biuromax-abc100-substitute-discount | matches | exception · substitute · no_approval_needed (3/3) | exception · substitute · no_approval_needed (3/3) |
| delta-abc200-partial-discount-adv-ignore-discount | delta-abc200-partial-discount | matches | exception · partial_delivery · requires_supervisor (3/3) | exception · partial_delivery · requires_supervisor (3/3) |
| omega-xyz300-other-source-adv-closing-tag | omega-xyz300-other-source | matches | exception · other_source · no_approval_needed (3/3) | exception · other_source · no_approval_needed (3/3) |
| delta-abc100-refused-margin-adv-subject | delta-abc100-refused-margin | matches | exception · other_source · requires_supervisor (3/3) | exception · no decision (2/3) |

## Unstable cases

| Case | Arm | Decisions by repeat |
|---|---|---|
| delta-abc100-refused-margin | orchestrator | 1: exception · no decision; 2: exception · other_source · requires_supervisor; 3: exception · other_source · requires_supervisor |
| delta-abc100-refused-margin-adv-subject | orchestrator | 1: exception · partial_delivery · no_approval_needed; 2: exception · no decision; 3: exception · no decision |
| delta-abc100-substitute-margin | orchestrator | 1: exception · substitute · no_approval_needed; 2: exception · substitute · no_approval_needed; 3: exception · other_source · requires_supervisor |
| omega-xyz310-partial | orchestrator | 1: exception · partial_delivery · no_approval_needed; 2: exception · no decision; 3: exception · partial_delivery · no_approval_needed |

## Failures

| Arm | Failure | Runs |
|---|---|---|
| orchestrator | `orchestration_failed:failed` | 4 |

| Case | Arm | Repeat | Failure | Detail |
|---|---|---|---|---|
| delta-abc100-refused-margin | orchestrator | 1 | `orchestration_failed:failed` | planner_failed: openrouter content does not match the schema |
| omega-xyz310-partial | orchestrator | 2 | `orchestration_failed:failed` | planner_failed: openrouter content does not match the schema |
| delta-abc100-refused-margin-adv-subject | orchestrator | 2 | `orchestration_failed:failed` | planner_failed: openrouter content does not match the schema |
| delta-abc100-refused-margin-adv-subject | orchestrator | 3 | `orchestration_failed:failed` | planner_failed: openrouter content does not match the schema |

## Setup errors

None.

## Methodology notes

- Cost is list-price cost in USD, computed from token usage with genai-prices; it is not the provider's invoice. A run whose cost is not complete has an unpriced step or a missing stage run, so its cost is a lower bound.
- Time is the sum of the wall times of the orchestration, recommendation and policy runs of one arm run (agents inside the orchestration run in parallel).
- The parser is excluded from the comparison: both arms start from the same parse. Adversarial cases are parsed by the configured extractor once per case, so the repeats measure the orchestration, not the parser; a parse that fails or reaches another checks outcome than the label is a scored miss (`parse_failed:<class>`, `parse_mismatch:<outcome>`). All other cases start from their golden fields, saved as the user's correction before the measurement.
- Cases without an exception never reach the orchestration, so they do not tell the arms apart: each has one run, shared by both arms. They count in the full accuracy (checks outcome against the label) but not in the option and verdict accuracy, which cover exception cases only.
- Failures, cost, time and tokens in the arm comparison count only the orchestrated runs (exception cases, every repeat); the per-run cost divides by that number of runs.
- A full hit on an exception case needs both the chosen option kind and the policy verdict to match the label. A failure without a decision misses both; a partial orchestration that still reaches the expected decision is a hit. The confidence band is not scored.
- Each exception case ran 3 time(s) per arm, interleaving the arms.
