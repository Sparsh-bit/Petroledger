"""
011 — Create anomaly_flags table.

anomaly_flags stores persistent, queryable anomaly records detected
during or after reconciliation.  This replaces the current approach of
storing anomalies as a JSON blob inside reconciliation_results.anomalies.

Why a separate table instead of JSON:
  • Anomalies need to be queried individually (e.g. "show all unresolved
    HIGH severity flags for site X this week")
  • Anomalies need to be resolved with a reason and timestamp
  • Anomalies need to be linked to specific attendants for accountability
  • A JSON blob cannot be indexed, filtered, or resolved individually

Anomaly types (from PRD section 13):
  CASH_SHORTAGE         — expected cash > actual cash turned in
  CASH_EXCESS           — actual cash > expected cash
  FMS_DIP_MISMATCH      — physical tank stock doesn't match FMS dispensed
  REVENUE_BELOW_TREND   — daily total >15% below 30-day average
  UNUSUAL_VOID_RATE     — voids >2% of transactions
  SAME_AMOUNT_REPEAT    — possible test/fraud transactions
  LATE_SHIFT_CLOSE      — shift not closed within 30 min of scheduled end
  BATCH_NOT_SETTLED     — POS batch not submitted by 11 PM
  UNMATCHED_UPI         — UPI received but no matching FMS transaction
  ZERO_DIGITAL_PAYMENTS — fuel dispensed but no UPI/POS/fleet recorded
  WORKER_HISTORY        — attendant has pattern of flagged shifts

Revision ID: 011
Revises: 010
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "011"
down_revision: str = "010"
branch_labels: tuple | None = None
depends_on: str | None = None


# ── New enum types ─────────────────────────────────────────────────────

anomaly_severity = sa.Enum(
    "LOW",
    "MEDIUM",
    "HIGH",
    name="anomaly_severity",
)

anomaly_flag_type = sa.Enum(
    "CASH_SHORTAGE",
    "CASH_EXCESS",
    "FMS_DIP_MISMATCH",
    "REVENUE_BELOW_TREND",
    "UNUSUAL_VOID_RATE",
    "SAME_AMOUNT_REPEAT",
    "LATE_SHIFT_CLOSE",
    "BATCH_NOT_SETTLED",
    "UNMATCHED_UPI",
    "ZERO_DIGITAL_PAYMENTS",
    "WORKER_HISTORY",
    "OTHER",
    name="anomaly_flag_type",
)


def upgrade() -> None:

    # ── 2. Create anomaly_flags ────────────────────────────────────────
    op.create_table(
        "anomaly_flags",

        # ── Primary key ────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),

        # ── Scope — what does this anomaly belong to ───────────────────
        sa.Column(
            "site_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # nullable: some anomalies are site-level, not shift-level
        # (e.g. REVENUE_BELOW_TREND spans multiple shifts)
        sa.Column(
            "shift_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # nullable: not all anomalies are attributable to a specific attendant
        sa.Column(
            "attendant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workers.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # ── Anomaly details ────────────────────────────────────────────
        sa.Column("flag_type", anomaly_flag_type, nullable=False),
        sa.Column("severity", anomaly_severity, nullable=False),
        # Human-readable description of why this was flagged
        sa.Column("description", sa.Text(), nullable=False),
        # Optional monetary amount involved (e.g. shortage of ₹500)
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),

        # ── Resolution ─────────────────────────────────────────────────
        sa.Column(
            "is_resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "resolved_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Owner/manager writes the reason when marking as resolved
        sa.Column("resolution_note", sa.Text(), nullable=True),

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

    # ── 3. Indexes ─────────────────────────────────────────────────────
    op.create_index(
        "ix_anomaly_flags_site_id",
        "anomaly_flags",
        ["site_id"],
    )
    op.create_index(
        "ix_anomaly_flags_shift_id",
        "anomaly_flags",
        ["shift_id"],
    )
    op.create_index(
        "ix_anomaly_flags_attendant_id",
        "anomaly_flags",
        ["attendant_id"],
    )
    op.create_index(
        "ix_anomaly_flags_flag_type",
        "anomaly_flags",
        ["flag_type"],
    )
    op.create_index(
        "ix_anomaly_flags_severity",
        "anomaly_flags",
        ["severity"],
    )
    op.create_index(
        "ix_anomaly_flags_is_resolved",
        "anomaly_flags",
        ["is_resolved"],
    )
    op.create_index(
        "ix_anomaly_flags_created_at",
        "anomaly_flags",
        ["created_at"],
    )

    # Composite index for the dashboard query:
    # "Show all unresolved flags for site X ordered by severity"
    op.create_index(
        "ix_anomaly_flags_site_resolved_severity",
        "anomaly_flags",
        ["site_id", "is_resolved", "severity"],
    )

    # Composite index for the shift detail query:
    # "Show all flags for this shift"
    op.create_index(
        "ix_anomaly_flags_shift_resolved",
        "anomaly_flags",
        ["shift_id", "is_resolved"],
    )


def downgrade() -> None:

    # ── 3. Drop indexes ────────────────────────────────────────────────
    op.drop_index("ix_anomaly_flags_shift_resolved",        table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_site_resolved_severity", table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_created_at",            table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_is_resolved",           table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_severity",              table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_flag_type",             table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_attendant_id",          table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_shift_id",              table_name="anomaly_flags")
    op.drop_index("ix_anomaly_flags_site_id",               table_name="anomaly_flags")

    # ── 2. Drop table ──────────────────────────────────────────────────
    op.drop_table("anomaly_flags")

    # ── 1. Drop enums ──────────────────────────────────────────────────
    anomaly_flag_type.drop(op.get_bind(), checkfirst=True)
    anomaly_severity.drop(op.get_bind(), checkfirst=True)
