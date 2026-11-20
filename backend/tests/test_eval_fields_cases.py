"""The parser field eval case schema and loader: label invariants. No database."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.eval.fields import cases as cases_module
from app.eval.fields.cases import DuplicateFieldCaseId, FieldCase, load_cases


def _expected(**overrides: Any) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "customer": {"value": "ACME"},
        "product_code": {"value": "ABC-200"},
        "quantity": {"value": 80},
        "deadline": {"value": "2026-11-06", "weekday": "friday"},
        "substitute_allowed": {"value": None, "flagged": True},
        "price": {"kind": "none"},
    }
    return expected | overrides


def _case(**overrides: Any) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": "do-piatku",
        "subject": "Zapytanie",
        "body": "Potrzebujemy 80 szt. ABC-200 do piatku. Pozdrawiam, ACME",
        "received_at": "2026-11-02T08:15:00Z",
        "expected": _expected(),
        "rationale": "Poniedzialek 2026-11-02, najblizszy piatek to 2026-11-06.",
        "tags": ["deadline_supported"],
    }
    return case | overrides


def _write(tmp_path: Path, cases: list[dict[str, Any]]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


def test_a_valid_case_loads(tmp_path: Path) -> None:
    (case,) = load_cases(_write(tmp_path, [_case()]))

    assert case.id == "do-piatku"
    assert case.expected.deadline.weekday == "friday"
    assert case.expected.price.kind == "none"
    assert case.tags == ["deadline_supported"]


def test_a_missing_default_file_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cases_module, "FIELD_CASES_PATH", tmp_path / "missing.json")

    with pytest.raises(FileNotFoundError):
        load_cases(tmp_path / "missing.json")


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(DuplicateFieldCaseId, match="do-piatku"):
        load_cases(_write(tmp_path, [_case(), _case()]))


@pytest.mark.parametrize("bad_id", ["Do-Piatku", "do_piatku", "do piatku", "-do", "do-", ""])
def test_ids_must_be_kebab_case(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="kebab-case"):
        FieldCase.model_validate(_case(id=bad_id))


def test_an_empty_rationale_is_rejected() -> None:
    with pytest.raises(ValidationError, match="rationale"):
        FieldCase.model_validate(_case(rationale="   "))


def test_repeated_tags_are_rejected() -> None:
    with pytest.raises(ValidationError, match="tags"):
        FieldCase.model_validate(_case(tags=["deadline_supported", "deadline_supported"]))


def test_an_unknown_tag_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldCase.model_validate(_case(tags=["deadline_magic"]))


def test_a_weekday_that_disagrees_with_the_date_is_rejected() -> None:
    expected = _expected(deadline={"value": "2026-11-06", "weekday": "thursday"})

    with pytest.raises(ValidationError, match="is not a thursday"):
        FieldCase.model_validate(_case(expected=expected))


def test_a_weekday_without_a_date_is_rejected() -> None:
    expected = _expected(deadline={"value": None, "weekday": "friday"})

    with pytest.raises(ValidationError, match="weekday needs"):
        FieldCase.model_validate(_case(expected=expected))


def test_a_deadline_before_the_reference_day_is_rejected() -> None:
    expected = _expected(deadline={"value": "2026-11-01"})

    with pytest.raises(ValidationError, match="before the reference day"):
        FieldCase.model_validate(_case(expected=expected))


def test_the_reference_day_is_the_warsaw_day() -> None:
    # 23:30 UTC on 11-02 is 00:30 on 11-03 in Warsaw (UTC+1): 11-02 is already in the past.
    late = _case(
        received_at="2026-11-02T23:30:00Z",
        expected=_expected(deadline={"value": "2026-11-02"}),
    )
    with pytest.raises(ValidationError, match="before the reference day 2026-11-03"):
        FieldCase.model_validate(late)

    same_day = _case(
        received_at="2026-11-02T23:30:00Z",
        expected=_expected(deadline={"value": "2026-11-03"}),
    )
    assert FieldCase.model_validate(same_day).expected.deadline.value.isoformat() == "2026-11-03"  # type: ignore[union-attr]


def test_a_deadline_on_the_reference_day_is_allowed() -> None:
    FieldCase.model_validate(_case(expected=_expected(deadline={"value": "2026-11-02"})))


def test_an_absent_deadline_needs_no_flag() -> None:
    case = FieldCase.model_validate(_case(expected=_expected(deadline={"value": None})))

    assert case.expected.deadline.value is None
    assert case.expected.deadline.flagged is False


@pytest.mark.parametrize("field", ["customer", "product_code", "quantity", "substitute_allowed"])
def test_a_null_value_must_be_flagged(field: str) -> None:
    with pytest.raises(ValidationError, match="must be flagged"):
        FieldCase.model_validate(_case(expected=_expected(**{field: {"value": None}})))


def test_a_flagged_null_value_is_allowed() -> None:
    expected = _expected(customer={"value": None, "flagged": True})

    assert FieldCase.model_validate(_case(expected=expected)).expected.customer.flagged


def test_a_quantity_below_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldCase.model_validate(_case(expected=_expected(quantity={"value": 0})))


@pytest.mark.parametrize(
    "price",
    [
        {"kind": "target_price"},
        {"kind": "target_price", "value": "0"},
        {"kind": "target_price", "value": "-3"},
        {"kind": "discount_percent", "value": "0"},
        {"kind": "discount_percent", "value": "100.5"},
        {"kind": "discount_percent"},
        {"kind": "best_price", "value": "5"},
        {"kind": "none", "value": "5"},
    ],
)
def test_invalid_price_labels_are_rejected(price: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        FieldCase.model_validate(_case(expected=_expected(price=price)))


@pytest.mark.parametrize(
    "price",
    [
        {"kind": "target_price", "value": "12.50"},
        {"kind": "discount_percent", "value": "100"},
        {"kind": "discount_percent", "value": "7.5"},
        {"kind": "best_price"},
        {"kind": "none"},
    ],
)
def test_valid_price_labels_are_accepted(price: dict[str, Any]) -> None:
    FieldCase.model_validate(_case(expected=_expected(price=price)))


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldCase.model_validate(_case(extra="x"))


def test_the_loader_never_uses_the_deadline_resolver() -> None:
    source = Path(cases_module.__file__).read_text(encoding="utf-8")

    assert "resolve_deadline" not in source
    assert "app.parsing.deadline" not in source
    assert not hasattr(cases_module, "resolve_deadline")
