"""
007 — Create pos_batch_settlements table.

pos_batch_settlements stores one row per POS terminal per shift,
representing the EOD batch settlement total.  This is the card
component of the reconciliation formula:

    Card Total = SUM(pos_batch_settlements.gross_amount)  WHERE shift_id = ?

This table is SEPARATE from pos_transactions (which tracks individual
card swipes fed through the OCR pipeline).  The reconciliation engine
uses pos_batch_settlements only — the gross EOD batch amount before MDR
deduction, matching what actually left the customer's account.

Key design decisions:
  • gross_amount   — amount BEFORE MDR; this is what matches FMS
  • network breakdowns (visa/mastercard/rupay/amex) — for owner reporting
    only, NOT used in the reconciliation formula
  • entry_method   — MANUAL (manager types it in) or OCR (slip photo)
  • is_deleted     — soft delete; financial records never hard-deleted
  • Multiple rows allowed per shift (one per terminal_id)

Revision ID: 007
Revises: 006
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "007"
down_revision: str = "006"
branch_labels: tuple | None = None
depends_on: str | None = None


# ── New enum type ──────────────────────────────────────────────────────

pos_entry_method = sa.Enum("MANUAL", "OCR", name="pos_entry_method")


def upgrade() -> None:

    # ── 2. Create pos_batch_settlements ───────────────────────────────
    op.create_table(
        "pos_batch_settlements",

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

        # ── Terminal identification ────────────────────────────────────
        # Each POS machine has a unique terminal_id assigned by acquiring bank
        sa.Column("terminal_id", sa.String(100), nullable=False),
        # Batch number from EOD settlement slip
        sa.Column("batch_number", sa.String(50), nullable=True),

        # ── Settlement amounts (all Numeric — never float) ────────────
        # gross_amount: total charged to customers BEFORE MDR deduction.
        # This is what the reconciliation formula uses.
        # Rule: always use gross_amount from POS slip, NOT net bank credit.
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),

        # Card network breakdowns — for owner cost reporting ONLY.
        # These are NOT summed separately in the reconciliation formula.
        sa.Column("visa_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("mastercard_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("rupay_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("amex_amount", sa.Numeric(12, 2), nullable=True),

        # ── Batch metadata ─────────────────────────────────────────────
        # Total card swipes in this batch (for reconciliation sanity check)
        sa.Column("total_transactions", sa.Integer(), nullable=True),
        # Date the batch was settled with the acquiring bank
        sa.Column("settlement_date", sa.Date(), nullable=True),

        # ── Entry method ───────────────────────────────────────────────
        # MANUAL: manager typed gross_amount directly into the app
        # OCR: parsed from a POS slip photo via pytesseract/pdfplumber
        sa.Column(
            "entry_method",
            pos_entry_method,
            nullable=False,
            server_default=sa.text("'MANUAL'"),
        ),

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
    )

    # ── 3. Indexes ────────────────────────────────────────────────────
    op.create_index(
        "ix_pos_batch_settlements_shift_id",
        "pos_batch_settlements",
        ["shift_id"],
    )
    op.create_index(
        "ix_pos_batch_settlements_terminal_id",
        "pos_batch_settlements",
        ["terminal_id"],
    )
    op.create_index(
        "ix_pos_batch_settlements_settlement_date",
        "pos_batch_settlements",
        ["settlement_date"],
    )
    op.create_index(
        "ix_pos_batch_settlements_is_deleted",
        "pos_batch_settlements",
        ["is_deleted"],
    )

    # Composite index for the reconciliation query:
    # SELECT SUM(gross_amount) WHERE shift_id = ? AND is_deleted = false
    op.create_index(
        "ix_pos_batch_settlements_shift_deleted",
        "pos_batch_settlements",
        ["shift_id", "is_deleted"],
    )


def downgrade() -> None:

    # ── 3. Drop indexes ────────────────────────────────────────────────
    op.drop_index(
        "ix_pos_batch_settlements_shift_deleted",
        table_name="pos_batch_settlements",
    )
    op.drop_index(
        "ix_pos_batch_settlements_is_deleted",
        table_name="pos_batch_settlements",
    )
    op.drop_index(
        "ix_pos_batch_settlements_settlement_date",
        table_name="pos_batch_settlements",
    )
    op.drop_index(
        "ix_pos_batch_settlements_terminal_id",
        table_name="pos_batch_settlements",
    )
    op.drop_index(
        "ix_pos_batch_settlements_shift_id",
        table_name="pos_batch_settlements",
    )

    # ── 2. Drop table ──────────────────────────────────────────────────
    op.drop_table("pos_batch_settlements")

    # ── 1. Drop enum ───────────────────────────────────────────────────
    pos_entry_method.drop(op.get_bind(), checkfirst=True)
