from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.settings import LlmProvider

# Enum-like columns are VARCHAR with a CHECK constraint; LlmProvider mirrors it.
EXTRACTOR_LENGTH = 20


class InquiryAnalysis(SQLModel, table=True):
    """The current analysis of an inquiry; a new analysis replaces it.

    The JSONB columns hold `ParsedFields.model_dump(mode="json")` (Decimal and date as
    strings) and are read back with `ParsedFields.model_validate`.
    """

    __tablename__ = "inquiry_analyses"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_analyses_inquiry_id"),
        CheckConstraint(
            "extractor IN ('fake', 'groq', 'openrouter')", name="ck_inquiry_analyses_extractor"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    extractor: LlmProvider = Field(sa_type=String(EXTRACTOR_LENGTH))
    reference_date: date  # received_at as a date in Europe/Warsaw
    # Fields as the model returned them, unchanged until the next analysis. The attribute
    # is not called `model_fields`: that name belongs to pydantic.
    fields_from_model: dict[str, Any] = Field(
        sa_column=Column("model_fields", JSONB, nullable=False)
    )
    fields: dict[str, Any] = Field(sa_type=JSONB)  # current values, after corrections
    uncertain: dict[str, Any] = Field(sa_type=JSONB)  # field name -> reason
    analyzed_at: datetime = Field(sa_type=DateTime(timezone=True))
    analyzed_by: int | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    corrected_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    corrected_by: int | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
