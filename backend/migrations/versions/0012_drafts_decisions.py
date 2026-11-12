"""Reply draft of an inquiry and the append-only history of the salesperson's decisions.

Revision ID: 0012_drafts_decisions
Revises: 0011_policy_verdicts
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_drafts_decisions"
down_revision: str | Sequence[str] | None = "0011_policy_verdicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = "'draft', 'ready_to_send', 'awaiting_supervisor', 'rejected'"


def upgrade() -> None:
    op.create_table(
        "inquiry_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("drafted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_drafts_inquiry_id"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_inquiry_drafts_status"),
    )
    op.create_index("ix_inquiry_drafts_run_id", "inquiry_drafts", ["run_id"])

    op.create_table(
        "inquiry_draft_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("status_after", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "action IN ('edit', 'approve', 'reject')",
            name="ck_inquiry_draft_decisions_action",
        ),
        sa.CheckConstraint(
            f"status_after IN ({STATUSES})", name="ck_inquiry_draft_decisions_status_after"
        ),
    )
    op.create_index(
        "ix_inquiry_draft_decisions_inquiry_id", "inquiry_draft_decisions", ["inquiry_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inquiry_draft_decisions_inquiry_id", table_name="inquiry_draft_decisions")
    op.drop_table("inquiry_draft_decisions")
    op.drop_index("ix_inquiry_drafts_run_id", table_name="inquiry_drafts")
    op.drop_table("inquiry_drafts")
