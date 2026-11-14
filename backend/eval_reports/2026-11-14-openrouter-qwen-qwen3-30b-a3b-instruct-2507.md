# Workflow vs orchestrator evaluation

- Date: 2026-11-14 13:15:02 UTC (finished 2026-11-14 13:23:28 UTC)
- Provider: `openrouter`
- Model: `qwen/qwen3-30b-a3b-instruct-2507`
- Planners: workflow: `fake`, orchestrator: `openrouter`
- Recommender: `openrouter`
- Repeats: 3
- Case set sha256: `49ec9f5e0c29a8baee7d0030a0f3d0c11edbed150faa91e801fceb54c4436769`
- Cases: 12 (10 with an exception, 2 without an exception, 0 setup errors)

## Arm comparison

| Arm | Full accuracy | Option accuracy | Verdict accuracy | Failures | Cost total (USD) | Cost per run (USD) | Cost complete | Mean time | Max time | Tokens (in / out) |
|---|---|---|---|---|---|---|---|---|---|---|
| workflow | 26/32 (81%) | 24/30 (80%) | 30/30 (100%) | 0 | 0.00607086 | 0.000202362 | yes | 5801 ms | 19430 ms | 42144 / 7593 |
| orchestrator | 22/32 (69%) | 20/30 (67%) | 28/30 (93%) | 2 | 0.0089694 | 0.00029898 | yes | 8718 ms | 16712 ms | 56720 / 12882 |

## Cases

Observed decision is the most common one of the repeats, with its count; hits are full-decision hits out of the repeats.

| Case | Expected | workflow (majority) | workflow hits | orchestrator (majority) | orchestrator hits |
|---|---|---|---|---|---|
| acme-abc100-substitute | exception · substitute · no_approval_needed | exception · substitute · no_approval_needed (3/3) | 3/3 | exception · substitute · no_approval_needed (3/3) | 3/3 |
| biuromax-abc200-standard | standard | standard (1/1), no orchestration | 1/1 | standard (1/1), no orchestration | 1/1 |
| delta-abc100-combined | exception · combined · requires_supervisor | exception · substitute · requires_supervisor (3/3) | 0/3 | exception · substitute · requires_supervisor (2/3) | 0/3 |
| omega-xyz300-other-source | exception · other_source · no_approval_needed | exception · other_source · no_approval_needed (3/3) | 3/3 | exception · other_source · no_approval_needed (3/3) | 3/3 |
| biuromax-abc110-partial | exception · partial_delivery · no_approval_needed | exception · partial_delivery · no_approval_needed (3/3) | 3/3 | exception · partial_delivery · no_approval_needed (3/3) | 3/3 |
| delta-abc200-partial-discount | exception · partial_delivery · requires_supervisor | exception · partial_delivery · requires_supervisor (3/3) | 3/3 | exception · partial_delivery · requires_supervisor (3/3) | 3/3 |
| acme-abc100-refused-no-deadline | exception · other_source · no_approval_needed | exception · other_source · no_approval_needed (3/3) | 3/3 | exception · partial_delivery · no_approval_needed (3/3) | 0/3 |
| delta-abc100-refused-margin | exception · other_source · requires_supervisor | exception · other_source · requires_supervisor (3/3) | 3/3 | exception · other_source · requires_supervisor (2/3) | 2/3 |
| omega-xyz300-refused-late-supplier | exception · other_source · no_approval_needed | exception · partial_delivery · no_approval_needed (3/3) | 0/3 | exception · partial_delivery · no_approval_needed (2/3) | 0/3 |
| acme-xyz300-discount | exception · other_source · requires_supervisor | exception · other_source · requires_supervisor (3/3) | 3/3 | exception · other_source · requires_supervisor (3/3) | 3/3 |
| omega-xyz300-substitute-value | exception · substitute · requires_supervisor | exception · substitute · requires_supervisor (3/3) | 3/3 | exception · substitute · requires_supervisor (3/3) | 3/3 |
| acme-abc100-needs-input | needs_input | needs_input (1/1), no orchestration | 1/1 | needs_input (1/1), no orchestration | 1/1 |

## Unstable cases

| Case | Arm | Decisions by repeat |
|---|---|---|
| delta-abc100-combined | orchestrator | 1: exception · substitute · requires_supervisor; 2: exception · other_source · requires_supervisor; 3: exception · substitute · requires_supervisor |
| delta-abc100-refused-margin | orchestrator | 1: exception · other_source · requires_supervisor; 2: exception · no decision; 3: exception · other_source · requires_supervisor |
| omega-xyz300-refused-late-supplier | orchestrator | 1: exception · partial_delivery · no_approval_needed; 2: exception · partial_delivery · no_approval_needed; 3: exception · no decision |

## Failures

| Arm | Failure | Runs |
|---|---|---|
| orchestrator | `orchestration_failed:failed` | 2 |

| Case | Arm | Repeat | Failure |
|---|---|---|---|
| delta-abc100-refused-margin | orchestrator | 2 | `orchestration_failed:failed` |
| omega-xyz300-refused-late-supplier | orchestrator | 3 | `orchestration_failed:failed` |

## Setup errors

None.

## Methodology notes

- Cost is list-price cost in USD, computed from token usage with genai-prices; it is not the provider's invoice. A run whose cost is not complete has an unpriced step or a missing stage run, so its cost is a lower bound.
- Time is the sum of the wall times of the orchestration, recommendation and policy runs of one arm run (agents inside the orchestration run in parallel).
- The parser is excluded from the comparison: both arms start from the golden fields of the case, saved as the user's correction before the measurement.
- Cases without an exception never reach the orchestration, so they do not tell the arms apart: each has one run, shared by both arms. They count in the full accuracy (checks outcome against the label) but not in the option and verdict accuracy, which cover exception cases only.
- Failures, cost, time and tokens in the arm comparison count only the orchestrated runs (exception cases, every repeat); the per-run cost divides by that number of runs.
- A full hit on an exception case needs both the chosen option kind and the policy verdict to match the label. A failure without a decision misses both; a partial orchestration that still reaches the expected decision is a hit. The confidence band is not scored.
- Each exception case ran 3 time(s) per arm, interleaving the arms.
