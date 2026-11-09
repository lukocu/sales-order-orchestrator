"""Step tracing: trace_runs and trace_steps.

Revision ID: 0002_step_tracing
Revises: 0001_baseline
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_step_tracing"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trace_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_us", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_trace_runs_status"
        ),
    )
    op.create_index("ix_trace_runs_subject", "trace_runs", ["subject_type", "subject_id"])

    op.create_table(
        "trace_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_type", sa.String(length=200), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=16, scale=10), nullable=True),
        sa.Column("price_status", sa.String(length=20), nullable=False),
        sa.Column("price_source", sa.String(length=100), nullable=True),
        sa.Column("raw_usage", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_us", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["trace_runs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('deterministic', 'llm')", name="ck_trace_steps_kind"),
        sa.CheckConstraint("status IN ('ok', 'failed')", name="ck_trace_steps_status"),
        sa.CheckConstraint(
            "price_status IN ('priced', 'unpriced', 'not_applicable')",
            name="ck_trace_steps_price_status",
        ),
    )
    op.create_index("ix_trace_steps_run_id", "trace_steps", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_trace_steps_run_id", table_name="trace_steps")
    op.drop_table("trace_steps")
    op.drop_index("ix_trace_runs_subject", table_name="trace_runs")
    op.drop_table("trace_runs")
