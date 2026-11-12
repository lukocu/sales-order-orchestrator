from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.draft.schema import DecisionAction, DraftStatus

# Enum-like columns are VARCHAR with a CHECK constraint; the Literals in schema mirror them.
ENUM_LENGTH = 30
_STATUSES = "'draft', 'ready_to_send', 'awaiting_supervisor', 'rejected'"


class InquiryDraft(SQLModel, table=True):
    """The current reply draft of an inquiry, pinned to the recommendation it was built from.

    `result` holds `DraftResult.model_dump(mode="json")` and is read back with
    `DraftResult.model_validate`. `updated_at` changes on every write and is the optimistic
    concurrency token of edits and decisions.
    """

    __tablename__ = "inquiry_drafts"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_drafts_inquiry_id"),
        CheckConstraint(f"status IN ({_STATUSES})", name="ck_inquiry_drafts_status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    # `recommended_at` of the recommendation the draft was built from.
    recommended_at: datetime = Field(sa_type=DateTime(timezone=True))
    status: DraftStatus = Field(sa_type=String(ENUM_LENGTH))
    result: dict[str, Any] = Field(sa_type=JSONB)
    drafted_at: datetime = Field(sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(sa_type=DateTime(timezone=True))


class InquiryDraftDecision(SQLModel, table=True):
    """One decision of a salesperson on a draft; append-only, kept when the draft is replaced.

    `snapshot` holds `DecisionSnapshot.model_dump(mode="json")`.
    """

    __tablename__ = "inquiry_draft_decisions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('edit', 'approve', 'reject')",
            name="ck_inquiry_draft_decisions_action",
        ),
        CheckConstraint(
            f"status_after IN ({_STATUSES})", name="ck_inquiry_draft_decisions_status_after"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE", index=True)
    # `recommended_at` of the recommendation the decided draft was built from.
    recommended_at: datetime = Field(sa_type=DateTime(timezone=True))
    action: DecisionAction = Field(sa_type=String(ENUM_LENGTH))
    status_after: DraftStatus = Field(sa_type=String(ENUM_LENGTH))
    reason: str | None = Field(default=None, sa_type=Text)
    decided_by: int | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    decided_at: datetime = Field(sa_type=DateTime(timezone=True))
    snapshot: dict[str, Any] = Field(sa_type=JSONB)
