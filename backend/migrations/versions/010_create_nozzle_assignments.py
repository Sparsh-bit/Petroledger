"""
010 — Create nozzle_assignments table.

nozzle_assignments records which attendant is responsible for which
nozzle during a shift.  This is what enables per-attendant reconciliation
— one of the key features of FuelRecon.

How it works:
  • At shift start, the shift in-charge assigns each nozzle to an attendant
    (via QR scan or PIN entry in the app).
  • If a handover happens mid-shift (attendant A is relieved by attendant B
    on nozzle N3), the first row gets relieved_at set and a new row is
    inserted for attendant B.
  • The reconciliation engine uses nozzle_assignments to:
      - Sum FMS transactions per attendant (via nozzle → assignment)
      - Sum cash entries per attendant
      - Produce a per-attendant shortage/excess report

Per-attendant reconciliation example:
  Attendant RAMESH handled N1, N3 during S1
  FMS total for N1+N3 during S1 = ₹45,000
  Digital payments tagged to N1+N3 during S1 = ₹28,000
  Expected cash from RAMESH = ₹17,000
  Actual cash turned in by RAMESH = ₹16,500
  Shortage: ₹500 — flagged against RAMESH specifically

Constraints:
  • A nozzle can only have ONE active assignment at any point in time.
    "Active" means: shift_id matches AND relieved_at IS NULL.
    This is enforced by the partial unique index below.

Revision ID: 010
Revises: 009
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "010"
down_revision: str = "009"
branch_labels: tuple | None = None
depends_on: str | None = None


def upgrade() -> None:

    op.create_table(
        "nozzle_assignments",

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
            sa.ForeignKey("nozzles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attendant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # ── Assignment window ──────────────────────────────────────────
        # When the attendant claimed this nozzle (shift start or handover)
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # When the attendant was relieved from this nozzle.
        # NULL means this assignment is currently ACTIVE.
        sa.Column(
            "relieved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        # ── Who performed the assignment / relief ──────────────────────
        # user_id of the shift in-charge or manager who did the action
        sa.Column(
            "assigned_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "relieved_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),

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

    # ── Standard indexes ───────────────────────────────────────────────
    op.create_index(
        "ix_nozzle_assignments_shift_id",
        "nozzle_assignments",
        ["shift_id"],
    )
    op.create_index(
        "ix_nozzle_assignments_nozzle_id",
        "nozzle_assignments",
        ["nozzle_id"],
    )
    op.create_index(
        "ix_nozzle_assignments_attendant_id",
        "nozzle_assignments",
        ["attendant_id"],
    )

    # Composite index for the per-attendant reconciliation query:
    # SELECT nozzle_id WHERE shift_id = ? AND attendant_id = ?
    op.create_index(
        "ix_nozzle_assignments_shift_attendant",
        "nozzle_assignments",
        ["shift_id", "attendant_id"],
    )

    # ── Partial unique index — one active assignment per nozzle per shift ─
    # A nozzle can only be assigned to ONE attendant at a time within a shift.
    # "Active" = relieved_at IS NULL.
    # PostgreSQL partial unique indexes enforce this without blocking
    # historical (relieved) rows for the same nozzle+shift.
    op.execute("""
        CREATE UNIQUE INDEX uq_nozzle_assignments_active
        ON nozzle_assignments (shift_id, nozzle_id)
        WHERE relieved_at IS NULL
    """)


def downgrade() -> None:

    op.execute("DROP INDEX IF EXISTS uq_nozzle_assignments_active")

    op.drop_index(
        "ix_nozzle_assignments_shift_attendant",
        table_name="nozzle_assignments",
    )
    op.drop_index(
        "ix_nozzle_assignments_attendant_id",
        table_name="nozzle_assignments",
    )
    op.drop_index(
        "ix_nozzle_assignments_nozzle_id",
        table_name="nozzle_assignments",
    )
    op.drop_index(
        "ix_nozzle_assignments_shift_id",
        table_name="nozzle_assignments",
    )

    op.drop_table("nozzle_assignments")
