"""Inquiry analyses: the current parsed fields of an inquiry.

Revision ID: 0004_inquiry_analyses
Revises: 0003_users_inquiries
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_inquiry_analyses"
down_revision: str | Sequence[str] | None = "0003_users_inquiries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inquiry_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("extractor", sa.String(length=20), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("model_fields", postgresql.JSONB(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("uncertain", postgresql.JSONB(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analyzed_by", sa.Integer(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrected_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analyzed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["corrected_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("inquiry_id", name="uq_inquiry_analyses_inquiry_id"),
        sa.CheckConstraint(
            "extractor IN ('fake', 'groq', 'openrouter')", name="ck_inquiry_analyses_extractor"
        ),
    )


def downgrade() -> None:
    op.drop_table("inquiry_analyses")
