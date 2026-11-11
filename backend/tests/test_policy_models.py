from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from app.inquiries.models import Inquiry
from app.policy.models import InquiryPolicyVerdict, PolicyRule
from app.recommendation.models import InquiryRecommendation
from tests.conftest import InquiryFactory

# The example thresholds (migrations/versions/0011_policy_verdicts.py).
SEED_THRESHOLDS = {
    "margin_min_percent": (Decimal("20.00"), "percent"),
    "discount_max_percent": (Decimal("15.00"), "percent"),
    "order_value_max": (Decimal("30000.00"), "PLN"),
}


def _assert_rejected(engine: Engine, row: SQLModel, constraint: str) -> None:
    with Session(engine) as session, pytest.raises(IntegrityError, match=constraint):
        session.add(row)
        session.commit()


def _recommendation(engine: Engine, inquiry: Inquiry) -> InquiryRecommendation:
    assert inquiry.id is not None
    now = datetime.now(UTC)
    row = InquiryRecommendation(
        inquiry_id=inquiry.id,
        analysis_version=now,
        checks_checked_at=now,
        orchestrated_at=now,
        status="completed",
        result={"options": []},
        recommended_at=now,
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _verdict(
    inquiry: Inquiry, recommendation: InquiryRecommendation, **overrides: object
) -> InquiryPolicyVerdict:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "inquiry_id": inquiry.id,
        "recommendation_id": recommendation.id,
        "recommended_at": recommendation.recommended_at,
        "outcome": "no_approval_needed",
        "result": {"rules": []},
        "evaluated_at": now,
    }
    values.update(overrides)
    return InquiryPolicyVerdict.model_validate(values)


def _verdicts_of(engine: Engine, inquiry: Inquiry) -> list[InquiryPolicyVerdict]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(InquiryPolicyVerdict).where(
                    col(InquiryPolicyVerdict.inquiry_id) == inquiry.id
                )
            ).all()
        )


# --- Seed -----------------------------------------------------------------------------


def test_seed_example_thresholds(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        rules = session.exec(select(PolicyRule)).all()

    assert {r.code: (r.threshold, r.unit) for r in rules} == SEED_THRESHOLDS
    assert all(r.is_example for r in rules)
    assert all(r.description for r in rules)


# --- Constraints ----------------------------------------------------------------------


def test_policy_rule_code_rejects_unknown_value(migrated_engine: Engine) -> None:
    row = PolicyRule(
        code="credit_max",  # type: ignore[arg-type]
        threshold=Decimal("1.00"),
        unit="PLN",
        description="Test",
    )

    _assert_rejected(migrated_engine, row, "ck_policy_rules_code")


def test_policy_rule_threshold_must_not_be_negative(migrated_engine: Engine) -> None:
    # The CHECK fires before the primary key collides with the seeded row.
    row = PolicyRule(
        code="order_value_max", threshold=Decimal("-1.00"), unit="PLN", description="Test"
    )

    _assert_rejected(migrated_engine, row, "ck_policy_rules_threshold")


def test_policy_rule_unit_rejects_unknown_value(migrated_engine: Engine) -> None:
    row = PolicyRule(
        code="order_value_max",
        threshold=Decimal("1.00"),
        unit="EUR",  # type: ignore[arg-type]
        description="Test",
    )

    _assert_rejected(migrated_engine, row, "ck_policy_rules_unit")


def test_verdict_outcome_rejects_unknown_value(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    row = _verdict(inquiry, _recommendation(migrated_engine, inquiry))
    row.outcome = "approved"  # type: ignore[assignment]

    _assert_rejected(migrated_engine, row, "ck_inquiry_policy_verdicts_outcome")


def test_one_verdict_per_inquiry(migrated_engine: Engine, make_inquiry: InquiryFactory) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    recommendation = _recommendation(migrated_engine, inquiry)
    with Session(migrated_engine) as session:
        session.add(_verdict(inquiry, recommendation))
        session.commit()

    _assert_rejected(
        migrated_engine,
        _verdict(inquiry, recommendation),
        "uq_inquiry_policy_verdicts_inquiry_id",
    )


def test_deleting_recommendation_deletes_verdict(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    recommendation = _recommendation(migrated_engine, inquiry)
    with Session(migrated_engine) as session:
        session.add(_verdict(inquiry, recommendation, outcome="requires_supervisor"))
        session.commit()
    stored = _verdicts_of(migrated_engine, inquiry)
    assert [(v.outcome, v.result) for v in stored] == [("requires_supervisor", {"rules": []})]

    with Session(migrated_engine) as session:
        session.delete(session.get_one(InquiryRecommendation, recommendation.id))
        session.commit()

    assert _verdicts_of(migrated_engine, inquiry) == []
