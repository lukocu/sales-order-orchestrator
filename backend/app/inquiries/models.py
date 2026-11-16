from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlmodel import Field, SQLModel

# Where an inquiry came from: a seeded sample (also eval and tests) or the test mailbox.
InquirySource = Literal["sample", "mailbox"]

# Enum-like columns are VARCHAR with a CHECK constraint; the Literal type above mirrors it.
SOURCE_LENGTH = 20


class Inquiry(SQLModel, table=True):
    """A customer inquiry, shaped like an e-mail so real mailbox messages fit the same table.

    `external_id` is the hex SHA-256 of the message's identifier (its Message-ID with the sender
    address and subject, or the raw bytes when it has none); NULL for sample inquiries.
    `(source, external_id)` is unique, so a message fetched twice is stored once.
    """

    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint("source IN ('sample', 'mailbox')", name="ck_inquiries_source"),
        Index("ux_inquiries_source_external_id", "source", "external_id", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    sender_name: str = Field(max_length=200)
    sender_email: str = Field(max_length=320)
    subject: str = Field(max_length=300)
    body: str = Field(sa_type=Text)
    received_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
    source: InquirySource = Field(
        default="sample",
        max_length=SOURCE_LENGTH,
        sa_type=String(SOURCE_LENGTH),
        sa_column_kwargs={"server_default": "sample"},
    )
    external_id: str | None = Field(default=None, max_length=64)
