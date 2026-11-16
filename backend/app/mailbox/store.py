"""Store mailbox candidates as `mailbox` inquiries, skipping the ones already stored."""

from collections.abc import Sequence

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col

from app.inquiries.models import Inquiry
from app.mailbox.message import MailCandidate


def insert_new(engine: Engine, candidates: Sequence[MailCandidate]) -> int:
    """Insert the candidates not stored yet, in one transaction; returns how many were new.

    `ON CONFLICT (source, external_id) DO NOTHING` skips stored messages without a prior
    lookup; a message repeated within the batch is inserted once.
    """
    unique: dict[str, MailCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.external_id, candidate)
    if not unique:
        return 0
    rows = [
        {
            "source": "mailbox",
            "external_id": c.external_id,
            "sender_name": c.sender_name,
            "sender_email": c.sender_email,
            "subject": c.subject,
            "body": c.body,
            "received_at": c.received_at,
        }
        for c in unique.values()
    ]
    statement = (
        insert(Inquiry)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["source", "external_id"])
        .returning(col(Inquiry.id))
    )
    with engine.begin() as connection:
        return len(connection.execute(statement).all())
