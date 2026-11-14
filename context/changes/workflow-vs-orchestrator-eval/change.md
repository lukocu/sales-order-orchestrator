---
change_id: workflow-vs-orchestrator-eval
title: Workflow vs orchestrator eval
status: impl_reviewed
created: 2026-11-13
updated: 2026-11-14
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

### Deviations from the plan

- **Real run provider (3.4).** The committed report (7bda4b3) comes from OpenRouter with `qwen/qwen3-30b-a3b-instruct-2507`, not Groq. Groq's free tier (`openai/gpt-oss-120b`) answered 429 after a few calls, so almost every run failed with `rate_limited`. Progress row 3.4 keeps its original title ("Przebieg z Groq").
- **`run_eval` signature.** Three extra required keyword arguments, `provider`, `model` and `cases_version`, carry the report metadata the plan asked for.
- **Report metrics.** Accuracy counts every run; failures, cost, time and tokens count only orchestrated runs (`ArmReport` with `all_runs` / `orchestrated`). Explained in the report's methodology notes.
- **Not part of S-10.** 9ccff5f (tracing: step `started_at` from a monotonic clock) is a separate flaky-test fix reviewed in PR lukocu/sales-order-orchestrator#1; it landed between p2 and p3.
- **After the implementation review** (reviews/impl-review.md): stale stage results score as `stale_result`, an arm call that raises is recorded as `unexpected:<ClassName>` instead of discarding the run, runs hold a Postgres advisory lock, the CLI refuses a non-local database without `--allow-remote-db`, and failures carry the stage's error message as `failure_detail`.
