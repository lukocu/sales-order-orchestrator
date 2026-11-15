"""Inquiry source and external id, so mailbox messages can be told apart and deduplicated.

Existing rows (the sample inquiries) get `sample` from the server default.

Revision ID: 0014_inquiry_source
Revises: 0013_supervisor_decisions
Create Date: 2026-11-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_inquiry_source"
down_revision: str | Sequence[str] | None = "0013_supervisor_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CHECK = "ck_inquiries_source"
SOURCE_EXTERNAL_ID_INDEX = "ux_inquiries_source_external_id"


def upgrade() -> None:
    op.add_column(
        "inquiries",
        sa.Column("source", sa.String(20), nullable=False, server_default="sample"),
    )
    op.add_column("inquiries", sa.Column("external_id", sa.String(64), nullable=True))
    op.create_check_constraint(SOURCE_CHECK, "inquiries", "source IN ('sample', 'mailbox')")
    # NULLs are distinct, so the sample and eval inquiries (no external id) never collide.
    op.create_index(SOURCE_EXTERNAL_ID_INDEX, "inquiries", ["source", "external_id"], unique=True)


def downgrade() -> None:
    # Mailbox inquiries stay as plain inquiries; only the source information is lost.
    op.drop_index(SOURCE_EXTERNAL_ID_INDEX, table_name="inquiries")
    op.drop_constraint(SOURCE_CHECK, "inquiries", type_="check")
    op.drop_column("inquiries", "external_id")
    op.drop_column("inquiries", "source")
