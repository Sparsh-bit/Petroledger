"""
004 — Replace plain indexes on content_hash with unique constraints.

The ``ON CONFLICT (content_hash) DO NOTHING`` used by
``NormalizationService.bulk_insert()`` requires a unique constraint,
not just a plain index.  This migration drops the existing indexes and
adds proper unique constraints on ``upi_transactions``,
``pos_transactions``, and ``pump_logs``.

Revision ID: 004
Revises: 003
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: tuple | None = None
depends_on: str | None = None

TABLES = ["upi_transactions", "pos_transactions", "pump_logs"]


def upgrade() -> None:
    for table in TABLES:
        # Drop the plain index created in migration 002
        op.drop_index(f"ix_{table}_content_hash", table_name=table)

        # Add a unique constraint on the same column
        op.create_unique_constraint(
            f"uq_{table}_content_hash",
            table,
            ["content_hash"],
        )


def downgrade() -> None:
    for table in TABLES:
        # Drop the unique constraint
        op.drop_constraint(f"uq_{table}_content_hash", table, type_="unique")

        # Re-create the plain index
        op.create_index(f"ix_{table}_content_hash", table, ["content_hash"])
