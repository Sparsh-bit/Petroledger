"""
006 — Create fms_transactions table and link upi_transactions.

fms_transactions stores one row per fuel dispense event as exported
from the Fuel Management System (FMS).  This is the primary source of
truth for the left-hand side of the reconciliation formula:

    FMS Total = SUM(fms_transactions.amount)  WHERE shift_id = ? AND status = 'COMPLETED'

After creating the table, adds matched_fms_txn_id (FK → fms_transactions)
to upi_transactions so 1:1 UPI↔FMS matching can be recorded.

Key design decisions:
  • volume_litres uses Numeric(10, 3) — three decimal places for litres
  • unit_price    uses Numeric(10, 2) — price per litre in ₹
  • amount        uses Numeric(12, 2) — total ₹ value of transaction
  • is_deleted    (soft-delete) — financial records are NEVER hard-deleted
  • content_hash  — SHA-256 of (shift_id|nozzle_id|txn_reference|amount)
                    for deduplication (ON CONFLICT DO NOTHING on bulk insert)

Revision ID: 006
Revises: 005
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "006"
down_revision: str = "005"
branch_labels: tuple | None = None
depends_on: str | None = None


# ── New enum type ──────────────────────────────────────────────────────

fms_txn_status = sa.Enum(
    "COMPLETED", "VOID", "CANCELLED", name="fms_txn_status"
)


def upgrade() -> None:

    # ── 2. Create fms_transactions ─────────────────────────────────────
    op.create_table(
        "fms_transactions",
        # ── Primary key ────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),

        # ── Foreign keys ───────────────────────────────────────────────
        sa.Column(
            "shift_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "nozzle_id",
            UUID(as_uuid=True),
            sa.ForeignKey("nozzles.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        # ── FMS transaction fields ─────────────────────────────────────
        # Unique reference from FMS (transaction ID in the dispenser log)
        sa.Column("txn_reference", sa.String(100), nullable=False),
        # Date and time as recorded by FMS (stored separately to match FMS
        # log format; combined into a timezone-aware timestamp at query time)
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_time", sa.Time(), nullable=False),
        # Volume in litres — three decimal places (FMS reports to 0.001 L)
        sa.Column("volume_litres", sa.Numeric(10, 3), nullable=False),
        # Price per litre at time of transaction in ₹
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        # Total ₹ amount = volume_litres × unit_price (stored explicitly
        # to preserve FMS-reported value even if price table changes)
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        # Indian OMC product code (MS=petrol, HSD=diesel, SPD97=speed97, CNG)
        sa.Column("product_code", sa.String(10), nullable=True),
        # Raw payment mode string as logged by FMS (not used in formula —
        # kept for audit/debugging only.  Formula treats everything as cash
        # unless a matching digital payment is found.)
        sa.Column("raw_payment_mode", sa.String(50), nullable=True),
        # Transaction status
        sa.Column(
            "status",
            fms_txn_status,
            nullable=False,
            server_default=sa.text("'COMPLETED'"),
        ),

        # ── Deduplication ──────────────────────────────────────────────
        # SHA-256 of (shift_id|nozzle_id|txn_reference|amount) for
        # ON CONFLICT DO NOTHING bulk inserts (same as upi/pos/pump_logs)
        sa.Column("content_hash", sa.String(64), nullable=True),

        # ── Raw data storage ───────────────────────────────────────────
        # Full raw parsed row from FMS log (for debugging / re-parsing)
        sa.Column("raw_data", JSONB, nullable=True),

        # ── Soft delete ────────────────────────────────────────────────
        # Financial records are NEVER hard-deleted — set is_deleted = true
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

        # ── Constraints ────────────────────────────────────────────────
        sa.UniqueConstraint("content_hash", name="uq_fms_transactions_content_hash"),
    )

    # ── 3. Indexes on fms_transactions ─────────────────────────────────
    op.create_index("ix_fms_transactions_shift_id", "fms_transactions", ["shift_id"])
    op.create_index("ix_fms_transactions_nozzle_id", "fms_transactions", ["nozzle_id"])
    op.create_index("ix_fms_transactions_txn_reference", "fms_transactions", ["txn_reference"])
    op.create_index("ix_fms_transactions_txn_date", "fms_transactions", ["txn_date"])
    op.create_index("ix_fms_transactions_status", "fms_transactions", ["status"])
    op.create_index("ix_fms_transactions_is_deleted", "fms_transactions", ["is_deleted"])

    # Composite index for reconciliation query:
    # SELECT SUM(amount) WHERE shift_id = ? AND status = 'COMPLETED' AND is_deleted = false
    op.create_index(
        "ix_fms_transactions_shift_status_deleted",
        "fms_transactions",
        ["shift_id", "status", "is_deleted"],
    )

    # ── 4. Add matched_fms_txn_id to upi_transactions ─────────────────
    # Deferred from migration 005 — fms_transactions now exists.
    # nullable: a UPI transaction may be UNMATCHED (no corresponding FMS row)
    op.add_column(
        "upi_transactions",
        sa.Column("matched_fms_txn_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_upi_transactions_matched_fms_txn",
        "upi_transactions",
        "fms_transactions",
        ["matched_fms_txn_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_upi_transactions_matched_fms_txn_id",
        "upi_transactions",
        ["matched_fms_txn_id"],
    )


def downgrade() -> None:

    # ── 4. Remove matched_fms_txn_id from upi_transactions ────────────
    op.drop_index(
        "ix_upi_transactions_matched_fms_txn_id",
        table_name="upi_transactions",
    )
    op.drop_constraint(
        "fk_upi_transactions_matched_fms_txn",
        "upi_transactions",
        type_="foreignkey",
    )
    op.drop_column("upi_transactions", "matched_fms_txn_id")

    # ── 3. Drop indexes on fms_transactions ────────────────────────────
    op.drop_index(
        "ix_fms_transactions_shift_status_deleted",
        table_name="fms_transactions",
    )
    op.drop_index("ix_fms_transactions_is_deleted", table_name="fms_transactions")
    op.drop_index("ix_fms_transactions_status", table_name="fms_transactions")
    op.drop_index("ix_fms_transactions_txn_date", table_name="fms_transactions")
    op.drop_index(
        "ix_fms_transactions_txn_reference", table_name="fms_transactions"
    )
    op.drop_index("ix_fms_transactions_nozzle_id", table_name="fms_transactions")
    op.drop_index("ix_fms_transactions_shift_id", table_name="fms_transactions")

    # ── 2. Drop fms_transactions ───────────────────────────────────────
    op.drop_table("fms_transactions")

    # ── 1. Drop enum ───────────────────────────────────────────────────
    fms_txn_status.drop(op.get_bind(), checkfirst=True)
