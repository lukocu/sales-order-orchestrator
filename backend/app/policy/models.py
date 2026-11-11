from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, UniqueConstraint, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.policy.schema import PolicyOutcome, ThresholdCode, Unit

# Enum-like columns are VARCHAR with a CHECK constraint; the Literals in schema mirror them.
ENUM_LENGTH = 30


class PolicyRule(SQLModel, table=True):
    """A policy threshold (configuration seeded by a migration; example values, FR-008)."""

    __tablename__ = "policy_rules"
    __table_args__ = (
        CheckConstraint(
            "code IN ('margin_min_percent', 'discount_max_percent', 'order_value_max')",
            name="ck_policy_rules_code",
        ),
        CheckConstraint("threshold >= 0", name="ck_policy_rules_threshold"),
        CheckConstraint("unit IN ('percent', 'PLN')", name="ck_policy_rules_unit"),
    )

    code: ThresholdCode = Field(primary_key=True, sa_type=String(ENUM_LENGTH))
    threshold: Decimal = Field(sa_type=Numeric(12, 2))
    unit: Unit = Field(sa_type=String(ENUM_LENGTH))
    description: str = Field(max_length=200)
    is_example: bool = Field(default=True, sa_column_kwargs={"server_default": true()})


class InquiryPolicyVerdict(SQLModel, table=True):
    """The current policy verdict of an inquiry; a new evaluation replaces it.

    `result` holds `PolicyResult.model_dump(mode="json")` and is read back with
    `PolicyResult.model_validate`. The outcome is also stored in its own column.
    """

    __tablename__ = "inquiry_policy_verdicts"
    __table_args__ = (
        UniqueConstraint("inquiry_id", name="uq_inquiry_policy_verdicts_inquiry_id"),
        CheckConstraint(
            "outcome IN ('no_approval_needed', 'requires_supervisor')",
            name="ck_inquiry_policy_verdicts_outcome",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    inquiry_id: int = Field(foreign_key="inquiries.id", ondelete="CASCADE")
    recommendation_id: int = Field(foreign_key="inquiry_recommendations.id", ondelete="CASCADE")
    run_id: int | None = Field(
        default=None, foreign_key="trace_runs.id", ondelete="SET NULL", index=True
    )
    # `recommended_at` of the recommendation the verdict evaluated.
    recommended_at: datetime = Field(sa_type=DateTime(timezone=True))
    outcome: PolicyOutcome = Field(sa_type=String(ENUM_LENGTH))
    result: dict[str, Any] = Field(sa_type=JSONB)
    evaluated_at: datetime = Field(sa_type=DateTime(timezone=True))
