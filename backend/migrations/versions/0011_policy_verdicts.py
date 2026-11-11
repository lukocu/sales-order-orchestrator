"""Policy thresholds (seeded example values) and the policy verdict of an inquiry.

Revision ID: 0011_policy_verdicts
Revises: 0010_supplier_offer_unique
Create Date: 2026-11-11

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_policy_verdicts"
down_revision: str | Sequence[str] | None = "0010_supplier_offer_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Example thresholds, not a real company policy (FR-008): every row is `is_example = true`
# and the UI labels them as examples. Change them with SQL or a later migration.
SEED_RULES = [
    {
        "code": "margin_min_percent",
        "threshold": Decimal("20.00"),
        "unit": "percent",
        "description": "Minimum margin of the selected option",
        "is_example": True,
    },
    {
        "code": "discount_max_percent",
        "threshold": Decimal("15.00"),
        "unit": "percent",
        "description": "Maximum discount the customer may get without approval",
        "is_example": True,
    },
    {
        "code": "order_value_max",
        "threshold": Decimal("30000.00"),
        "unit": "PLN",
        "description": "Maximum order value (PLN net) without approval",
        "is_example": True,
    },
]


def upgrade() -> None:
    policy_rules = op.create_table(
        "policy_rules",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("is_example", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.CheckConstraint(
            "code IN ('margin_min_percent', 'discount_max_percent', 'order_value_max')",
            name="ck_policy_rules_code",
        ),
        sa.CheckConstraint("threshold >= 0", name="ck_policy_rules_threshold"),
        sa.CheckConstraint("unit IN ('percent', 'PLN')", name="ck_policy_rules_unit"),
    )
    op.bulk_insert(policy_rules, SEED_RULES)

    op.create_table(
        "inquiry_policy_verdicts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["inquiry_recommendations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_policy_verdicts_inquiry_id"),
        sa.CheckConstraint(
            "outcome IN ('no_approval_needed', 'requires_supervisor')",
            name="ck_inquiry_policy_verdicts_outcome",
        ),
    )
    op.create_index("ix_inquiry_policy_verdicts_run_id", "inquiry_policy_verdicts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_inquiry_policy_verdicts_run_id", table_name="inquiry_policy_verdicts")
    op.drop_table("inquiry_policy_verdicts")
    op.drop_table("policy_rules")
