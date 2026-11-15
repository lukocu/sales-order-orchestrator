from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.mailbox.message import MailCandidate
from app.mailbox.store import insert_new
from tests.conftest import TEST_EMAIL_DOMAIN


def _candidate(external_id: str | None = None) -> MailCandidate:
    return MailCandidate(
        external_id=external_id or uuid4().hex * 2,
        sender_name="Test Sender",
        sender_email=f"sender-{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}",
        subject="Zapytanie z poczty",
        body="Treść.",
        received_at=datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
    )


def _stored(engine: Engine, external_ids: list[str]) -> list[Inquiry]:
    with Session(engine) as session:
        return list(
            session.exec(select(Inquiry).where(col(Inquiry.external_id).in_(external_ids))).all()
        )


def test_second_insert_of_same_candidates_adds_nothing(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    candidates = [_candidate(), _candidate()]

    assert insert_new(migrated_engine, candidates) == 2
    assert insert_new(migrated_engine, candidates) == 0

    rows = _stored(migrated_engine, [c.external_id for c in candidates])
    assert len(rows) == 2
    assert {r.source for r in rows} == {"mailbox"}


def test_duplicate_within_batch_is_stored_once(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    first = _candidate()
    duplicate = _candidate(first.external_id)

    assert insert_new(migrated_engine, [first, duplicate]) == 1

    rows = _stored(migrated_engine, [first.external_id])
    assert [r.sender_email for r in rows] == [first.sender_email]


def test_empty_batch_inserts_nothing(migrated_engine: Engine) -> None:
    assert insert_new(migrated_engine, []) == 0
