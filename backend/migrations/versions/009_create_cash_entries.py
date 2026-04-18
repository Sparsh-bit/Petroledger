"""
009 — Create cash_entries table.

cash_entries stores the physical cash count submitted by an attendant
or shift in-charge at shift end.  This is the right-hand side of the
reconciliation formula:

    Variance = Expected Cash - actual_cash
    where actual_cash = SUM of physical_cash from cash_entries for the shift

Design notes:
  • Denomination breakdown is optional but strongly encouraged — it
    makes disputes easier to resolve and catches counting errors.
  • physical_cash must equal the sum of all denomination columns when
    denominations are provided.  This check is enforced in the
    application layer (not a DB constraint) to allow partial entry.
  • Once submitted, a cash entry is LOCKED — it cannot be edited
    without an owner-level override that writes an audit log entry.
  • is_deleted — soft delete; financial records never hard-deleted.
  • A shift may have multiple cash entries (e.g. one per attendant if
    multiple attendants worked different nozzles on the same shift).
    The reconciliation engine sums all non-deleted physical_cash values.

Indian denomination reference (as of 2024):
  ₹2000 (being withdrawn but still valid), ₹500, ₹200, ₹100,
  ₹50, ₹20, ₹10, coins (₹1, ₹2, ₹5 — stored as decimal total)

Revision ID: 009
Revises: 008
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "009"
down_revision: str = "008"
branch_labels: tuple | None = None
depends_on: str | None = None


def upgrade() -> None:

    op.create_table(
        "cash_entries",

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
        # The attendant who is handing in the cash.
        # nullable: a shift-level cash entry may not be per-attendant.
        sa.Column(
            "attendant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # The nozzle this cash entry covers.
        # nullable: a single lump-sum entry may cover all nozzles.
        sa.Column(
            "nozzle_id",
            UUID(as_uuid=True),
            sa.ForeignKey("nozzles.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # ── Cash total (Numeric — never float) ────────────────────────
        # The total physical cash being turned in, in ₹.
        # This is what the reconciliation formula uses as actual_cash.
        sa.Column("physical_cash", sa.Numeric(12, 2), nullable=False),

        # ── Denomination breakdown (all nullable — optional but useful) ─
        # Count of each note/coin denomination.
        # physical_cash should equal:
        #   2000*d_2000 + 500*d_500 + 200*d_200 + 100*d_100
        #   + 50*d_50 + 20*d_20 + 10*d_10 + coins
        # Validation is enforced in the application layer, not DB.
        sa.Column("denomination_2000", sa.Integer(), nullable=True),
        sa.Column("denomination_500",  sa.Integer(), nullable=True),
        sa.Column("denomination_200",  sa.Integer(), nullable=True),
        sa.Column("denomination_100",  sa.Integer(), nullable=True),
        sa.Column("denomination_50",   sa.Integer(), nullable=True),
        sa.Column("denomination_20",   sa.Integer(), nullable=True),
        sa.Column("denomination_10",   sa.Integer(), nullable=True),
        # coins: total ₹ value of all coins (₹1 + ₹2 + ₹5 mixed)
        sa.Column("coins", sa.Numeric(6, 2), nullable=True),

        # ── Submission metadata ────────────────────────────────────────
        # user_id of whoever clicked "Submit" in the app
        sa.Column(
            "submitted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        # ── Lock flag ─────────────────────────────────────────────────
        # Once True, this entry cannot be modified without owner override
        # (which must write an audit_log entry with the reason).
        sa.Column(
            "is_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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

    # ── Indexes ────────────────────────────────────────────────────────
    op.create_index(
        "ix_cash_entries_shift_id",
        "cash_entries",
        ["shift_id"],
    )
    op.create_index(
        "ix_cash_entries_attendant_id",
        "cash_entries",
        ["attendant_id"],
    )
    op.create_index(
        "ix_cash_entries_nozzle_id",
        "cash_entries",
        ["nozzle_id"],
    )
    op.create_index(
        "ix_cash_entries_is_deleted",
        "cash_entries",
        ["is_deleted"],
    )
    op.create_index(
        "ix_cash_entries_is_locked",
        "cash_entries",
        ["is_locked"],
    )

    # Composite index for the reconciliation query:
    # SELECT SUM(physical_cash) WHERE shift_id = ? AND is_deleted = false
    op.create_index(
        "ix_cash_entries_shift_deleted",
        "cash_entries",
        ["shift_id", "is_deleted"],
    )


def downgrade() -> None:

    op.drop_index("ix_cash_entries_shift_deleted", table_name="cash_entries")
    op.drop_index("ix_cash_entries_is_locked",     table_name="cash_entries")
    op.drop_index("ix_cash_entries_is_deleted",    table_name="cash_entries")
    op.drop_index("ix_cash_entries_nozzle_id",     table_name="cash_entries")
    op.drop_index("ix_cash_entries_attendant_id",  table_name="cash_entries")
    op.drop_index("ix_cash_entries_shift_id",      table_name="cash_entries")

    op.drop_table("cash_entries")
