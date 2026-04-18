"""soft_delete_remaining_entities

Revision ID: 025
Revises: 024
Create Date: 2026-04-18

Extends soft-delete coverage to the remaining financial entities:

- users               : adds `is_deleted` (bool, default false) + `deleted_at`
- organizations       : adds `is_deleted` + `deleted_at` + `deleted_reason`
                        (keeps existing `is_active` — deactivation vs.
                        permanent retirement are distinct)
- upi_transactions    : adds `is_deleted` + `deleted_at` + `deleted_reason`
- shifts              : extends `shift_status` enum with `CANCELLED` value
                        (shifts are never deleted, only cancelled before
                        completion — a ledger entry for every physical shift)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str = "024"
branch_labels = None
depends_on = None


_BOOL_COLS: list[tuple[str, str]] = [
    ("users", "is_deleted"),
    ("organizations", "is_deleted"),
    ("upi_transactions", "is_deleted"),
]
_TS_COLS: list[tuple[str, str]] = [
    ("users", "deleted_at"),
    ("organizations", "deleted_at"),
    ("upi_transactions", "deleted_at"),
]
_REASON_COLS: list[tuple[str, str]] = [
    ("organizations", "deleted_reason"),
    ("upi_transactions", "deleted_reason"),
]


def upgrade() -> None:
    for table, col in _BOOL_COLS:
        op.add_column(
            table,
            sa.Column(
                col,
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index(f"ix_{table}_is_deleted", table, [col])

    for table, col in _TS_COLS:
        op.add_column(
            table,
            sa.Column(col, sa.DateTime(timezone=True), nullable=True),
        )

    for table, col in _REASON_COLS:
        op.add_column(
            table,
            sa.Column(col, sa.String(length=500), nullable=True),
        )

    # shift_status enum: add CANCELLED. Enum is modeled as String/VARCHAR
    # with `native_enum=False`, so no PostgreSQL-level ALTER TYPE is needed
    # — the CHECK is enforced at the application layer via the Enum class.
    # Nothing to do here; the Python enum change is the authoritative value set.


def downgrade() -> None:
    for table, col in _REASON_COLS:
        op.drop_column(table, col)
    for table, col in _TS_COLS:
        op.drop_column(table, col)
    for table, col in _BOOL_COLS:
        op.drop_index(f"ix_{table}_is_deleted", table_name=table)
        op.drop_column(table, col)
