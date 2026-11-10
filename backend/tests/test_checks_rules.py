from datetime import date
from decimal import Decimal

import pytest

from app.checks.rules import (
    CustomerRecord,
    ProductRecord,
    evaluate,
    match_customer,
    normalize_name,
)
from app.parsing.analyze import build_parsed
from app.parsing.fake import RuleBasedExtractor
from app.parsing.schema import ParsedFields
from tests.test_parsing_extractors import ACME, BIURO_MAX, DELTA, OMEGA


def _seed_customer(
    id: int, name: str, domain: str, discount: str, limit: str, balance: str
) -> CustomerRecord:
    return CustomerRecord(
        id=id,
        name=name,
        email_domain=domain,
        standard_discount_percent=Decimal(discount),
        credit_limit=Decimal(limit),
        credit_balance=Decimal(balance),
        credit_blocked=False,
    )


# The company seed (migrations/versions/0006_company_data_and_checks.py).
SEED_CUSTOMERS = (
    _seed_customer(1, "ACME", "acme.example", "5.00", "30000.00", "2000.00"),
    _seed_customer(2, "Biuro Max", "biuromax.example", "0.00", "10000.00", "0.00"),
    _seed_customer(3, "Hurtownia Delta", "hurtowniadelta.example", "10.00", "50000.00", "0.00"),
    _seed_customer(4, "Technika Omega", "technikaomega.example", "3.00", "40000.00", "5000.00"),
)
SEED_PRODUCTS = (
    ProductRecord(1, "ABC-100", "Czujnik ciśnienia ABC-100", Decimal("120.00"), 50),
    ProductRecord(2, "ABC-200", "Moduł sterujący ABC-200", Decimal("85.00"), 150),
    ProductRecord(3, "XYZ-300", "Zawór proporcjonalny XYZ-300", Decimal("240.00"), 60),
)


def _seed_fields(inquiry: tuple[str, str, date]) -> ParsedFields:
    """Fields the rule-based parser reads from a seed inquiry."""
    subject, body, reference_date = inquiry
    extraction = RuleBasedExtractor().extract(subject, body, reference_date)
    fields, _ = build_parsed(extraction.extraction, reference_date)
    return fields


def _fields(**overrides: object) -> ParsedFields:
    values: dict[str, object] = {
        "customer": "Biuro Max",
        "product_code": "ABC-200",
        "quantity": 20,
        "deadline": None,
        "deadline_text": None,
        "substitute_allowed": None,
        "price_kind": "none",
        "price_value": None,
        "price_text": None,
    }
    values.update(overrides)
    return ParsedFields.model_validate(values)


def _customer(**overrides: object) -> CustomerRecord:
    values: dict[str, object] = {
        "id": 10,
        "name": "Biuro Max",
        "email_domain": "biuromax.example",
        "standard_discount_percent": Decimal("0.00"),
        "credit_limit": Decimal("10000.00"),
        "credit_balance": Decimal("0.00"),
        "credit_blocked": False,
    }
    values.update(overrides)
    return CustomerRecord(**values)  # type: ignore[arg-type]


def _product(**overrides: object) -> ProductRecord:
    values: dict[str, object] = {
        "id": 20,
        "code": "ABC-200",
        "name": "Moduł sterujący ABC-200",
        "list_price": Decimal("85.00"),
        "stock_quantity": 150,
    }
    values.update(overrides)
    return ProductRecord(**values)  # type: ignore[arg-type]


# --- Seed inquiries -------------------------------------------------------------------


def test_seed_biuro_max_is_standard() -> None:
    result = evaluate(
        _seed_fields(BIURO_MAX), "biuro@biuromax.example", SEED_CUSTOMERS, SEED_PRODUCTS
    )

    assert (result.outcome, result.exception_type) == ("standard", None)
    checks = result.results
    assert checks.customer.status == "matched"
    assert checks.customer.matched_by == "name"
    assert checks.customer.name == "Biuro Max"
    assert (checks.stock.status, checks.stock.requested, checks.stock.available) == ("ok", 20, 150)
    assert checks.price.unit_price == Decimal("85.00")
    assert checks.price.total == Decimal("1700.00")
    assert checks.discount.status == "ok"
    assert checks.discount.standard_percent == Decimal("0.00")
    assert checks.credit.status == "ok"
    assert checks.reasons == []


def test_seed_acme_is_exception_with_shortage() -> None:
    result = evaluate(_seed_fields(ACME), "zakupy@acme.example", SEED_CUSTOMERS, SEED_PRODUCTS)

    assert (result.outcome, result.exception_type) == ("exception", "insufficient_stock")
    checks = result.results
    assert checks.customer.name == "ACME"
    assert checks.customer.matched_by == "name"
    assert checks.stock.status == "insufficient"
    assert (checks.stock.requested, checks.stock.available, checks.stock.shortage) == (80, 50, 30)
    assert checks.price.unit_price == Decimal("114.00")
    assert checks.price.total == Decimal("9120.00")
    assert checks.discount.requested_kind == "best_price"
    assert checks.discount.status == "ok"
    assert checks.credit.status == "ok"


def test_seed_delta_is_exception_above_standard_and_over_limit() -> None:
    result = evaluate(
        _seed_fields(DELTA), "handel@hurtowniadelta.example", SEED_CUSTOMERS, SEED_PRODUCTS
    )

    assert (result.outcome, result.exception_type) == ("exception", "insufficient_stock")
    checks = result.results
    assert checks.customer.name == "Hurtownia Delta"
    assert checks.stock.shortage == 450
    assert checks.price.unit_price == Decimal("108.00")
    assert checks.price.total == Decimal("54000.00")
    assert checks.discount.status == "above_standard"
    assert checks.discount.standard_percent == Decimal("10.00")
    assert checks.discount.requested_kind == "discount_percent"
    assert checks.discount.requested_value == Decimal("25")
    assert checks.credit.status == "over_limit"
    assert checks.credit.order_value == Decimal("54000.00")


def test_seed_omega_is_exception() -> None:
    result = evaluate(
        _seed_fields(OMEGA), "zaopatrzenie@technikaomega.example", SEED_CUSTOMERS, SEED_PRODUCTS
    )

    assert (result.outcome, result.exception_type) == ("exception", "insufficient_stock")
    checks = result.results
    assert checks.customer.name == "Technika Omega"
    assert (checks.stock.requested, checks.stock.available, checks.stock.shortage) == (120, 60, 60)
    assert checks.price.unit_price == Decimal("232.80")
    assert checks.price.total == Decimal("27936.00")
    assert checks.credit.status == "ok"


# --- Customer matching ----------------------------------------------------------------


def test_normalize_name_drops_legal_forms_and_punctuation() -> None:
    assert normalize_name("Dział zakupów, ACME Sp. z o.o.") == ["dział", "zakupów", "acme"]
    assert normalize_name("Delta S.A.") == ["delta"]
    assert normalize_name("Omega sp.j.") == ["omega"]
    assert normalize_name("Max  Sp. k.!") == ["max"]


def test_customer_matched_by_name_inside_signature() -> None:
    check, record = match_customer(
        _fields(customer="Dział zakupów, ACME Sp. z o.o."), "x@other.example", SEED_CUSTOMERS
    )

    assert (check.status, check.matched_by, check.name) == ("matched", "name", "ACME")
    assert check.customer_id == 1
    assert record is SEED_CUSTOMERS[0]


@pytest.mark.parametrize("customer", [None, "   "])
def test_empty_customer_matched_by_email(customer: str | None) -> None:
    check, record = match_customer(
        _fields(customer=customer), "zakupy@ACME.example", SEED_CUSTOMERS
    )

    assert (check.status, check.matched_by, check.name) == ("matched", "email", "ACME")
    assert record is SEED_CUSTOMERS[0]


def test_empty_customer_without_email_match_is_missing() -> None:
    check, record = match_customer(_fields(customer=None), "a@unknown.example", SEED_CUSTOMERS)

    assert (check.status, check.matched_by, record) == ("missing", None, None)


def test_filled_customer_without_hit_does_not_fall_back_to_email() -> None:
    check, record = match_customer(
        _fields(customer="Firma Krzak"), "zakupy@acme.example", SEED_CUSTOMERS
    )

    assert (check.status, record) == ("not_found", None)


def test_two_name_hits_are_ambiguous() -> None:
    customers = (*SEED_CUSTOMERS, _customer(id=5, name="Max", email_domain="max.example"))

    check, record = match_customer(_fields(customer="Biuro Max"), "", customers)

    assert (check.status, record) == ("ambiguous", None)
    assert check.candidates == ["Biuro Max", "Max"]


def test_part_of_name_does_not_match() -> None:
    check, _ = match_customer(_fields(customer="Max"), "biuro@biuromax.example", SEED_CUSTOMERS)

    assert check.status == "not_found"


def test_name_matches_whole_words_only() -> None:
    check, _ = match_customer(_fields(customer="ACMEX Sp. z o.o."), "", SEED_CUSTOMERS)

    assert check.status == "not_found"


def test_product_code_ignores_case_and_spaces() -> None:
    result = evaluate(_fields(product_code=" abc-200 "), "", [_customer()], [_product()])

    assert result.outcome == "standard"
    assert result.results.stock.product_code == "ABC-200"


# --- Boundaries -----------------------------------------------------------------------


def test_quantity_equal_to_stock_is_standard() -> None:
    result = evaluate(_fields(quantity=150), "", [_customer()], [_product(stock_quantity=150)])

    assert result.outcome == "standard"
    assert result.results.stock.status == "ok"
    assert result.results.stock.shortage == 0


def test_zero_stock_is_exception() -> None:
    result = evaluate(_fields(quantity=1), "", [_customer()], [_product(stock_quantity=0)])

    assert (result.outcome, result.exception_type) == ("exception", "insufficient_stock")
    assert result.results.stock.shortage == 1


@pytest.mark.parametrize(
    ("overrides", "sender", "reason"),
    [
        ({"customer": None}, "a@unknown.example", "customer_missing"),
        ({"customer": "Nieznana Firma"}, "biuro@biuromax.example", "customer_not_found"),
        ({"customer": "Biuro Max"}, "", "customer_ambiguous"),
        ({"product_code": None}, "", "product_missing"),
        ({"product_code": "ABC-999"}, "", "product_not_found"),
        ({"quantity": None}, "", "quantity_missing"),
    ],
)
def test_each_needs_input_reason(overrides: dict[str, object], sender: str, reason: str) -> None:
    customers = [_customer(), _customer(id=11, name="Max", email_domain="max.example")]
    if reason != "customer_ambiguous":
        customers = customers[:1]

    result = evaluate(_fields(**overrides), sender, customers, [_product()])

    assert (result.outcome, result.exception_type) == ("needs_input", None)
    assert result.results.reasons == [reason]


def test_needs_input_wins_over_exception_and_lists_all_reasons() -> None:
    result = evaluate(
        _fields(customer="Nieznana", quantity=500), "", [_customer()], [_product(stock_quantity=1)]
    )

    assert result.outcome == "needs_input"
    assert result.results.reasons == ["customer_not_found"]
    # Stock is checked without the customer; price, discount and credit are skipped.
    assert result.results.stock.status == "insufficient"
    assert result.results.price.status == "skipped"
    assert result.results.discount.status == "skipped"
    assert result.results.credit.status == "skipped"


def test_missing_product_skips_stock_price_and_credit() -> None:
    result = evaluate(_fields(product_code="ABC-999"), "", [_customer()], [_product()])

    checks = result.results
    assert (checks.stock.status, checks.stock.product_code) == ("skipped", "ABC-999")
    assert checks.price.status == "skipped"
    assert checks.discount.status == "ok"
    assert checks.credit.status == "skipped"


def test_missing_quantity_skips_stock_total_and_credit() -> None:
    result = evaluate(_fields(quantity=None), "", [_customer()], [_product()])

    checks = result.results
    assert (checks.stock.status, checks.stock.available) == ("skipped", 150)
    assert (checks.price.status, checks.price.unit_price) == ("ok", Decimal("85.00"))
    assert checks.price.total is None
    assert checks.credit.status == "skipped"


def test_absurd_quantity_skips_price_and_credit() -> None:
    # The total would need more digits than the decimal context holds.
    result = evaluate(
        _fields(quantity=10**30, price_kind="target_price", price_value="80"),
        "",
        [_customer()],
        [_product()],
    )

    checks = result.results
    assert (checks.price.status, checks.price.total) == ("skipped", None)
    assert checks.discount.status == "skipped"
    assert checks.credit.status == "skipped"
    assert checks.stock.status == "insufficient"


def test_price_rounds_half_up_to_cents() -> None:
    # 10.05 x 0.95 = 9.5475 -> 9.55; 9.55 x 3 = 28.65
    result = evaluate(
        _fields(quantity=3),
        "",
        [_customer(standard_discount_percent=Decimal("5.00"))],
        [_product(list_price=Decimal("10.05"))],
    )

    assert result.results.price.unit_price == Decimal("9.55")
    assert result.results.price.total == Decimal("28.65")


def test_price_rounds_a_half_cent_up() -> None:
    # 0.25 x 0.90 = 0.225 -> 0.23
    result = evaluate(
        _fields(quantity=1),
        "",
        [_customer(standard_discount_percent=Decimal("10.00"))],
        [_product(list_price=Decimal("0.25"))],
    )

    assert result.results.price.unit_price == Decimal("0.23")


# --- Discount and credit --------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "value", "status"),
    [
        ("discount_percent", "5", "ok"),
        ("discount_percent", "5.01", "above_standard"),
        ("target_price", "80.75", "ok"),  # standard unit price is 85.00 x 0.95 = 80.75
        ("target_price", "80.74", "above_standard"),
        ("best_price", None, "ok"),
    ],
)
def test_discount_above_standard(kind: str, value: str | None, status: str) -> None:
    result = evaluate(
        _fields(price_kind=kind, price_value=value),
        "",
        [_customer(standard_discount_percent=Decimal("5.00"))],
        [_product()],
    )

    assert result.results.discount.status == status
    assert result.results.discount.requested_kind == kind
    assert result.outcome == "standard"  # informational only


def test_target_price_without_a_standard_price_is_skipped() -> None:
    result = evaluate(
        _fields(product_code="ABC-999", price_kind="target_price", price_value="80"),
        "",
        [_customer(standard_discount_percent=Decimal("5.00"))],
        [_product()],
    )

    discount = result.results.discount
    assert result.results.price.status == "skipped"
    assert (discount.status, discount.standard_percent) == ("skipped", Decimal("5.00"))
    assert (discount.requested_kind, discount.requested_value) == ("target_price", Decimal("80"))


@pytest.mark.parametrize(
    ("balance", "blocked", "status"),
    [
        ("8300.00", False, "ok"),  # 8300 + 1700 = 10000, not above the limit
        ("8300.01", False, "over_limit"),
        ("0.00", True, "blocked"),
    ],
)
def test_credit_status(balance: str, blocked: bool, status: str) -> None:
    customer = _customer(credit_balance=Decimal(balance), credit_blocked=blocked)

    result = evaluate(_fields(), "", [customer], [_product()])

    assert result.results.credit.status == status
    assert result.outcome == "standard"  # informational only


def test_results_round_trip_through_json() -> None:
    result = evaluate(
        _seed_fields(DELTA), "handel@hurtowniadelta.example", SEED_CUSTOMERS, SEED_PRODUCTS
    )

    stored = result.results.model_dump(mode="json")

    assert stored["price"]["total"] == "54000.00"
    assert "outcome" not in stored
    assert type(result.results).model_validate(stored) == result.results
