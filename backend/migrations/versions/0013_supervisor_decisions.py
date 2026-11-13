"""Supervisor decisions in the draft history and an index for the supervisor's inbox.

Revision ID: 0013_supervisor_decisions
Revises: 0012_drafts_decisions
Create Date: 2026-11-13

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_supervisor_decisions"
down_revision: str | Sequence[str] | None = "0012_drafts_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIONS = "'edit', 'approve', 'reject', 'supervisor_approve', 'supervisor_reject'"
OLD_ACTIONS = "'edit', 'approve', 'reject'"
ACTION_CHECK = "ck_inquiry_draft_decisions_action"


def upgrade() -> None:
    op.drop_constraint(ACTION_CHECK, "inquiry_draft_decisions", type_="check")
    op.create_check_constraint(ACTION_CHECK, "inquiry_draft_decisions", f"action IN ({ACTIONS})")
    op.create_index("ix_inquiry_drafts_status", "inquiry_drafts", ["status"])


def downgrade() -> None:
    # Fails while supervisor decisions exist: the history is an audit trail, never deleted.
    op.drop_index("ix_inquiry_drafts_status", table_name="inquiry_drafts")
    op.drop_constraint(ACTION_CHECK, "inquiry_draft_decisions", type_="check")
    op.create_check_constraint(
        ACTION_CHECK, "inquiry_draft_decisions", f"action IN ({OLD_ACTIONS})"
    )
