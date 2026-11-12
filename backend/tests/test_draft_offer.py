"""Draft offer core on in-memory data: the offer of an option, edits with recomputation, the
offered discount and policy input, and the e-mail subject and body. No database, no model."""

import re
from decimal import Decimal
from typing import Any

import pytest

from app.checks.schema import CheckResults
from app.draft.offer import (
    InvalidEdit,
    LineEdit,
    apply_edit,
    format_amount,
    offer_from_option,
    offer_policy_inputs,
    offered_discount,
    render_body,
    render_subject,
)
from app.draft.schema import DraftText
from app.policy.rules import PolicyInputs, PolicyThresholds, evaluate
from app.recommendation.schema import RecommendationOption

# Seed data (migrations 0006, 0007, 0009) and the options of tests/test_recommendation_core.py.
LIST_PRICES = {
    "ABC-100": Decimal("120.00"),
    "ABC-110": Decimal("125.00"),
    "XYZ-300": Decimal("240.00"),
}
SEED = PolicyThresholds(
    margin_min_percent=Decimal("20.00"),
    discount_max_percent=Decimal("15.00"),
    order_value_max=Decimal("30000.00"),
    are_examples=True,
)


def _line(
    code: str,
    name: str,
    source: str,
    quantity: int,
    price: str,
    cost: str,
    available_on: str,
    supplier: str | None = None,
) -> dict[str, Any]:
    return {
        "product_code": code,
        "product_name": name,
        "source": source,
        "supplier": supplier,
        "quantity": quantity,
        "available_on": available_on,
        "unit_price": price,
        "unit_cost": cost,
        "value": str(Decimal(price) * quantity),
        "cost": str(Decimal(cost) * quantity),
    }


def _option(
    option_id: str, kind: str, lines: list[dict[str, Any]], **rest: Any
) -> RecommendationOption:
    return RecommendationOption.model_validate(
        {"id": option_id, "kind": kind, "lines": lines, "band": "HIGH", "signals": [], **rest}
    )


ABC_100 = "Czujnik ciśnienia ABC-100"
ABC_110 = "Czujnik ciśnienia ABC-110"
XYZ_300 = "Zawór proporcjonalny XYZ-300"

# ACME 80x ABC-100, 5% discount: own stock and the substitute.
ACME = _option(
    "stock+ABC-110",
    "substitute",
    [
        _line("ABC-100", ABC_100, "stock", 50, "114.00", "84.00", "2026-11-02"),
        _line("ABC-110", ABC_110, "substitute_stock", 30, "118.75", "90.00", "2026-11-02"),
    ],
    covered_quantity=80,
    requested_quantity=80,
    fulfilled_on="2026-11-02",
    meets_deadline=True,
    value="9262.50",
    cost="6900.00",
    margin_percent="25.51",
)
# Delta 500x ABC-100, 10% discount: stock, substitute and supplier, no deadline.
DELTA = _option(
    "stock+ABC-110+supplier:Sensortech Polska",
    "combined",
    [
        _line("ABC-100", ABC_100, "stock", 50, "108.00", "84.00", "2026-11-03"),
        _line("ABC-110", ABC_110, "substitute_stock", 40, "112.50", "90.00", "2026-11-03"),
        _line(
            "ABC-100",
            ABC_100,
            "supplier",
            200,
            "108.00",
            "96.00",
            "2026-11-10",
            supplier="Sensortech Polska",
        ),
    ],
    covered_quantity=290,
    requested_quantity=500,
    fulfilled_on="2026-11-10",
    meets_deadline=None,
    value="31500.00",
    cost="27000.00",
    margin_percent="14.29",
)
# Omega 120x XYZ-300, 3% discount: own stock and a supplier of the same product.
OMEGA = _option(
    "stock+supplier:Hydro-Valve",
    "other_source",
    [
        _line("XYZ-300", XYZ_300, "stock", 60, "232.80", "170.00", "2026-11-05"),
        _line(
            "XYZ-300",
            XYZ_300,
            "supplier",
            60,
            "232.80",
            "185.00",
            "2026-11-10",
            supplier="Hydro-Valve",
        ),
    ],
    covered_quantity=120,
    requested_quantity=120,
    fulfilled_on="2026-11-10",
    meets_deadline=True,
    value="27936.00",
    cost="21300.00",
    margin_percent="23.75",
)


def _checks(
    *,
    standard: str,
    kind: str = "none",
    requested: str | None = None,
    discount_status: str = "ok",
    limit: str = "30000.00",
    balance: str = "2000.00",
    credit_status: str = "ok",
) -> CheckResults:
    return CheckResults.model_validate(
        {
            "customer": {"status": "matched", "matched_by": "email", "customer_id": 1},
            "stock": {"status": "insufficient", "product_code": "ABC-100"},
            "price": {"status": "ok", "list_price": "120.00", "discount_percent": standard},
            "discount": {
                "status": discount_status,
                "standard_percent": standard,
                "requested_kind": kind,
                "requested_value": requested,
            },
            "credit": {"status": credit_status, "limit": limit, "balance": balance},
        }
    )


ACME_CHECKS = _checks(standard="5.00")
DELTA_CHECKS = _checks(
    standard="10.00",
    kind="discount_percent",
    requested="25",
    discount_status="above_standard",
    limit="50000.00",
    balance="0.00",
    credit_status="over_limit",
)


def _unchanged(option: RecommendationOption) -> list[LineEdit]:
    return [
        LineEdit(product_code=line.product_code, quantity=line.quantity, unit_price=line.unit_price)
        for line in option.lines
    ]


def _stage_inputs(option: RecommendationOption, checks: CheckResults) -> PolicyInputs:
    """The policy stage's input of the option as recommended (policy/service.py)."""
    return PolicyInputs(
        option_id=option.id,
        value=option.value,
        margin_percent=option.margin_percent,
        discount=checks.discount,
        list_price=checks.price.list_price,
        credit=checks.credit,
    )


# --- Offer of an option -----------------------------------------------------------------


def test_offer_of_acme_is_the_option_with_list_prices() -> None:
    offer = offer_from_option(ACME, LIST_PRICES)

    assert offer.option_id == "stock+ABC-110"
    assert offer.kind == "substitute"
    assert offer.edited is False
    assert [(line.product_code, line.list_price, line.unit_price) for line in offer.lines] == [
        ("ABC-100", Decimal("120.00"), Decimal("114.00")),
        ("ABC-110", Decimal("125.00"), Decimal("118.75")),
    ]
    assert (offer.value, offer.cost, offer.margin_percent) == (
        Decimal("9262.50"),
        Decimal("6900.00"),
        Decimal("25.51"),
    )
    assert (offer.covered_quantity, offer.requested_quantity) == (80, 80)
    assert (str(offer.fulfilled_on), offer.meets_deadline) == ("2026-11-02", True)


def test_offer_of_delta_keeps_the_supplier_line() -> None:
    offer = offer_from_option(DELTA, LIST_PRICES)

    assert [(line.source, line.supplier, line.quantity) for line in offer.lines] == [
        ("stock", None, 50),
        ("substitute_stock", None, 40),
        ("supplier", "Sensortech Polska", 200),
    ]
    assert (offer.covered_quantity, offer.requested_quantity) == (290, 500)
    assert offer.meets_deadline is None
    assert offer.value == Decimal("31500.00")


# --- Edit -------------------------------------------------------------------------------


def test_unchanged_edit_keeps_the_numbers() -> None:
    edited = apply_edit(ACME, _unchanged(ACME), LIST_PRICES)

    assert edited.edited is True
    assert edited.model_copy(update={"edited": False}) == offer_from_option(ACME, LIST_PRICES)


def test_edit_of_price_and_quantity_recomputes_value_cost_and_margin() -> None:
    edits = [
        LineEdit(product_code="ABC-110", quantity=20, unit_price=Decimal("118.75")),
        LineEdit(product_code="ABC-100", quantity=50, unit_price=Decimal("100.00")),
    ]

    offer = apply_edit(ACME, edits, LIST_PRICES)

    assert [(line.quantity, line.unit_price, line.value, line.cost) for line in offer.lines] == [
        (50, Decimal("100.00"), Decimal("5000.00"), Decimal("4200.00")),
        (20, Decimal("118.75"), Decimal("2375.00"), Decimal("1800.00")),
    ]
    assert (offer.value, offer.cost) == (Decimal("7375.00"), Decimal("6000.00"))
    # (7375 - 6000) / 7375 * 100 = 18.644…
    assert offer.margin_percent == Decimal("18.64")
    assert (offer.covered_quantity, offer.requested_quantity) == (70, 80)
    # Dates are those of the option.
    assert (str(offer.fulfilled_on), offer.meets_deadline) == ("2026-11-02", True)
    assert [line.list_price for line in offer.lines] == [Decimal("120.00"), Decimal("125.00")]


def test_edits_of_lines_sharing_a_code_apply_in_line_order() -> None:
    edits = [
        LineEdit(product_code="XYZ-300", quantity=60, unit_price=Decimal("230.00")),
        LineEdit(product_code="XYZ-300", quantity=40, unit_price=Decimal("235.00")),
    ]

    offer = apply_edit(OMEGA, edits, LIST_PRICES)

    assert [(line.source, line.quantity, line.unit_price) for line in offer.lines] == [
        ("stock", 60, Decimal("230.00")),
        ("supplier", 40, Decimal("235.00")),
    ]
    assert [line.cost for line in offer.lines] == [Decimal("10200.00"), Decimal("7400.00")]
    assert (offer.value, offer.covered_quantity) == (Decimal("23200.00"), 100)


def _edit(code: str, quantity: int = 1, price: str = "100.00") -> LineEdit:
    return LineEdit(product_code=code, quantity=quantity, unit_price=Decimal(price))


@pytest.mark.parametrize(
    "edits",
    [
        pytest.param([_edit("ABC-100"), _edit("XYZ-300")], id="foreign code"),
        pytest.param([_edit("ABC-100")], id="missing line"),
        pytest.param([_edit("ABC-100"), _edit("ABC-110"), _edit("ABC-110")], id="extra line"),
        pytest.param([_edit("ABC-100"), _edit("ABC-100")], id="same code twice"),
        pytest.param([_edit("ABC-100", quantity=0), _edit("ABC-110")], id="zero quantity"),
        pytest.param([_edit("ABC-100", quantity=-5), _edit("ABC-110")], id="negative quantity"),
        pytest.param([_edit("ABC-100", price="0.00"), _edit("ABC-110")], id="zero price"),
        pytest.param([_edit("ABC-100", price="-1.00"), _edit("ABC-110")], id="negative price"),
        pytest.param([_edit("ABC-100", price="99.999"), _edit("ABC-110")], id="sub-cent price"),
        pytest.param([], id="no lines"),
    ],
)
def test_invalid_edit_is_rejected(edits: list[LineEdit]) -> None:
    with pytest.raises(InvalidEdit):
        apply_edit(ACME, edits, LIST_PRICES)


# --- Offered discount and policy input --------------------------------------------------


def test_offered_discount_of_the_recommended_offer_is_the_standard_discount() -> None:
    assert offered_discount(offer_from_option(ACME, LIST_PRICES)) == Decimal("5.00")
    assert offered_discount(offer_from_option(DELTA, LIST_PRICES)) == Decimal("10.00")
    assert offered_discount(offer_from_option(OMEGA, LIST_PRICES)) == Decimal("3.00")


@pytest.mark.parametrize(
    ("price", "discount", "verdict"),
    [
        ("102.00", Decimal("15.00"), "pass"),  # (120 - 102) / 120 = exactly 15 %
        ("101.99", Decimal("15.01"), "fail"),
        ("130.00", Decimal("5.00"), "pass"),  # above the list price: the other line decides
    ],
)
def test_offered_discount_at_the_threshold(price: str, discount: Decimal, verdict: str) -> None:
    edits = [
        LineEdit(product_code="ABC-100", quantity=50, unit_price=Decimal(price)),
        LineEdit(product_code="ABC-110", quantity=30, unit_price=Decimal("118.75")),
    ]
    offer = apply_edit(ACME, edits, LIST_PRICES)

    assert offered_discount(offer) == discount
    rule = evaluate(offer_policy_inputs(offer, ACME_CHECKS), SEED).rules[1]
    assert (rule.code, rule.verdict, rule.actual) == ("discount", verdict, discount)


def test_policy_inputs_of_an_offer() -> None:
    offer = apply_edit(ACME, _unchanged(ACME), LIST_PRICES)

    inputs = offer_policy_inputs(offer, ACME_CHECKS)

    assert inputs == PolicyInputs(
        option_id="stock+ABC-110",
        value=Decimal("9262.50"),
        margin_percent=Decimal("25.51"),
        discount=ACME_CHECKS.discount,
        list_price=Decimal("120.00"),
        credit=ACME_CHECKS.credit,
        offered_discount_percent=Decimal("5.00"),
    )


@pytest.mark.parametrize(
    ("option", "checks"), [(ACME, ACME_CHECKS), (DELTA, DELTA_CHECKS), (OMEGA, ACME_CHECKS)]
)
def test_unchanged_edit_gives_the_stage_verdict(
    option: RecommendationOption, checks: CheckResults
) -> None:
    offer = apply_edit(option, _unchanged(option), LIST_PRICES)

    assert evaluate(offer_policy_inputs(offer, checks), SEED) == evaluate(
        _stage_inputs(option, checks), SEED
    )


def test_price_cut_below_the_discount_threshold_requires_a_supervisor() -> None:
    edits = [
        LineEdit(product_code="ABC-100", quantity=50, unit_price=Decimal("100.00")),
        LineEdit(product_code="ABC-110", quantity=30, unit_price=Decimal("118.75")),
    ]
    result = evaluate(offer_policy_inputs(apply_edit(ACME, edits, LIST_PRICES), ACME_CHECKS), SEED)

    discount = result.rules[1]
    assert (discount.verdict, discount.actual) == ("fail", Decimal("16.67"))
    assert discount.reason == "Offered discount above the maximum"
    assert result.outcome == "requires_supervisor"


# --- E-mail -----------------------------------------------------------------------------

TEXT = DraftText(
    intro="Dziękujemy za zapytanie. Poniżej przesyłamy propozycję realizacji zamówienia.",
    closing="Prosimy o potwierdzenie wybranego wariantu.",
    source="model",
)


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Zapytanie o czujniki ABC-100", "Re: Zapytanie o czujniki ABC-100"),
        ("  Zamówienie  ", "Re: Zamówienie"),
        ("RE: Zamówienie", "RE: Zamówienie"),
        ("Re: Zamówienie", "Re: Zamówienie"),
    ],
)
def test_render_subject(subject: str, expected: str) -> None:
    assert render_subject(subject) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("31500"), "31 500,00"),
        (Decimal("118.75"), "118,75"),
        (Decimal("0.5"), "0,50"),
        (Decimal("1234567.891"), "1 234 567,89"),
    ],
)
def test_format_amount_is_polish(amount: Decimal, expected: str) -> None:
    assert format_amount(amount) == expected


def test_render_body_of_acme() -> None:
    body = render_body(offer_from_option(ACME, LIST_PRICES), TEXT, "Jan Nowak")

    assert body == "\n".join(
        [
            "Dzień dobry,",
            "",
            TEXT.intro,
            "",
            "Proponowane pozycje:",
            "- Czujnik ciśnienia ABC-100 (ABC-100): 50 szt. × 114,00 PLN netto = 5 700,00 PLN "
            "netto, dostępne od 02.11.2026",
            "- Czujnik ciśnienia ABC-110 (ABC-110): 30 szt. × 118,75 PLN netto = 3 562,50 PLN "
            "netto, dostępne od 02.11.2026",
            "",
            "Razem: 9 262,50 PLN netto.",
            "Termin realizacji: 02.11.2026.",
            "",
            TEXT.closing,
            "",
            "Z poważaniem",
            "Dział sprzedaży",
        ]
    )


def test_render_body_has_numbers_only_in_the_offer_lines() -> None:
    offer = offer_from_option(DELTA, LIST_PRICES)

    body = render_body(offer, TEXT, "Jan Nowak")

    with_digits = [line for line in body.splitlines() if re.search(r"\d", line)]
    assert with_digits == [
        "- Czujnik ciśnienia ABC-100 (ABC-100): 50 szt. × 108,00 PLN netto = 5 400,00 PLN "
        "netto, dostępne od 03.11.2026",
        "- Czujnik ciśnienia ABC-110 (ABC-110): 40 szt. × 112,50 PLN netto = 4 500,00 PLN "
        "netto, dostępne od 03.11.2026",
        "- Czujnik ciśnienia ABC-100 (ABC-100): 200 szt. × 108,00 PLN netto = 21 600,00 PLN "
        "netto, dostępne od 10.11.2026",
        "Razem: 31 500,00 PLN netto.",
        "Termin realizacji: 10.11.2026.",
    ]
    assert TEXT.intro in body
    assert TEXT.closing in body
