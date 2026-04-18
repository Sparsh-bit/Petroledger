"""
008 — Create fleet_transactions table.

fleet_transactions stores one row per fleet card provider per shift,
representing the total fleet card dispensing for that shift.  This is
the fleet component of the reconciliation formula:

    Fleet Total = SUM(fleet_transactions.total_amount)  WHERE shift_id = ?

Important domain notes:
  • Fleet card funds settle WEEKLY or FORTNIGHTLY with the OMC.
    The reconciliation uses the TRANSACTION VALUE (fuel dispensed × price)
    on the shift date — NOT the bank settlement amount or date.
    Owners must understand this distinction.
  • Sources: BPCL XTRAPOWER, IOCL Fleet Card, HPCL FleetCard,
    Indian Oil XtraPower, and private fleet cards.
  • MVP entry method is MANUAL (manager enters daily total per provider).
    Phase 2 will add CSV upload from OMC portal.
  • Multiple rows per shift are allowed — one per fleet_provider.
  • is_deleted — soft delete; financial records never hard-deleted.

Revision ID: 008
Revises: 007
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "008"
down_revision: str = "007"
branch_labels: tuple | None = None
depends_on: str | None = None


# ── New enum types ─────────────────────────────────────────────────────

fleet_provider = sa.Enum(
    "XTRAPOWER",   # BPCL XtraPower
    "IOCL",        # Indian Oil Fleet Card / XtraPower
    "HPCL",        # HPCL FleetCard
    "PRIVATE",     # Private/corporate fleet cards
    "OTHER",       # Any other provider
    name="fleet_provider",
)

fleet_entry_method = sa.Enum(
    "MANUAL",  # Manager enters total manually
    "CSV",     # Parsed from OMC portal CSV export (Phase 2)
    name="fleet_entry_method",
)


def upgrade() -> None:

    # ── 2. Create fleet_transactions ───────────────────────────────────
    op.create_table(
        "fleet_transactions",

        # ── Primary key ────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),

        # ── Foreign key ────────────────────────────────────────────────
        sa.Column(
            "shift_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # ── Fleet provider ─────────────────────────────────────────────
        sa.Column("fleet_provider", fleet_provider, nullable=False),

        # ── Totals (all Numeric — never float) ────────────────────────
        # Number of individual fleet card swipes in this batch
        sa.Column("total_transactions", sa.Integer(), nullable=True),
        # Total ₹ amount dispensed on fleet cards for this provider this shift.
        # Uses TRANSACTION VALUE (dispensed × price), not settlement amount.
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),

        # ── Entry method ───────────────────────────────────────────────
        sa.Column(
            "entry_method",
            fleet_entry_method,
            nullable=False,
            server_default=sa.text("'MANUAL'"),
        ),

        # ── Optional reference fields ──────────────────────────────────
        # Free-text note from manager (e.g. "from XTRAPOWER portal")
        sa.Column("notes", sa.Text(), nullable=True),

        # ── Soft delete ────────────────────────────────────────────────
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_reason", sa.Text(), nullable=True),

        # ── Timestamps ─────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        # ── Constraint: one row per provider per shift ─────────────────
        # Prevents accidental double-entry by the manager.
        # If a correction is needed, soft-delete the old row and insert new.
        sa.UniqueConstraint(
            "shift_id",
            "fleet_provider",
            "is_deleted",
            name="uq_fleet_transactions_shift_provider_active",
        ),
    )

    # ── 3. Indexes ─────────────────────────────────────────────────────
    op.create_index(
        "ix_fleet_transactions_shift_id",
        "fleet_transactions",
        ["shift_id"],
    )
    op.create_index(
        "ix_fleet_transactions_fleet_provider",
        "fleet_transactions",
        ["fleet_provider"],
    )
    op.create_index(
        "ix_fleet_transactions_is_deleted",
        "fleet_transactions",
        ["is_deleted"],
    )

    # Composite index for the reconciliation query:
    # SELECT SUM(total_amount) WHERE shift_id = ? AND is_deleted = false
    op.create_index(
        "ix_fleet_transactions_shift_deleted",
        "fleet_transactions",
        ["shift_id", "is_deleted"],
    )


def downgrade() -> None:

    # ── 3. Drop indexes ────────────────────────────────────────────────
    op.drop_index(
        "ix_fleet_transactions_shift_deleted",
        table_name="fleet_transactions",
    )
    op.drop_index(
        "ix_fleet_transactions_is_deleted",
        table_name="fleet_transactions",
    )
    op.drop_index(
        "ix_fleet_transactions_fleet_provider",
        table_name="fleet_transactions",
    )
    op.drop_index(
        "ix_fleet_transactions_shift_id",
        table_name="fleet_transactions",
    )

    # ── 2. Drop table ──────────────────────────────────────────────────
    op.drop_table("fleet_transactions")

    # ── 1. Drop enums ──────────────────────────────────────────────────
    fleet_entry_method.drop(op.get_bind(), checkfirst=True)
    fleet_provider.drop(op.get_bind(), checkfirst=True)
