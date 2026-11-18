"""Policy rules as pure functions: no database, no model, no clock.

The input is independent of the stored recommendation JSONB (the value and margin of one
option plus the discount and credit checks), so an edited draft can be evaluated the same
way. A value exactly at its threshold passes. A rule without its threshold or its data is
`not_evaluated`, and anything but all rules passing requires a supervisor.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.checks.rules import CENT, HUNDRED
from app.checks.schema import CreditCheck, DiscountCheck
from app.policy.schema import PolicyOutcome, PolicyResult, RuleResult


@dataclass(frozen=True)
class PolicyThresholds:
    """Thresholds of the configurable rules; None when the threshold is not configured."""

    margin_min_percent: Decimal | None
    discount_max_percent: Decimal | None
    order_value_max: Decimal | None
    are_examples: bool


@dataclass(frozen=True)
class PolicyInputs:
    """What the rules evaluate: one option and the discount and credit checks.

    `offered_discount_percent` is the largest discount of an edited offer's prices off their
    list prices; None for the option as recommended, whose discount rule is the S-06 one.
    """

    option_id: str
    value: Decimal  # PLN net
    margin_percent: Decimal
    discount: DiscountCheck
    list_price: Decimal | None  # catalogue price of the requested product
    credit: CreditCheck
    offered_discount_percent: Decimal | None = None


def evaluate_margin(margin_percent: Decimal, minimum: Decimal | None) -> RuleResult:
    if minimum is None:
        return RuleResult(
            code="margin",
            verdict="not_evaluated",
            actual=margin_percent,
            threshold=None,
            unit="percent",
            reason="No minimum margin threshold",
            reason_code="margin_threshold_missing",
        )
    passed = margin_percent >= minimum
    return RuleResult(
        code="margin",
        verdict="pass" if passed else "fail",
        actual=margin_percent,
        threshold=minimum,
        unit="percent",
        reason="Margin at or above the minimum" if passed else "Margin below the minimum",
        reason_code="margin_within_minimum" if passed else "margin_below_minimum",
    )


def target_price_discount(target_price: Decimal, list_price: Decimal) -> Decimal:
    """Discount off the list price implied by a target price; negative above the list price."""
    return ((list_price - target_price) / list_price * HUNDRED).quantize(CENT, ROUND_HALF_UP)


def evaluate_discount(
    discount: DiscountCheck,
    list_price: Decimal | None,
    maximum: Decimal | None,
    offered: Decimal | None = None,
) -> RuleResult:
    """The discount the customer asks for; without a request, the standard discount.

    With `offered` (the discount in an edited offer's prices) both are evaluated: the rule
    fails when either is above the maximum and reports the larger one. An unchanged offer
    thus keeps the stage's result, and a lower price can only make it worse.
    """
    requested = _evaluate_requested_discount(discount, list_price, maximum)
    if offered is None:
        return requested
    if maximum is None:
        candidates = [d for d in (requested.actual, offered) if d is not None]
        return RuleResult(
            code="discount",
            verdict="not_evaluated",
            actual=max(candidates),
            threshold=None,
            unit="percent",
            reason="No maximum discount threshold",
            reason_code="discount_threshold_missing",
        )
    decided = requested.verdict != "not_evaluated" and requested.actual is not None
    if decided and requested.actual is not None and requested.actual >= offered:
        return requested  # the requested (or standard) discount decides, with its own reason
    passed = offered <= maximum
    return RuleResult(
        code="discount",
        verdict="pass" if passed else "fail",
        actual=offered,
        threshold=maximum,
        unit="percent",
        reason="Offered discount within the maximum"
        if passed
        else "Offered discount above the maximum",
        reason_code="offered_discount_within_maximum"
        if passed
        else "offered_discount_above_maximum",
    )


def _evaluate_requested_discount(
    discount: DiscountCheck, list_price: Decimal | None, maximum: Decimal | None
) -> RuleResult:
    """The S-06 discount rule: the requested discount, else the standard one."""

    def not_evaluated(reason: str, reason_code: str, actual: Decimal | None = None) -> RuleResult:
        return RuleResult(
            code="discount",
            verdict="not_evaluated",
            actual=actual,
            threshold=maximum,
            unit="percent",
            reason=reason,
            reason_code=reason_code,
        )

    if discount.status == "skipped":
        return not_evaluated("Discount check skipped", "discount_check_skipped")
    kind = discount.requested_kind
    if kind == "discount_percent":
        if discount.requested_value is None:
            return not_evaluated("Requested discount missing", "requested_discount_missing")
        actual = discount.requested_value
        subject = "Requested discount"
        reason_prefix = "requested_discount"
    elif kind == "target_price":
        if discount.requested_value is None:
            return not_evaluated("Target price missing", "target_price_missing")
        if list_price is None or list_price <= 0:
            return not_evaluated("Target price without a list price", "target_list_price_missing")
        actual = target_price_discount(discount.requested_value, list_price)
        subject = "Discount implied by the target price"
        reason_prefix = "target_discount"
    else:  # none, best_price: the customer gets the standard discount
        if discount.standard_percent is None:
            return not_evaluated("No standard discount", "standard_discount_missing")
        actual = discount.standard_percent
        subject = "Standard discount"
        reason_prefix = "standard_discount"
    if maximum is None:
        return not_evaluated("No maximum discount threshold", "discount_threshold_missing", actual)
    passed = actual <= maximum
    return RuleResult(
        code="discount",
        verdict="pass" if passed else "fail",
        actual=actual,
        threshold=maximum,
        unit="percent",
        reason=f"{subject} within the maximum" if passed else f"{subject} above the maximum",
        reason_code=f"{reason_prefix}_within_maximum"
        if passed
        else f"{reason_prefix}_above_maximum",
    )


def evaluate_order_value(value: Decimal, maximum: Decimal | None) -> RuleResult:
    if maximum is None:
        return RuleResult(
            code="order_value",
            verdict="not_evaluated",
            actual=value,
            threshold=None,
            unit="PLN",
            reason="No maximum order value threshold",
            reason_code="order_value_threshold_missing",
        )
    passed = value <= maximum
    return RuleResult(
        code="order_value",
        verdict="pass" if passed else "fail",
        actual=value,
        threshold=maximum,
        unit="PLN",
        reason="Order value within the maximum" if passed else "Order value above the maximum",
        reason_code="order_value_within_maximum" if passed else "order_value_above_maximum",
    )


def evaluate_credit(credit: CreditCheck, value: Decimal) -> RuleResult:
    """Balance plus the selected option's value against the customer's limit.

    The check's own `over_limit` is computed for the full requested quantity, so it is not
    used here; only a blocked customer fails regardless of the amounts.
    """
    if credit.status == "skipped":
        return RuleResult(
            code="credit",
            verdict="not_evaluated",
            actual=None,
            threshold=None,
            unit="PLN",
            reason="Credit check skipped",
            reason_code="credit_check_skipped",
        )
    actual = credit.balance + value if credit.balance is not None else None
    if credit.status == "blocked":
        return RuleResult(
            code="credit",
            verdict="fail",
            actual=actual,
            threshold=credit.limit,
            unit="PLN",
            reason="Customer credit blocked",
            reason_code="credit_blocked",
        )
    if actual is None or credit.limit is None:
        return RuleResult(
            code="credit",
            verdict="not_evaluated",
            actual=actual,
            threshold=credit.limit,
            unit="PLN",
            reason="Credit limit or balance missing",
            reason_code="credit_data_missing",
        )
    passed = actual <= credit.limit
    return RuleResult(
        code="credit",
        verdict="pass" if passed else "fail",
        actual=actual,
        threshold=credit.limit,
        unit="PLN",
        reason=(
            "Balance + selected option value within limit"
            if passed
            else "Balance + selected option value over limit"
        ),
        reason_code="credit_within_limit" if passed else "credit_over_limit",
    )


def outcome(rules: list[RuleResult]) -> PolicyOutcome:
    """No approval only when every rule passes; a fail or a gap goes to a supervisor."""
    if all(rule.verdict == "pass" for rule in rules):
        return "no_approval_needed"
    return "requires_supervisor"


def evaluate(inputs: PolicyInputs, thresholds: PolicyThresholds) -> PolicyResult:
    rules = [
        evaluate_margin(inputs.margin_percent, thresholds.margin_min_percent),
        evaluate_discount(
            inputs.discount,
            inputs.list_price,
            thresholds.discount_max_percent,
            inputs.offered_discount_percent,
        ),
        evaluate_order_value(inputs.value, thresholds.order_value_max),
        evaluate_credit(inputs.credit, inputs.value),
    ]
    return PolicyResult(
        option_id=inputs.option_id,
        rules=rules,
        outcome=outcome(rules),
        thresholds_are_examples=thresholds.are_examples,
    )
