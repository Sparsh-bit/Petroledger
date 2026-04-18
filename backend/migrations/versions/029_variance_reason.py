"""variance_reason

Revision ID: 029
Revises: 028
Create Date: 2026-04-18

Adds owner-auditable variance-classification columns to
`reconciliation_results`:
- variance_reason        : enum-style string (kept as VARCHAR so adding
                           new codes doesn't need a PG ALTER TYPE)
- variance_notes         : free-text explanation
- reason_set_by_user_id  : who classified
- reason_set_at          : when
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "029"
down_revision: str = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reconciliation_results",
        sa.Column("variance_reason", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("variance_notes", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column(
            "reason_set_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("reason_set_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reconciliation_results", "reason_set_at")
    op.drop_column("reconciliation_results", "reason_set_by_user_id")
    op.drop_column("reconciliation_results", "variance_notes")
    op.drop_column("reconciliation_results", "variance_reason")
