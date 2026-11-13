"""The labelled evaluation set: loading, label invariants and scenario coverage. No database."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.eval.cases import DuplicateCaseId, EvalCase, ExpectedDecision, load_cases

SEED_CUSTOMER_DOMAINS = {
    "acme.example",
    "biuromax.example",
    "hurtowniadelta.example",
    "technikaomega.example",
}


def _case(**overrides: Any) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": "acme-test",
        "sender_name": "Marek Nowak",
        "sender_email": "zakupy@acme.example",
        "subject": "Zapytanie",
        "body": "Dzień dobry",
        "received_at": "2026-11-02T08:15:00Z",
        "fields": {
            "customer": "ACME",
            "product_code": "ABC-200",
            "quantity": 10,
            "deadline": None,
            "deadline_text": None,
            "substitute_allowed": None,
            "price_kind": "none",
            "price_value": None,
            "price_text": None,
        },
        "expected": {"checks_outcome": "standard", "option_kind": None, "policy_outcome": None},
        "rationale": "Na stanie.",
    }
    return case | overrides


def _write(tmp_path: Path, cases: list[dict[str, Any]]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


def test_builtin_set_loads_with_unique_ids() -> None:
    cases = load_cases()
    ids = [case.id for case in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) >= 12


def test_builtin_set_starts_with_the_four_seed_scenarios() -> None:
    first = [case.sender_email.rpartition("@")[2] for case in load_cases()[:4]]
    assert first == [
        "acme.example",
        "biuromax.example",
        "hurtowniadelta.example",
        "technikaomega.example",
    ]


def test_builtin_set_covers_the_scenarios() -> None:
    cases = load_cases()
    exceptions = [c for c in cases if c.expected.checks_outcome == "exception"]
    assert len(exceptions) >= 10
    assert {c.expected.policy_outcome for c in exceptions} == {
        "no_approval_needed",
        "requires_supervisor",
    }
    kinds = {c.expected.option_kind for c in exceptions}
    assert len(kinds) >= 3
    assert kinds == {"partial_delivery", "substitute", "other_source", "combined"}
    assert any(c.expected.checks_outcome == "standard" for c in cases)
    assert any(c.expected.checks_outcome == "needs_input" for c in cases)
    # Refused substitutes and an exception without a deadline are both in the set.
    assert any(c.fields.substitute_allowed is False for c in exceptions)
    assert any(c.fields.deadline is None for c in exceptions)


def test_builtin_set_uses_seed_customer_domains_and_explains_every_label() -> None:
    for case in load_cases():
        assert case.sender_email.rpartition("@")[2] in SEED_CUSTOMER_DOMAINS, case.id
        assert case.rationale.strip(), case.id
        assert case.received_at.tzinfo is not None, case.id


def test_builtin_labels_keep_the_invariant() -> None:
    for case in load_cases():
        exception = case.expected.checks_outcome == "exception"
        assert (case.expected.option_kind is not None) is exception, case.id
        assert (case.expected.policy_outcome is not None) is exception, case.id


def test_loads_a_valid_file(tmp_path: Path) -> None:
    (case,) = load_cases(_write(tmp_path, [_case()]))
    assert isinstance(case, EvalCase)
    assert case.id == "acme-test"


def test_rejects_an_extra_field(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_cases(_write(tmp_path, [_case(note="extra")]))


def test_rejects_an_extra_field_in_the_golden_fields(tmp_path: Path) -> None:
    fields = _case()["fields"] | {"unit": "szt."}
    with pytest.raises(ValidationError):
        load_cases(_write(tmp_path, [_case(fields=fields)]))


def test_rejects_a_duplicate_id(tmp_path: Path) -> None:
    with pytest.raises(DuplicateCaseId):
        load_cases(_write(tmp_path, [_case(), _case()]))


def test_rejects_an_id_that_is_not_kebab_case(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_cases(_write(tmp_path, [_case(id="Acme_Test")]))


def test_rejects_a_received_at_without_a_timezone(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_cases(_write(tmp_path, [_case(received_at="2026-11-02T08:15:00")]))


@pytest.mark.parametrize(
    "expected",
    [
        {"checks_outcome": "exception", "option_kind": None, "policy_outcome": None},
        {"checks_outcome": "exception", "option_kind": "substitute", "policy_outcome": None},
        {
            "checks_outcome": "exception",
            "option_kind": None,
            "policy_outcome": "requires_supervisor",
        },
        {"checks_outcome": "standard", "option_kind": "substitute", "policy_outcome": None},
        {
            "checks_outcome": "needs_input",
            "option_kind": None,
            "policy_outcome": "no_approval_needed",
        },
    ],
)
def test_rejects_an_inconsistent_label(tmp_path: Path, expected: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        load_cases(_write(tmp_path, [_case(expected=expected)]))


def test_rejects_an_unknown_option_kind() -> None:
    with pytest.raises(ValidationError):
        ExpectedDecision.model_validate(
            {
                "checks_outcome": "exception",
                "option_kind": "backorder",
                "policy_outcome": "requires_supervisor",
            }
        )
