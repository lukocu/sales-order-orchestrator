"""One mailbox fetch: lock, read the newest messages, convert them, store the new ones.

Only counts are logged, never subjects, senders, bodies or Message-IDs.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.mailbox.client import Mailbox
from app.mailbox.message import MailCandidate, to_candidate
from app.mailbox.store import insert_new

logger = logging.getLogger(__name__)

# Newest messages read per fetch; older ones are not looked at.
FETCH_LIMIT = 20
# Key of the session-level advisory lock that makes fetches exclusive ("mail" in ASCII).
MAILBOX_LOCK_KEY = 0x6D61696C


class MailboxBusy(RuntimeError):
    """Another fetch holds the mailbox lock on this database."""


class FetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetched: int  # messages read from the mailbox
    created: int  # new inquiries
    duplicates: int  # readable messages already stored (or repeated in the batch)
    skipped: int  # messages without a sender or unreadable


def fetch_mailbox(engine: Engine, mailbox: Mailbox, *, now: datetime | None = None) -> FetchResult:
    """Store the newest `FETCH_LIMIT` messages not stored yet as `mailbox` inquiries.

    `now` is the receive time of messages without a (valid) `Date`. Raises `MailboxBusy`,
    before connecting to the mailbox, when another fetch is in progress; mailbox errors
    propagate.
    """
    with _fetch_lock(engine):
        raw_messages = mailbox.latest(FETCH_LIMIT)
        fetched_at = now if now is not None else datetime.now(UTC)
        results = [to_candidate(raw, fetched_at=fetched_at) for raw in raw_messages]
        candidates = [r for r in results if isinstance(r, MailCandidate)]
        created = insert_new(engine, candidates)
    result = FetchResult(
        fetched=len(raw_messages),
        created=created,
        duplicates=len(candidates) - created,
        skipped=len(results) - len(candidates),
    )
    logger.info(
        "mailbox fetch: fetched=%d created=%d duplicates=%d skipped=%d",
        result.fetched,
        result.created,
        result.duplicates,
        result.skipped,
    )
    return result


@contextmanager
def _fetch_lock(engine: Engine) -> Iterator[None]:
    """Hold the mailbox lock on a dedicated connection for the duration of the block."""
    with engine.connect() as connection:
        locked = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": MAILBOX_LOCK_KEY}
        ).scalar_one()
        connection.commit()
        if not locked:
            raise MailboxBusy("Mailbox fetch already in progress")
        try:
            yield
        finally:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": MAILBOX_LOCK_KEY}
                )
                connection.commit()
            except SQLAlchemyError:
                # Closing the session releases its lock; the original error (if any) stays.
                connection.invalidate()
