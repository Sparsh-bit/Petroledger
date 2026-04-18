"""
002 — Add content_hash columns to transaction tables.

Adds a ``content_hash`` (VARCHAR 64, nullable, indexed) column to
``upi_transactions``, ``pos_transactions``, and ``pump_logs`` for
deduplication support.

Revision ID: 002
Revises: 001
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: str = "001"
branch_labels: tuple | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── upi_transactions ───────────────────────────────────────────
    op.add_column(
        "upi_transactions",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_upi_transactions_content_hash",
        "upi_transactions",
        ["content_hash"],
    )

    # ── pos_transactions ───────────────────────────────────────────
    op.add_column(
        "pos_transactions",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_pos_transactions_content_hash",
        "pos_transactions",
        ["content_hash"],
    )

    # ── pump_logs ──────────────────────────────────────────────────
    op.add_column(
        "pump_logs",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_pump_logs_content_hash",
        "pump_logs",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_pump_logs_content_hash", table_name="pump_logs")
    op.drop_column("pump_logs", "content_hash")

    op.drop_index("ix_pos_transactions_content_hash", table_name="pos_transactions")
    op.drop_column("pos_transactions", "content_hash")

    op.drop_index("ix_upi_transactions_content_hash", table_name="upi_transactions")
    op.drop_column("upi_transactions", "content_hash")
