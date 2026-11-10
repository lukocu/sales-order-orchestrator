"""Index inquiry_analyses.run_id (FK with ON DELETE SET NULL), like other FK indexes.

Revision ID: 0005_inquiry_analyses_run_index
Revises: 0004_inquiry_analyses
Create Date: 2026-11-10

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_inquiry_analyses_run_index"
down_revision: str | Sequence[str] | None = "0004_inquiry_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_inquiry_analyses_run_id", "inquiry_analyses", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_inquiry_analyses_run_id", table_name="inquiry_analyses")
