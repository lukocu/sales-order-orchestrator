"""The check result an orchestration used (`checks_checked_at`), so a result computed from a
replaced check result is dropped on store and shown as stale on read.

Revision ID: 0008_orchestration_checks_ref
Revises: 0007_orchestration_data
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_orchestration_checks_ref"
down_revision: str | Sequence[str] | None = "0007_orchestration_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inquiry_orchestrations",
        sa.Column("checks_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing rows were computed from the inquiry's current check result (one per inquiry):
    # a newer re-check would have replaced the orchestration too, unless it failed, which the
    # old schema could not tell apart.
    op.execute(
        """
        UPDATE inquiry_orchestrations AS o
        SET checks_checked_at = c.checked_at
        FROM inquiry_checks AS c
        WHERE c.inquiry_id = o.inquiry_id
        """
    )
    # An orchestration always follows a check result; a row without one cannot be shown as
    # current, and "Re-run orchestrator" recreates it.
    op.execute("DELETE FROM inquiry_orchestrations WHERE checks_checked_at IS NULL")
    op.alter_column("inquiry_orchestrations", "checks_checked_at", nullable=False)


def downgrade() -> None:
    op.drop_column("inquiry_orchestrations", "checks_checked_at")
