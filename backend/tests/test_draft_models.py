from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from app.draft.models import InquiryDraft, InquiryDraftDecision
from app.draft.schema import DecisionSnapshot, DraftOffer, DraftResult, DraftText
from app.inquiries.models import Inquiry
from app.policy.schema import PolicyResult
from tests.conftest import InquiryFactory, UserFactory


def _assert_rejected(engine: Engine, row: SQLModel, constraint: str) -> None:
    with Session(engine) as session, pytest.raises(IntegrityError, match=constraint):
        session.add(row)
        session.commit()


def _add(engine: Engine, row: SQLModel) -> None:
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)


def _offer() -> DraftOffer:
    return DraftOffer.model_validate(
        {
            "option_id": "stock",
            "kind": "partial_delivery",
            "lines": [
                {
                    "product_code": "ABC-100",
                    "product_name": "Czujnik ciśnienia ABC-100",
                    "source": "stock",
                    "quantity": 50,
                    "available_on": "2026-11-02",
                    "list_price": "120.00",
                    "unit_price": "114.00",
                    "unit_cost": "84.00",
                    "value": "5700.00",
                    "cost": "4200.00",
                }
            ],
            "covered_quantity": 50,
            "requested_quantity": 80,
            "fulfilled_on": "2026-11-02",
            "meets_deadline": True,
            "value": "5700.00",
            "cost": "4200.00",
            "margin_percent": "26.32",
            "edited": False,
        }
    )


def _result(policy: PolicyResult | None = None) -> DraftResult:
    return DraftResult(
        drafter="fake",
        offer=_offer(),
        text=DraftText(intro="Dziękujemy za zapytanie.", closing="Pozdrawiamy.", source="model"),
        policy=policy,
    )


def _draft(inquiry: Inquiry, **overrides: object) -> InquiryDraft:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "recommended_at": now,
        "status": "draft",
        "result": _result().model_dump(mode="json"),
        "drafted_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return InquiryDraft.model_validate(values)


def _decision(inquiry: Inquiry, **overrides: object) -> InquiryDraftDecision:
    snapshot = DecisionSnapshot(offer=_offer(), policy_outcome="no_approval_needed")
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "recommended_at": datetime.now(UTC),
        "action": "approve",
        "status_after": "ready_to_send",
        "decided_at": datetime.now(UTC),
        "snapshot": snapshot.model_dump(mode="json"),
    }
    values.update(overrides)
    return InquiryDraftDecision.model_validate(values)


def _decisions_of(engine: Engine, inquiry: Inquiry) -> list[InquiryDraftDecision]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(InquiryDraftDecision)
                .where(col(InquiryDraftDecision.inquiry_id) == inquiry.id)
                .order_by(col(InquiryDraftDecision.id))
            ).all()
        )


# --- Schema ---------------------------------------------------------------------------


def test_draft_result_round_trips_through_json_with_decimal_strings() -> None:
    policy = PolicyResult.model_validate(
        {
            "option_id": "stock",
            "rules": [
                {
                    "code": "discount",
                    "verdict": "fail",
                    "actual": "16.67",
                    "threshold": "15.00",
                    "unit": "percent",
                    "reason": "Offered discount above the maximum",
                }
            ],
            "outcome": "requires_supervisor",
            "thresholds_are_examples": True,
        }
    )
    result = _result(policy)

    stored = result.model_dump(mode="json")

    assert stored["offer"]["value"] == "5700.00"
    assert stored["offer"]["lines"][0]["available_on"] == "2026-11-02"
    assert stored["text"]["error"] is None
    assert DraftResult.model_validate(stored) == result
    assert DraftResult.model_validate(stored).offer.lines[0].list_price == Decimal("120.00")
    assert DraftResult.model_validate(stored).offer.fulfilled_on == date(2026, 11, 2)


def test_decision_snapshot_round_trips() -> None:
    snapshot = DecisionSnapshot(
        offer=_offer(), policy_outcome="requires_supervisor", failing_rules=["margin", "discount"]
    )

    assert DecisionSnapshot.model_validate(snapshot.model_dump(mode="json")) == snapshot


def test_decision_snapshot_without_not_evaluated_rules_reads() -> None:
    # Stored before `not_evaluated_rules` existed.
    stored = {
        "offer": _offer().model_dump(mode="json"),
        "policy_outcome": "requires_supervisor",
        "failing_rules": ["discount"],
    }

    snapshot = DecisionSnapshot.model_validate(stored)

    assert (snapshot.failing_rules, snapshot.not_evaluated_rules) == (["discount"], [])


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (DraftText, {"intro": "a", "closing": "b", "source": "model", "extra": 1}),
        (DraftText, {"intro": "a", "closing": "b", "source": "llm"}),
        (DraftOffer, {**_offer().model_dump(mode="json"), "band": "HIGH"}),
        (DraftResult, {**_result().model_dump(mode="json"), "status": "draft"}),
        (
            DecisionSnapshot,
            {"offer": _offer().model_dump(mode="json"), "policy_outcome": "approved"},
        ),
        (
            DecisionSnapshot,
            {
                "offer": _offer().model_dump(mode="json"),
                "policy_outcome": None,
                "failing_rules": ["deadline"],
            },
        ),
    ],
)
def test_schema_rejects_unknown_fields_and_values(model: type[Any], data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_offer_line_rejects_unknown_fields() -> None:
    data = _offer().model_dump(mode="json")
    data["lines"][0]["discount"] = "5.00"

    with pytest.raises(ValidationError):
        DraftOffer.model_validate(data)


# --- Constraints ----------------------------------------------------------------------


def test_draft_status_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    row = _draft(inquiry)
    row.status = "sent"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_drafts_status")


def test_one_draft_per_inquiry(migrated_engine: Engine, make_inquiry: InquiryFactory) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    _add(migrated_engine, _draft(inquiry))

    _assert_rejected(migrated_engine, _draft(inquiry), "uq_inquiry_drafts_inquiry_id")


def test_decision_action_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    row = _decision(inquiry)
    row.action = "send"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_draft_decisions_action")


@pytest.mark.parametrize(
    ("action", "status_after"),
    [("supervisor_approve", "ready_to_send"), ("supervisor_reject", "rejected")],
)
def test_supervisor_actions_are_accepted(
    migrated_engine: Engine, make_inquiry: InquiryFactory, action: str, status_after: str
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    _add(migrated_engine, _decision(inquiry, action=action, status_after=status_after))

    assert [d.action for d in _decisions_of(migrated_engine, inquiry)] == [action]


def test_decision_status_after_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    row = _decision(inquiry)
    row.status_after = "sent"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_draft_decisions_status_after")


@pytest.mark.parametrize("status", ["draft", "ready_to_send", "awaiting_supervisor", "rejected"])
def test_every_status_is_accepted(
    migrated_engine: Engine, make_inquiry: InquiryFactory, status: str
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    _add(migrated_engine, _draft(inquiry, status=status))
    _add(migrated_engine, _decision(inquiry, status_after=status, action="edit", reason=None))

    assert [d.status_after for d in _decisions_of(migrated_engine, inquiry)] == [status]


def test_decisions_are_a_history_and_survive_the_draft(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    draft = _draft(inquiry)
    _add(migrated_engine, draft)
    _add(migrated_engine, _decision(inquiry, action="edit", status_after="draft", reason="Cena"))
    _add(migrated_engine, _decision(inquiry, action="reject", status_after="rejected", reason="X"))

    with Session(migrated_engine) as session:
        session.delete(session.get_one(InquiryDraft, draft.id))
        session.commit()

    assert [(d.action, d.reason) for d in _decisions_of(migrated_engine, inquiry)] == [
        ("edit", "Cena"),
        ("reject", "X"),
    ]


def test_deleting_inquiry_deletes_draft_and_decisions(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    draft = _draft(inquiry)
    _add(migrated_engine, draft)
    _add(migrated_engine, _decision(inquiry))

    with Session(migrated_engine) as session:
        session.delete(session.get_one(Inquiry, inquiry.id))
        session.commit()

    with Session(migrated_engine) as session:
        assert session.get(InquiryDraft, draft.id) is None
    assert _decisions_of(migrated_engine, inquiry) == []


def test_deleting_user_keeps_decision_without_author(
    migrated_engine: Engine, make_inquiry: InquiryFactory, make_user: UserFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    user = make_user()
    decision = _decision(inquiry, decided_by=user.id)
    _add(migrated_engine, decision)
    assert decision.decided_by == user.id

    with Session(migrated_engine) as session:
        session.delete(session.get_one(type(user), user.id))
        session.commit()

    assert [d.decided_by for d in _decisions_of(migrated_engine, inquiry)] == [None]
