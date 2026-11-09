from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlmodel import Field, SQLModel


class Inquiry(SQLModel, table=True):
    """A customer inquiry, shaped like an e-mail so real mailbox messages fit the same table."""

    __tablename__ = "inquiries"

    id: int | None = Field(default=None, primary_key=True)
    sender_name: str = Field(max_length=200)
    sender_email: str = Field(max_length=320)
    subject: str = Field(max_length=300)
    body: str = Field(sa_type=Text)
    received_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)
