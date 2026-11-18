# Business message contracts

`RuleResult.reason_code` is optional (`null` for historical results). The original
`reason`, numbers, verdict and rule-selection logic remain unchanged. Codes are
chosen in the producer, never inferred from the original sentence.

| Rule | Codes |
| --- | --- |
| Margin | `margin_threshold_missing`, `margin_within_minimum`, `margin_below_minimum` |
| Discount data | `discount_check_skipped`, `requested_discount_missing`, `target_price_missing`, `target_list_price_missing`, `standard_discount_missing`, `discount_threshold_missing` |
| Requested percentage | `requested_discount_within_maximum`, `requested_discount_above_maximum` |
| Target price | `target_discount_within_maximum`, `target_discount_above_maximum` |
| Standard discount | `standard_discount_within_maximum`, `standard_discount_above_maximum` |
| Edited offer | `offered_discount_within_maximum`, `offered_discount_above_maximum` |
| Order value | `order_value_threshold_missing`, `order_value_within_maximum`, `order_value_above_maximum` |
| Credit | `credit_check_skipped`, `credit_blocked`, `credit_data_missing`, `credit_within_limit`, `credit_over_limit` |

For edited offers the larger deciding discount keeps its own code and original
reason. A missing maximum always uses `discount_threshold_missing` once a discount
can be computed. A blocked customer keeps `credit_blocked` even without amounts.

`Signal.params` defaults to an independent empty object for old results. Values
are strict strings, integers or floating-point numbers (booleans, null, arrays
and objects are rejected). Each occurrence has its own parameters:

| Signal | Parameters |
| --- | --- |
| `incomplete_coverage` | `covered`: integer, `requested`: integer |
| `deadline_missed` | `fulfilled_on`: ISO date string, `deadline`: ISO date string |
| `compat_full`, `compat_partial` | `product_code`: string |
| Other existing signals | Empty object; no dynamic data was embedded in their original labels |

Existing codes and suffixes (`task_failed:<capability>`, `not_checked:<capability>`,
`alternative_not_checked:<capability>`, `uncertain_input:<field>`) retain their
meaning. Polarities, original labels and confidence bands are unchanged.

Coverage: `tests/test_business_message_contracts.py` enumerates every policy
branch, deciding edited discounts, repeated compatibility signals and dynamic
quantities/dates. It checks strict parameter types and reads both generations of
recommendation, policy and nested draft JSONB plus decision snapshots through the
API without changing stored JSONB. Snapshots contain rule-code lists rather than
policy reasons or confidence signals; they retain their original facts.
