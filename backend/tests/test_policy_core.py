"""Policy rules on in-memory data: each rule at its threshold, missing data, the overall
outcome and the seed scenarios. No database."""

from decimal import Decimal

import pytest

from app.checks.schema import CreditCheck, DiscountCheck
from app.parsing.schema import PriceKind
from app.policy.rules import (
    PolicyInputs,
    PolicyThresholds,
    evaluate,
    evaluate_credit,
    evaluate_discount,
    evaluate_margin,
    evaluate_order_value,
    outcome,
    target_price_discount,
)
from app.policy.schema import RuleResult

# The example thresholds (migrations/versions/0011_policy_verdicts.py).
SEED = PolicyThresholds(
    margin_min_percent=Decimal("20.00"),
    discount_max_percent=Decimal("15.00"),
    order_value_max=Decimal("30000.00"),
    are_examples=True,
)
NO_THRESHOLDS = PolicyThresholds(
    margin_min_percent=None, discount_max_percent=None, order_value_max=None, are_examples=True
)


def _discount(
    kind: PriceKind = "none",
    value: str | None = None,
    standard: str | None = "5.00",
    status: str = "ok",
) -> DiscountCheck:
    return DiscountCheck.model_validate(
        {
            "status": status,
            "standard_percent": standard,
            "requested_kind": kind,
            "requested_value": value,
        }
    )


def _credit(
    limit: str | None = "30000.00", balance: str | None = "2000.00", status: str = "ok"
) -> CreditCheck:
    return CreditCheck.model_validate({"status": status, "limit": limit, "balance": balance})


def _verdicts(rules: list[RuleResult]) -> dict[str, str]:
    return {rule.code: rule.verdict for rule in rules}


# --- Seed scenarios ---------------------------------------------------------------------


def test_acme_passes_every_rule() -> None:
    inputs = PolicyInputs(
        option_id="stock+ABC-110",
        value=Decimal("9262.50"),
        margin_percent=Decimal("25.51"),
        discount=_discount(standard="5.00"),
        list_price=Decimal("120.00"),
        credit=_credit("30000.00", "2000.00"),
    )

    result = evaluate(inputs, SEED)

    assert result.option_id == "stock+ABC-110"
    assert [rule.code for rule in result.rules] == ["margin", "discount", "order_value", "credit"]
    assert _verdicts(result.rules) == {
        "margin": "pass",
        "discount": "pass",
        "order_value": "pass",
        "credit": "pass",
    }
    assert result.outcome == "no_approval_needed"
    assert result.thresholds_are_examples is True
    credit = result.rules[3]
    assert (credit.actual, credit.threshold) == (Decimal("11262.50"), Decimal("30000.00"))


def test_omega_needs_no_approval() -> None:
    inputs = PolicyInputs(
        option_id="stock+supplier:Hydro-Valve",
        value=Decimal("27936.00"),
        margin_percent=Decimal("23.75"),
        discount=_discount(standard="3.00"),
        list_price=Decimal("240.00"),
        credit=_credit("40000.00", "5000.00"),
    )

    result = evaluate(inputs, SEED)

    assert set(_verdicts(result.rules).values()) == {"pass"}
    assert result.outcome == "no_approval_needed"


def test_delta_requires_supervisor() -> None:
    inputs = PolicyInputs(
        option_id="combined",
        value=Decimal("31500.00"),
        margin_percent=Decimal("14.29"),
        discount=_discount("discount_percent", "25", standard="10.00", status="above_standard"),
        list_price=Decimal("120.00"),
        # S-03 reports over_limit for the full requested quantity (54000 > 50000).
        credit=_credit("50000.00", "0.00", status="over_limit"),
    )

    result = evaluate(inputs, SEED)

    assert _verdicts(result.rules) == {
        "margin": "fail",
        "discount": "fail",
        "order_value": "fail",
        "credit": "pass",
    }
    assert result.outcome == "requires_supervisor"
    discount = result.rules[1]
    assert (discount.actual, discount.threshold) == (Decimal("25"), Decimal("15.00"))
    assert result.rules[3].reason == "Balance + selected option value within limit"


# --- Thresholds -------------------------------------------------------------------------


def test_values_exactly_at_the_thresholds_pass() -> None:
    assert evaluate_margin(Decimal("20.00"), Decimal("20.00")).verdict == "pass"
    assert evaluate_margin(Decimal("19.99"), Decimal("20.00")).verdict == "fail"
    assert (
        evaluate_discount(_discount("discount_percent", "15.00"), None, Decimal("15.00")).verdict
        == "pass"
    )
    assert (
        evaluate_discount(_discount("discount_percent", "15.01"), None, Decimal("15.00")).verdict
        == "fail"
    )
    assert evaluate_order_value(Decimal("30000.00"), Decimal("30000.00")).verdict == "pass"
    assert evaluate_order_value(Decimal("30000.01"), Decimal("30000.00")).verdict == "fail"
    assert evaluate_credit(_credit("30000.00", "20000.00"), Decimal("10000.00")).verdict == "pass"
    assert evaluate_credit(_credit("30000.00", "20000.00"), Decimal("10000.01")).verdict == "fail"


def test_missing_thresholds_are_not_evaluated() -> None:
    inputs = PolicyInputs(
        option_id="stock",
        value=Decimal("100.00"),
        margin_percent=Decimal("30.00"),
        discount=_discount(),
        list_price=Decimal("120.00"),
        credit=_credit(),
    )

    result = evaluate(inputs, NO_THRESHOLDS)

    assert _verdicts(result.rules) == {
        "margin": "not_evaluated",
        "discount": "not_evaluated",
        "order_value": "not_evaluated",
        "credit": "pass",  # uses the customer's limit, not a threshold
    }
    # The actual values are still shown.
    assert [rule.actual for rule in result.rules[:3]] == [
        Decimal("30.00"),
        Decimal("5.00"),
        Decimal("100.00"),
    ]
    assert result.outcome == "requires_supervisor"


# --- Discount ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "expected", "verdict"),
    [
        ("100.00", Decimal("16.67"), "fail"),  # (120 - 100) / 120 * 100 = 16.666…
        ("102.00", Decimal("15.00"), "pass"),
        ("110.00", Decimal("8.33"), "pass"),
        ("120.00", Decimal("0.00"), "pass"),
        ("130.00", Decimal("-8.33"), "pass"),  # above the list price: no discount
    ],
)
def test_target_price_becomes_a_discount_off_the_list_price(
    target: str, expected: Decimal, verdict: str
) -> None:
    rule = evaluate_discount(_discount("target_price", target), Decimal("120.00"), Decimal("15.00"))

    assert (rule.actual, rule.verdict) == (expected, verdict)
    assert rule.reason.startswith("Discount implied by the target price")


def test_target_price_discount_rounds_half_up() -> None:
    # (200 - 199.99) / 200 * 100 = 0.005
    assert target_price_discount(Decimal("199.99"), Decimal("200.00")) == Decimal("0.01")


@pytest.mark.parametrize("kind", ["none", "best_price"])
def test_without_a_requested_discount_the_standard_discount_is_evaluated(kind: PriceKind) -> None:
    passing = evaluate_discount(_discount(kind, standard="10.00"), None, Decimal("15.00"))
    failing = evaluate_discount(_discount(kind, standard="20.00"), None, Decimal("15.00"))

    assert (passing.actual, passing.verdict) == (Decimal("10.00"), "pass")
    assert (failing.actual, failing.verdict) == (Decimal("20.00"), "fail")
    assert passing.reason == "Standard discount within the maximum"


@pytest.mark.parametrize(
    "discount",
    [
        _discount(status="skipped", standard=None),
        _discount("target_price", "100.00", status="skipped"),
        _discount(standard=None),
        _discount("target_price", "100.00"),  # list_price is None below
        _discount("discount_percent", None),
    ],
)
def test_discount_without_data_is_not_evaluated(discount: DiscountCheck) -> None:
    rule = evaluate_discount(discount, None, Decimal("15.00"))

    assert rule.verdict == "not_evaluated"
    assert rule.threshold == Decimal("15.00")


# --- Credit -----------------------------------------------------------------------------


def test_blocked_credit_fails() -> None:
    rule = evaluate_credit(_credit("30000.00", "0.00", status="blocked"), Decimal("100.00"))

    assert rule.verdict == "fail"
    assert rule.reason == "Customer credit blocked"


def test_over_limit_with_the_selected_option() -> None:
    rule = evaluate_credit(_credit("10000.00", "5000.00", status="over_limit"), Decimal("6000.00"))

    assert (rule.verdict, rule.actual, rule.threshold) == (
        "fail",
        Decimal("11000.00"),
        Decimal("10000.00"),
    )
    assert rule.reason == "Balance + selected option value over limit"


@pytest.mark.parametrize(
    "credit",
    [
        CreditCheck(status="skipped"),
        _credit(limit=None),
        _credit(balance=None),
    ],
)
def test_credit_without_data_is_not_evaluated(credit: CreditCheck) -> None:
    assert evaluate_credit(credit, Decimal("100.00")).verdict == "not_evaluated"


# --- Outcome ----------------------------------------------------------------------------


def _rule(verdict: str) -> RuleResult:
    return RuleResult.model_validate(
        {
            "code": "margin",
            "verdict": verdict,
            "actual": None,
            "threshold": None,
            "unit": "percent",
            "reason": "test",
        }
    )


def test_outcome() -> None:
    assert outcome([_rule("pass")] * 4) == "no_approval_needed"
    assert outcome([_rule("pass")] * 3 + [_rule("fail")]) == "requires_supervisor"
    assert outcome([_rule("pass")] * 3 + [_rule("not_evaluated")]) == "requires_supervisor"


def test_one_not_evaluated_rule_requires_a_supervisor() -> None:
    inputs = PolicyInputs(
        option_id="stock",
        value=Decimal("1000.00"),
        margin_percent=Decimal("30.00"),
        discount=_discount(),
        list_price=Decimal("120.00"),
        credit=CreditCheck(status="skipped"),
    )

    result = evaluate(inputs, SEED)

    assert _verdicts(result.rules)["credit"] == "not_evaluated"
    assert [r.verdict for r in result.rules[:3]] == ["pass", "pass", "pass"]
    assert result.outcome == "requires_supervisor"


def test_result_round_trips_through_json() -> None:
    inputs = PolicyInputs(
        option_id="stock",
        value=Decimal("1000.00"),
        margin_percent=Decimal("30.00"),
        discount=_discount("target_price", "100.00"),
        list_price=Decimal("120.00"),
        credit=_credit(),
    )
    result = evaluate(inputs, SEED)

    assert type(result).model_validate(result.model_dump(mode="json")) == result


# --- Offered discount (an edited draft, S-07) -------------------------------------------


def test_without_an_offered_discount_the_rule_is_unchanged() -> None:
    for discount in (
        _discount(standard="10.00"),
        _discount("discount_percent", "25"),
        _discount("target_price", "100.00"),
        _discount(status="skipped", standard=None),
    ):
        assert evaluate_discount(
            discount, Decimal("120.00"), Decimal("15.00"), None
        ) == evaluate_discount(discount, Decimal("120.00"), Decimal("15.00"))


def test_offered_discount_equal_to_the_standard_keeps_the_stage_result() -> None:
    discount = _discount(standard="5.00")

    assert evaluate_discount(
        discount, None, Decimal("15.00"), Decimal("5.00")
    ) == evaluate_discount(discount, None, Decimal("15.00"))


def test_offered_discount_above_the_maximum_fails() -> None:
    rule = evaluate_discount(_discount(standard="5.00"), None, Decimal("15.00"), Decimal("16.67"))

    assert (rule.verdict, rule.actual, rule.threshold) == (
        "fail",
        Decimal("16.67"),
        Decimal("15.00"),
    )
    assert rule.reason == "Offered discount above the maximum"


def test_larger_offered_discount_within_the_maximum_passes() -> None:
    rule = evaluate_discount(_discount(standard="5.00"), None, Decimal("15.00"), Decimal("15.00"))

    assert (rule.verdict, rule.actual) == ("pass", Decimal("15.00"))
    assert rule.reason == "Offered discount within the maximum"


def test_requested_discount_above_the_maximum_fails_even_with_a_small_offered_one() -> None:
    rule = evaluate_discount(
        _discount("discount_percent", "25", standard="10.00", status="above_standard"),
        None,
        Decimal("15.00"),
        Decimal("10.00"),
    )

    assert (rule.verdict, rule.actual) == ("fail", Decimal("25"))
    assert rule.reason == "Requested discount above the maximum"


def test_target_price_above_the_maximum_fails_with_an_offered_discount() -> None:
    rule = evaluate_discount(
        _discount("target_price", "100.00"), Decimal("120.00"), Decimal("15.00"), Decimal("5.00")
    )

    assert (rule.verdict, rule.actual) == ("fail", Decimal("16.67"))
    assert rule.reason == "Discount implied by the target price above the maximum"


@pytest.mark.parametrize(
    ("offered", "verdict"), [(Decimal("15.00"), "pass"), (Decimal("15.01"), "fail")]
)
def test_offered_discount_decides_when_the_requested_one_is_not_evaluated(
    offered: Decimal, verdict: str
) -> None:
    for discount in (
        _discount(status="skipped", standard=None),
        _discount("target_price", "100.00"),  # no list price
        _discount("discount_percent", None),
    ):
        rule = evaluate_discount(discount, None, Decimal("15.00"), offered)

        assert (rule.verdict, rule.actual) == (verdict, offered)
        assert rule.reason.startswith("Offered discount")


def test_offered_discount_without_a_maximum_is_not_evaluated() -> None:
    rule = evaluate_discount(_discount(standard="5.00"), None, None, Decimal("8.00"))

    assert (rule.verdict, rule.actual, rule.threshold) == ("not_evaluated", Decimal("8.00"), None)


def test_evaluate_passes_the_offered_discount_to_the_rule() -> None:
    inputs = PolicyInputs(
        option_id="stock+ABC-110",
        value=Decimal("8562.50"),
        margin_percent=Decimal("19.42"),
        discount=_discount(standard="5.00"),
        list_price=Decimal("120.00"),
        credit=_credit("30000.00", "2000.00"),
        offered_discount_percent=Decimal("16.67"),
    )

    result = evaluate(inputs, SEED)

    assert _verdicts(result.rules) == {
        "margin": "fail",
        "discount": "fail",
        "order_value": "pass",
        "credit": "pass",
    }
    assert result.outcome == "requires_supervisor"
