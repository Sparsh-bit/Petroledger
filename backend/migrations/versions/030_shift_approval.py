"""shift_approval

Revision ID: 030
Revises: 029
Create Date: 2026-04-18

Adds approval-workflow fields to `shifts`:
- approval_notes        : optional notes from the approving owner
- approved_by_user_id   : FK → users.id (SET NULL on user delete)
- approved_at           : UTC timestamp
- rejection_reason      : mandatory on REJECTED

`shift_status` is modeled as VARCHAR (native_enum=False), so the new
`pending_approval` / `rejected` values are a Python-layer change — no
ALTER TYPE needed here.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "030"
down_revision: str = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shifts",
        sa.Column("approval_notes", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column(
            "approved_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "shifts",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column("rejection_reason", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shifts", "rejection_reason")
    op.drop_column("shifts", "approved_at")
    op.drop_column("shifts", "approved_by_user_id")
    op.drop_column("shifts", "approval_notes")
