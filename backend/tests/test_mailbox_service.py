import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlmodel import Session, col, select

from app.inquiries.models import Inquiry
from app.mailbox.client import FakeMailbox, MailboxUnavailable
from app.mailbox.service import (
    FETCH_LIMIT,
    MAILBOX_LOCK_KEY,
    FetchResult,
    MailboxBusy,
    fetch_mailbox,
)
from tests.conftest import TEST_EMAIL_DOMAIN

NOW = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
TEST_SUBJECT = "Zapytanie testowe ABC-100"


def make_mail(*, sender: str | None = None, subject: str = TEST_SUBJECT) -> bytes:
    """A unique message (fresh Message-ID) from this process's test domain, so the test
    cleanup deletes the inquiry it becomes."""
    msg = EmailMessage()
    if sender is None:
        sender = f"Klient Testowy <klient-{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}>"
    if sender:
        msg["From"] = sender
    msg["To"] = "sprzedaz@firma.example"
    msg["Subject"] = subject
    msg["Date"] = "Sat, 14 Nov 2026 09:00:00 +0100"
    msg["Message-ID"] = f"<{uuid4().hex}@{TEST_EMAIL_DOMAIN}>"
    msg.set_content("Dzień dobry,\n\nprosimy o ofertę na 10 szt. ABC-100.\n\nPozdrawiam,\nACME")
    return msg.as_bytes()


class SpyMailbox:
    """Fake mailbox that records whether it was read."""

    name = "fake"

    def __init__(self, messages: Sequence[bytes] = ()) -> None:
        self._fake = FakeMailbox(messages)
        self.reads = 0

    def latest(self, limit: int) -> list[bytes]:
        self.reads += 1
        return self._fake.latest(limit)


class BrokenMailbox:
    name = "imap"

    def latest(self, limit: int) -> list[bytes]:
        raise MailboxUnavailable("Mailbox unavailable")


def _stored_sources(engine: Engine) -> list[str]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(Inquiry.source).where(
                    col(Inquiry.sender_email).endswith(f"@{TEST_EMAIL_DOMAIN}")
                )
            ).all()
        )


def test_first_fetch_creates_and_second_finds_duplicates(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    mailbox = FakeMailbox([make_mail(), make_mail()])

    first = fetch_mailbox(migrated_engine, mailbox, now=NOW)
    second = fetch_mailbox(migrated_engine, mailbox, now=NOW)

    assert first == FetchResult(fetched=2, created=2, duplicates=0, skipped=0)
    assert second == FetchResult(fetched=2, created=0, duplicates=2, skipped=0)
    assert _stored_sources(migrated_engine) == ["mailbox", "mailbox"]


def test_messages_without_sender_are_skipped(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    mailbox = FakeMailbox([make_mail(), make_mail(sender="")])

    result = fetch_mailbox(migrated_engine, mailbox, now=NOW)

    assert result == FetchResult(fetched=2, created=1, duplicates=0, skipped=1)


def test_only_the_newest_messages_are_read(migrated_engine: Engine, delete_test_rows: None) -> None:
    mailbox = FakeMailbox([make_mail() for _ in range(FETCH_LIMIT + 2)])

    result = fetch_mailbox(migrated_engine, mailbox, now=NOW)

    assert (result.fetched, result.created) == (FETCH_LIMIT, FETCH_LIMIT)


def test_busy_lock_refuses_before_reading_the_mailbox(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    mailbox = SpyMailbox([make_mail()])
    with migrated_engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MAILBOX_LOCK_KEY})
        try:
            with pytest.raises(MailboxBusy):
                fetch_mailbox(migrated_engine, mailbox, now=NOW)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MAILBOX_LOCK_KEY})

    assert mailbox.reads == 0
    assert _stored_sources(migrated_engine) == []


def test_lock_is_released_after_a_mailbox_error(
    migrated_engine: Engine, delete_test_rows: None
) -> None:
    with pytest.raises(MailboxUnavailable):
        fetch_mailbox(migrated_engine, BrokenMailbox(), now=NOW)

    result = fetch_mailbox(migrated_engine, FakeMailbox([make_mail()]), now=NOW)

    assert result.created == 1


def test_log_has_only_counts(
    migrated_engine: Engine, delete_test_rows: None, caplog: pytest.LogCaptureFixture
) -> None:
    sender = f"Poufny Nadawca <poufny-{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}>"
    mailbox = FakeMailbox([make_mail(sender=sender, subject="Tajny temat")])

    with caplog.at_level(logging.INFO, logger="app.mailbox"):
        fetch_mailbox(migrated_engine, mailbox, now=NOW)

    assert [r.getMessage() for r in caplog.records if r.name.startswith("app.mailbox")] == [
        "mailbox fetch: fetched=1 created=1 duplicates=0 skipped=0"
    ]
    assert "Tajny" not in caplog.text
    assert "poufny" not in caplog.text.lower()
