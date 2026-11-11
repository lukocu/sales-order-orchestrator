from datetime import datetime
from typing import Any, Literal

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# Enum-like columns are VARCHAR with a CHECK constraint; RecommendationStatus mirrors it.
ENUM_LENGTH = 30

# `failed`: the options are stored, but choosing one of them did not succeed.
RecommendationStatus = Literal["completed", "failed"]


class InquiryRecommendation(SQLModel, table=True):
    """The current recommendation of an inquiry; a new run replaces it.

    `result` holds the recommendation result dumped with `model_dump(mode="json")` and is read
    back with `model_validate`. The status lives only in its column.
    """

    __tablename__ = "inquiry_recommendations"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_recommendations_inquiry_id"),
        CheckConstraint(
            "status IN ('completed', 'failed')", name="ck_inquiry_recommendations_status"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    # The analysis version (corrected_at, else analyzed_at) the recommendation used.
    analysis_version: datetime = Field(sa_type=DateTime(timezone=True))
    # `checked_at` of the check result the recommendation used.
    checks_checked_at: datetime = Field(sa_type=DateTime(timezone=True))
    # `orchestrated_at` of the orchestration result the recommendation used.
    orchestrated_at: datetime = Field(sa_type=DateTime(timezone=True))
    status: RecommendationStatus = Field(sa_type=String(ENUM_LENGTH))
    result: dict[str, Any] = Field(sa_type=JSONB)
    recommended_at: datetime = Field(sa_type=DateTime(timezone=True))
