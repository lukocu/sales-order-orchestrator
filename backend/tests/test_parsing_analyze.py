from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.parsing.analyze import build_parsed
from app.parsing.schema import MAX_TEXT_LENGTH, ModelExtraction, ParsedFields

MONDAY = date(2026, 11, 2)


def _extraction(**overrides: object) -> ModelExtraction:
    fields: dict[str, object] = {
        "customer": "ACME Sp. z o.o.",
        "product_code": "ABC-100",
        "quantity": 80,
        "deadline_text": "do piątku",
        "deadline_date": "2026-11-06",
        "substitute_allowed": True,
        "price_kind": "best_price",
        "price_value": None,
        "price_text": "najlepszą cenę",
        "uncertain": [],
    }
    fields.update(overrides)
    return ModelExtraction.model_validate(fields)


def test_clean_extraction_has_no_uncertain_fields() -> None:
    fields, uncertain = build_parsed(_extraction(), MONDAY)

    assert uncertain == {}
    assert fields == ParsedFields(
        customer="ACME Sp. z o.o.",
        product_code="ABC-100",
        quantity=80,
        deadline=date(2026, 11, 6),
        deadline_text="do piątku",
        substitute_allowed=True,
        price_kind="best_price",
        price_value=None,
        price_text="najlepszą cenę",
    )


@pytest.mark.parametrize("field", ["customer", "product_code", "quantity"])
def test_missing_core_field_is_flagged(field: str) -> None:
    fields, uncertain = build_parsed(_extraction(**{field: None}), MONDAY)

    assert getattr(fields, field) is None
    assert uncertain == {field: "Missing"}


def test_blank_text_counts_as_missing() -> None:
    fields, uncertain = build_parsed(_extraction(customer="   "), MONDAY)

    assert fields.customer is None
    assert uncertain == {"customer": "Missing"}


@pytest.mark.parametrize("quantity", [0, -5])
def test_invalid_quantity_is_emptied_and_flagged(quantity: int) -> None:
    fields, uncertain = build_parsed(_extraction(quantity=quantity), MONDAY)

    assert fields.quantity is None
    assert uncertain == {"quantity": f"Invalid quantity {quantity}"}


def test_too_long_text_is_truncated_and_flagged() -> None:
    fields, uncertain = build_parsed(_extraction(customer="A" * 300), MONDAY)

    assert fields.customer == "A" * MAX_TEXT_LENGTH
    assert "truncated" in uncertain["customer"]


def test_deadline_disagreement_names_both_dates() -> None:
    fields, uncertain = build_parsed(_extraction(deadline_date="2026-11-13"), MONDAY)

    assert fields.deadline == date(2026, 11, 6)  # the code wins
    assert uncertain == {"deadline": "Rules read 2026-11-06, model read 2026-11-13"}


def test_ambiguous_deadline_is_flagged() -> None:
    friday = date(2026, 11, 6)

    fields, uncertain = build_parsed(_extraction(), friday)

    assert fields.deadline == friday
    assert uncertain == {"deadline": "Ambiguous phrase"}


def test_deadline_resolved_by_model_only() -> None:
    fields, uncertain = build_parsed(
        _extraction(deadline_text="na święta", deadline_date="2026-12-24"), MONDAY
    )

    assert fields.deadline == date(2026, 12, 24)
    assert fields.deadline_text == "na święta"
    assert uncertain == {"deadline": "Resolved by model only"}


@pytest.mark.parametrize("model_date", [None, "not a date"])
def test_unresolvable_deadline_is_flagged(model_date: str | None) -> None:
    fields, uncertain = build_parsed(
        _extraction(deadline_text="na święta", deadline_date=model_date), MONDAY
    )

    assert fields.deadline is None
    assert uncertain == {"deadline": "Could not resolve the deadline phrase"}


def test_no_deadline_is_not_flagged() -> None:
    fields, uncertain = build_parsed(_extraction(deadline_text=None, deadline_date=None), MONDAY)

    assert fields.deadline is None
    assert uncertain == {}


def test_model_date_without_phrase_is_kept_and_flagged() -> None:
    fields, uncertain = build_parsed(
        _extraction(deadline_text=None, deadline_date="2026-11-20"), MONDAY
    )

    assert fields.deadline == date(2026, 11, 20)
    assert uncertain == {"deadline": "Date given without the deadline phrase"}


def test_substitute_not_stated_is_flagged() -> None:
    fields, uncertain = build_parsed(_extraction(substitute_allowed=None), MONDAY)

    assert fields.substitute_allowed is None
    assert uncertain == {"substitute_allowed": "Not stated"}


def test_valid_discount_is_kept() -> None:
    fields, uncertain = build_parsed(
        _extraction(price_kind="discount_percent", price_value=25.0, price_text="rabat 25%"),
        MONDAY,
    )

    assert (fields.price_kind, fields.price_value) == ("discount_percent", Decimal("25.0"))
    assert uncertain == {}


def test_target_price_is_kept() -> None:
    fields, uncertain = build_parsed(
        _extraction(price_kind="target_price", price_value=12.5), MONDAY
    )

    assert (fields.price_kind, fields.price_value) == ("target_price", Decimal("12.5"))
    assert uncertain == {}


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("discount_percent", None),
        ("discount_percent", 0.0),
        ("discount_percent", 150.0),
        ("discount_percent", float("nan")),
        ("target_price", -3.0),
        ("target_price", None),
    ],
)
def test_price_kind_without_valid_number_is_reset_and_flagged(
    kind: str, value: float | None
) -> None:
    fields, uncertain = build_parsed(
        _extraction(price_kind=kind, price_value=value, price_text="rabat"), MONDAY
    )

    assert (fields.price_kind, fields.price_value) == ("none", None)
    assert fields.price_text == "rabat"
    assert set(uncertain) == {"price"}


def test_value_for_kind_without_number_is_dropped() -> None:
    fields, uncertain = build_parsed(_extraction(price_value=10.0), MONDAY)

    assert (fields.price_kind, fields.price_value) == ("best_price", None)
    assert uncertain == {}


def test_model_flags_are_joined_per_field_after_code_flags() -> None:
    extraction = _extraction(
        substitute_allowed=None,
        uncertain=[
            {"field": "substitute_allowed", "reason": "Only implied"},
            {"field": "customer", "reason": " Signature only "},
            {"field": "customer", "reason": ""},
        ],
    )

    _, uncertain = build_parsed(extraction, MONDAY)

    assert uncertain == {
        "substitute_allowed": "Not stated; Model: Only implied",
        "customer": "Model: Signature only; Model marked as uncertain",
    }


# --- ParsedFields validation ----------------------------------------------------------


def _parsed(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "customer": None,
        "product_code": None,
        "quantity": None,
        "deadline": None,
        "deadline_text": None,
        "substitute_allowed": None,
        "price_kind": "none",
        "price_value": None,
        "price_text": None,
    }
    fields.update(overrides)
    return fields


@pytest.mark.parametrize(
    "overrides",
    [
        {"price_kind": "discount_percent", "price_value": "150"},
        {"price_kind": "discount_percent", "price_value": "0"},
        {"price_kind": "discount_percent", "price_value": None},
        {"price_kind": "target_price", "price_value": "-1"},
        {"price_kind": "best_price", "price_value": "10"},
        {"price_kind": "none", "price_value": "10"},
        {"quantity": 0},
        {"customer": "A" * (MAX_TEXT_LENGTH + 1)},
        {"unknown": 1},
    ],
)
def test_parsed_fields_reject_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ParsedFields.model_validate(_parsed(**overrides))


def test_parsed_fields_round_trip_through_json() -> None:
    fields = ParsedFields.model_validate(
        _parsed(price_kind="discount_percent", price_value="25", deadline="2026-11-06")
    )

    dumped = fields.model_dump(mode="json")

    assert dumped["price_value"] == "25"
    assert dumped["deadline"] == "2026-11-06"
    assert ParsedFields.model_validate(dumped) == fields
