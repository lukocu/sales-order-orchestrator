"""Field scoring of the parser field eval: outcomes and summaries. No database."""

from datetime import date
from decimal import Decimal
from typing import Any

from app.eval.fields.cases import FieldCase, FieldTag
from app.eval.fields.scoring import FieldOutcome, score_case, summarize
from app.parsing.schema import FieldName, ParsedFields, PriceKind


def _case(tags: list[FieldTag] | None = None, **expected: Any) -> FieldCase:
    fields: dict[str, Any] = {
        "customer": {"value": "ACME"},
        "product_code": {"value": "ABC-200"},
        "quantity": {"value": 80},
        "deadline": {"value": "2026-11-06"},
        "substitute_allowed": {"value": True},
        "price": {"kind": "none"},
    }
    return FieldCase.model_validate(
        {
            "id": "case",
            "subject": "s",
            "body": "b",
            "received_at": "2026-11-02T08:15:00Z",
            "expected": fields | expected,
            "rationale": "r",
            "tags": tags or [],
        }
    )


def _parsed(
    *,
    customer: str | None = "ACME",
    product_code: str | None = "ABC-200",
    quantity: int | None = 80,
    deadline: date | None = date(2026, 11, 6),
    substitute_allowed: bool | None = True,
    price_kind: PriceKind = "none",
    price_value: Decimal | None = None,
) -> ParsedFields:
    return ParsedFields(
        customer=customer,
        product_code=product_code,
        quantity=quantity,
        deadline=deadline,
        deadline_text=None,
        substitute_allowed=substitute_allowed,
        price_kind=price_kind,
        price_value=price_value,
        price_text=None,
    )


def test_everything_right_is_all_hits() -> None:
    outcomes = score_case(_case(), _parsed(), {})

    assert set(outcomes.values()) == {"hit"}
    assert set(outcomes) == {
        "customer",
        "product_code",
        "quantity",
        "deadline",
        "substitute_allowed",
        "price",
    }


def test_each_field_has_all_three_outcomes() -> None:
    wrong: dict[FieldName, ParsedFields] = {
        "customer": _parsed(customer="Biuro Max"),
        "product_code": _parsed(product_code="XYZ-300"),
        "quantity": _parsed(quantity=81),
        "deadline": _parsed(deadline=date(2026, 11, 7)),
        "substitute_allowed": _parsed(substitute_allowed=False),
        "price": _parsed(price_kind="best_price"),
    }
    for field, parsed in wrong.items():
        silent = score_case(_case(), parsed, {})
        flagged = score_case(_case(), parsed, {field: "unsure"})

        assert silent[field] == "silent_wrong", field
        assert flagged[field] == "flagged_miss", field
        assert {name: o for name, o in silent.items() if name != field} == {
            name: "hit" for name in silent if name != field
        }


def test_a_flag_on_a_correct_field_is_still_a_hit() -> None:
    assert score_case(_case(), _parsed(), {"quantity": "Missing"})["quantity"] == "hit"


def test_a_required_flag_is_part_of_a_hit() -> None:
    case = _case(deadline={"value": "2026-11-06", "flagged": True})

    assert score_case(case, _parsed(), {"deadline": "Ambiguous phrase"})["deadline"] == "hit"
    assert score_case(case, _parsed(), {})["deadline"] == "silent_wrong"


def test_a_null_label_needs_a_null_result_and_the_flag() -> None:
    case = _case(
        deadline={"value": None, "flagged": True}, quantity={"value": None, "flagged": True}
    )
    parsed = _parsed(deadline=None, quantity=None)

    both = score_case(case, parsed, {"deadline": "Could not resolve", "quantity": "Missing"})
    assert both["deadline"] == "hit"
    assert both["quantity"] == "hit"

    unflagged = score_case(case, parsed, {})
    assert unflagged["deadline"] == "silent_wrong"
    assert unflagged["quantity"] == "silent_wrong"

    guessed = score_case(case, _parsed(), {"deadline": "Resolved by model only"})
    assert guessed["deadline"] == "flagged_miss"
    assert guessed["quantity"] == "silent_wrong"


def test_an_absent_deadline_label_is_a_plain_hit() -> None:
    case = _case(deadline={"value": None})

    assert score_case(case, _parsed(deadline=None), {})["deadline"] == "hit"
    assert score_case(case, _parsed(), {})["deadline"] == "silent_wrong"


def test_a_missing_value_for_a_present_label_is_wrong() -> None:
    outcomes = score_case(_case(), _parsed(customer=None, substitute_allowed=None), {})

    assert outcomes["customer"] == "silent_wrong"
    assert outcomes["substitute_allowed"] == "silent_wrong"


def test_the_customer_label_may_be_a_contiguous_run_of_the_result() -> None:
    case = _case()

    for name in ("Zakupy, ACME", "ACME Sp. z o.o.", "acme", "Jan Kowalski, ACME Sp. z o.o."):
        assert score_case(case, _parsed(customer=name), {})["customer"] == "hit", name
    for name in ("Acmex", "Biuro Max"):
        assert score_case(case, _parsed(customer=name), {})["customer"] == "silent_wrong", name


def test_a_multi_word_customer_label_must_be_contiguous() -> None:
    case = _case(customer={"value": "Biuro Max"})

    assert score_case(case, _parsed(customer="Biuro Max Sp. z o.o."), {})["customer"] == "hit"
    assert score_case(case, _parsed(customer="Max Biuro"), {})["customer"] == "silent_wrong"
    assert score_case(case, _parsed(customer="Biuro i Max"), {})["customer"] == "silent_wrong"


def test_a_null_customer_label_needs_a_null_result() -> None:
    case = _case(customer={"value": None, "flagged": True})

    assert score_case(case, _parsed(customer=None), {"customer": "Missing"})["customer"] == "hit"
    assert (
        score_case(case, _parsed(customer="ACME"), {"customer": "Model: x"})["customer"]
        == "flagged_miss"
    )


def test_the_product_code_ignores_case_and_surrounding_space() -> None:
    assert score_case(_case(), _parsed(product_code=" abc-200 "), {})["product_code"] == "hit"
    assert (
        score_case(_case(), _parsed(product_code="ABC 200"), {})["product_code"] == "silent_wrong"
    )


def test_price_needs_the_same_kind_and_the_same_decimal() -> None:
    discount = _case(price={"kind": "discount_percent", "value": "7.5"})

    assert (
        score_case(
            discount, _parsed(price_kind="discount_percent", price_value=Decimal("7.5")), {}
        )["price"]
        == "hit"
    )
    assert (
        score_case(
            discount, _parsed(price_kind="discount_percent", price_value=Decimal("7.50")), {}
        )["price"]
        == "hit"
    )
    assert (
        score_case(discount, _parsed(price_kind="discount_percent", price_value=Decimal("8")), {})[
            "price"
        ]
        == "silent_wrong"
    )
    assert (
        score_case(discount, _parsed(price_kind="target_price", price_value=Decimal("7.5")), {})[
            "price"
        ]
        == "silent_wrong"
    )


def test_a_kind_without_a_value_compares_the_kind_only() -> None:
    best = _case(price={"kind": "best_price"})

    assert score_case(best, _parsed(price_kind="best_price"), {})["price"] == "hit"
    assert score_case(best, _parsed(), {})["price"] == "silent_wrong"
    assert score_case(best, _parsed(), {"price": "No number"})["price"] == "flagged_miss"


def _all(outcome: FieldOutcome) -> dict[FieldName, FieldOutcome]:
    return {
        "customer": outcome,
        "product_code": outcome,
        "quantity": outcome,
        "deadline": outcome,
        "substitute_allowed": outcome,
        "price": outcome,
    }


def test_summarize_counts_each_field_over_cases_and_repeats() -> None:
    case = _case()
    mixed = _all("hit") | {"quantity": "silent_wrong", "price": "flagged_miss"}

    summary = summarize([(case, [_all("hit"), mixed]), (case, [mixed])])

    quantity = summary.per_field["quantity"]
    assert (quantity.hits, quantity.flagged_misses, quantity.silent_wrongs) == (1, 0, 2)
    assert quantity.total == 3
    price = summary.per_field["price"]
    assert (price.hits, price.flagged_misses, price.silent_wrongs) == (1, 2, 0)
    customer = summary.per_field["customer"]
    assert (customer.hits, customer.total) == (3, 3)
    assert summary.per_tag == {}


def test_summarize_counts_a_tag_only_on_its_own_field() -> None:
    price_case = _case(tags=["price_target", "deadline_supported"])
    other = _case(tags=["quantity_variant", "substitute_absent"])
    wrong_price = _all("hit") | {"price": "silent_wrong", "deadline": "flagged_miss"}
    wrong_quantity = _all("hit") | {"quantity": "silent_wrong", "price": "silent_wrong"}

    summary = summarize([(price_case, [wrong_price, _all("hit")]), (other, [wrong_quantity])])

    target = summary.per_tag["price_target"]
    assert (target.hits, target.silent_wrongs, target.total) == (1, 1, 2)
    deadline = summary.per_tag["deadline_supported"]
    assert (deadline.hits, deadline.flagged_misses, deadline.total) == (1, 1, 2)
    quantity = summary.per_tag["quantity_variant"]
    assert (quantity.silent_wrongs, quantity.total) == (1, 1)
    substitute = summary.per_tag["substitute_absent"]
    assert (substitute.hits, substitute.total) == (1, 1)
    assert "price_best" not in summary.per_tag


def test_two_tags_of_one_field_count_the_same_unit_twice() -> None:
    case = _case(tags=["deadline_supported", "weekend_reference"])
    wrong = _all("hit") | {"deadline": "silent_wrong", "price": "silent_wrong"}

    summary = summarize([(case, [wrong, _all("hit")])])

    for tag in ("deadline_supported", "weekend_reference"):
        tally = summary.per_tag[tag]
        assert (tally.hits, tally.silent_wrongs, tally.total) == (1, 1, 2)
    assert summary.per_field["deadline"].total == 2  # the field itself counts each unit once
