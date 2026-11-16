from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, insert, tuple_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from tests.conftest import TEST_EMAIL_DOMAIN, InquiryFactory

# (sender, subject) of the four sample inquiries seeded by migration 0003. The sender alone
# is not enough: the fake mailbox's sample messages come from the same companies.
SAMPLE_INQUIRIES = [
    ("zakupy@acme.example", "Zapytanie ofertowe: 80 szt. ABC-100"),
    ("biuro@biuromax.example", "Zamówienie ABC-200, 20 szt."),
    ("handel@hurtowniadelta.example", "500 szt. ABC-100 — prośba o rabat"),
    ("zaopatrzenie@technikaomega.example", "Pilne: 120 szt. XYZ-300"),
]


def test_seeded_inquiries_are_samples_without_external_id(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        seeds = session.exec(
            select(Inquiry).where(
                tuple_(col(Inquiry.sender_email), col(Inquiry.subject)).in_(SAMPLE_INQUIRIES)
            )
        ).all()

    assert len(seeds) == len(SAMPLE_INQUIRIES)
    assert {s.source for s in seeds} == {"sample"}
    assert {s.external_id for s in seeds} == {None}


def test_inquiry_without_source_is_sample(make_inquiry: InquiryFactory) -> None:
    inquiry = make_inquiry(received_at=datetime.now(UTC))

    assert inquiry.source == "sample"
    assert inquiry.external_id is None


def test_source_check_rejects_unknown_source(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    statement = insert(Inquiry).values(
        sender_name="Test Sender",
        sender_email=f"sender-{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}",
        subject="Test inquiry",
        body="Test inquiry body.",
        received_at=datetime.now(UTC),
        source="fax",
    )

    with (
        Session(migrated_engine) as session,
        pytest.raises(IntegrityError, match="ck_inquiries_source"),
    ):
        session.execute(statement)
        session.commit()
