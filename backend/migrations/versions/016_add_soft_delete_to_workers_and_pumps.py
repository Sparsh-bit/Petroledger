"""add_soft_delete_to_workers_and_pumps

Revision ID: 016
Revises: 015
Create Date: 2026-04-15

Adds is_deleted (bool, default false) and deleted_at (timestamptz, nullable)
to the workers and pumps tables. Hard-delete routes are replaced with soft
deletes; all list/get queries filter on is_deleted = false.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── workers ────────────────────────────────────────────────────────────
    op.add_column(
        "workers",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workers",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workers_is_deleted", "workers", ["is_deleted"])

    # ── pumps ──────────────────────────────────────────────────────────────
    op.add_column(
        "pumps",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "pumps",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pumps_is_deleted", "pumps", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_pumps_is_deleted", table_name="pumps")
    op.drop_column("pumps", "deleted_at")
    op.drop_column("pumps", "is_deleted")

    op.drop_index("ix_workers_is_deleted", table_name="workers")
    op.drop_column("workers", "deleted_at")
    op.drop_column("workers", "is_deleted")
