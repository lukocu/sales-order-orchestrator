from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.auth.deps import AuthUser
from app.auth.models import User
from app.draft.drafter import FakeDrafter
from app.inquiries.models import Inquiry
from app.orchestration.planning import RuleBasedPlanner
from app.parsing.fake import RuleBasedExtractor
from app.parsing.models import InquiryAnalysis
from app.parsing.schema import ParsedFields
from app.parsing.service import analyze_inquiry, changed_fields, reference_date_of
from app.recommendation.recommender import FakeRecommender
from app.tracing.models import TraceRun
from tests.conftest import InquiryFactory, UserFactory


def _fields(**overrides: object) -> ParsedFields:
    values: dict[str, object] = {
        "customer": "ACME Sp. z o.o.",
        "product_code": "ABC-100",
        "quantity": 80,
        "deadline": date(2026, 11, 6),
        "deadline_text": "do piątku",
        "substitute_allowed": True,
        "price_kind": "discount_percent",
        "price_value": "12.5",
        "price_text": "rabat 12,5%",
    }
    values.update(overrides)
    return ParsedFields.model_validate(values)


def test_json_round_trip_keeps_decimal_and_date() -> None:
    fields = _fields()

    stored = fields.model_dump(mode="json")

    assert stored["price_value"] == "12.5"
    assert stored["deadline"] == "2026-11-06"
    assert ParsedFields.model_validate(stored) == fields


def test_changed_fields_groups_attributes() -> None:
    before = _fields()
    after = _fields(deadline_text="do soboty", price_value="15", quantity=80)

    assert changed_fields(before, after) == ["deadline", "price"]
    assert changed_fields(before, _fields(price_value="12.50")) == []


def test_reference_date_is_warsaw_day() -> None:
    assert reference_date_of(datetime(2026, 11, 1, 23, 30, tzinfo=UTC)) == date(2026, 11, 2)
    assert reference_date_of(datetime(2026, 11, 2, 22, 59, tzinfo=UTC)) == date(2026, 11, 2)


def _analyze(engine: Engine, inquiry: Inquiry, user: User) -> None:
    assert inquiry.id is not None
    analyze_inquiry(
        engine,
        RuleBasedExtractor(),
        inquiry.id,
        AuthUser.from_user(user),
        RuleBasedPlanner(),
        FakeRecommender(),
        FakeDrafter(),
    )


def test_deleting_inquiry_deletes_analysis(
    migrated_engine: Engine, make_inquiry: InquiryFactory, make_user: UserFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    _analyze(migrated_engine, inquiry, make_user())

    with Session(migrated_engine) as session:
        session.delete(session.get_one(Inquiry, inquiry.id))
        # The teardown finds runs through the test inquiries; this one is gone.
        session.exec(
            delete(TraceRun).where(
                col(TraceRun.subject_type) == "inquiry",
                col(TraceRun.subject_id) == str(inquiry.id),
            )
        )
        session.commit()
        remaining = session.exec(
            select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry.id)
        ).all()

    assert remaining == []


def test_deleting_user_keeps_analysis(
    migrated_engine: Engine, make_inquiry: InquiryFactory, make_user: UserFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    user = make_user()
    _analyze(migrated_engine, inquiry, user)

    with Session(migrated_engine) as session:
        session.delete(session.get_one(User, user.id))
        session.commit()
        analysis = session.exec(
            select(InquiryAnalysis).where(col(InquiryAnalysis.inquiry_id) == inquiry.id)
        ).one()

    assert analysis.analyzed_by is None


def test_extractor_check_rejects_unknown_name(
    migrated_engine: Engine, make_inquiry: InquiryFactory
) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))
    assert inquiry.id is not None
    stored = _fields().model_dump(mode="json")
    analysis = InquiryAnalysis(
        inquiry_id=inquiry.id,
        extractor="gemini",  # type: ignore[arg-type]
        reference_date=date(2026, 11, 2),
        fields_from_model=stored,
        fields=stored,
        uncertain={},
        analyzed_at=datetime.now(UTC),
    )

    with (
        Session(migrated_engine) as session,
        pytest.raises(IntegrityError, match="ck_inquiry_analyses_extractor"),
    ):
        session.add(analysis)
        session.commit()
