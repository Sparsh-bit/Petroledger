"""
001 — Initial PetroLedger Schema.

Creates all tables, enums, indexes, and unique constraints for the
PetroLedger multi-tenant petrol pump reconciliation platform.

Revision ID: 001
Revises: —
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "001"
down_revision: str | None = None
branch_labels: tuple | None = None
depends_on: str | None = None


# ── Enum types (PostgreSQL native) ─────────────────────────────────────

user_role = sa.Enum("owner", "admin", "manager", "worker", name="user_role")
fuel_type = sa.Enum("petrol", "diesel", "cng", name="fuel_type")
shift_status = sa.Enum("active", "completed", "reconciled", name="shift_status")
reconciliation_status = sa.Enum("pending", "completed", "flagged", name="reconciliation_status")


def upgrade() -> None:
    # ── 2. organizations ───────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_is_active", "organizations", ["is_active"])

    # ── 3. users ───────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_index("ix_users_role", "users", ["role"])

    # ── 4. pumps ───────────────────────────────────────────────────────
    op.create_table(
        "pumps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("nozzle_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pumps_org_id", "pumps", ["org_id"])
    op.create_index("ix_pumps_is_active", "pumps", ["is_active"])

    # ── 5. nozzles ─────────────────────────────────────────────────────
    op.create_table(
        "nozzles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pump_id", UUID(as_uuid=True), sa.ForeignKey("pumps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nozzle_number", sa.Integer(), nullable=False),
        sa.Column("fuel_type", fuel_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_nozzles_pump_id", "nozzles", ["pump_id"])

    # ── 6. workers ─────────────────────────────────────────────────────
    op.create_table(
        "workers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pump_id", UUID(as_uuid=True), sa.ForeignKey("pumps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_code", sa.String(50), nullable=False),
        sa.Column("joined_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_workers_user_id"),
        sa.UniqueConstraint("employee_code", name="uq_workers_employee_code"),
    )
    op.create_index("ix_workers_user_id", "workers", ["user_id"])
    op.create_index("ix_workers_pump_id", "workers", ["pump_id"])
    op.create_index("ix_workers_employee_code", "workers", ["employee_code"])

    # ── 7. shifts ──────────────────────────────────────────────────────
    op.create_table(
        "shifts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pump_id", UUID(as_uuid=True), sa.ForeignKey("pumps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", shift_status, nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_shifts_pump_id", "shifts", ["pump_id"])
    op.create_index("ix_shifts_worker_id", "shifts", ["worker_id"])
    op.create_index("ix_shifts_status", "shifts", ["status"])

    # ── 8. upi_transactions ────────────────────────────────────────────
    op.create_table(
        "upi_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("upi_ref", sa.String(100), nullable=False),
        sa.Column("bank", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_upi_transactions_shift_id", "upi_transactions", ["shift_id"])
    op.create_index("ix_upi_transactions_upi_ref", "upi_transactions", ["upi_ref"])

    # ── 9. pos_transactions ────────────────────────────────────────────
    op.create_table(
        "pos_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("terminal_id", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pos_transactions_shift_id", "pos_transactions", ["shift_id"])
    op.create_index("ix_pos_transactions_terminal_id", "pos_transactions", ["terminal_id"])

    # ── 10. pump_logs ──────────────────────────────────────────────────
    op.create_table(
        "pump_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nozzle_id", UUID(as_uuid=True), sa.ForeignKey("nozzles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_reading", sa.Numeric(12, 2), nullable=False),
        sa.Column("end_reading", sa.Numeric(12, 2), nullable=False),
        sa.Column("volume_dispensed", sa.Numeric(12, 2), nullable=False),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pump_logs_shift_id", "pump_logs", ["shift_id"])
    op.create_index("ix_pump_logs_nozzle_id", "pump_logs", ["nozzle_id"])

    # ── 11. reconciliation_results ─────────────────────────────────────
    op.create_table(
        "reconciliation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("variance", sa.Numeric(12, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", reconciliation_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("anomalies", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shift_id", name="uq_reconciliation_results_shift_id"),
    )
    op.create_index("ix_reconciliation_results_shift_id", "reconciliation_results", ["shift_id"], unique=True)
    op.create_index("ix_reconciliation_results_status", "reconciliation_results", ["status"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("reconciliation_results")
    op.drop_table("pump_logs")
    op.drop_table("pos_transactions")
    op.drop_table("upi_transactions")
    op.drop_table("shifts")
    op.drop_table("workers")
    op.drop_table("nozzles")
    op.drop_table("pumps")
    op.drop_table("users")
    op.drop_table("organizations")

    # Drop enums
    reconciliation_status.drop(op.get_bind(), checkfirst=True)
    shift_status.drop(op.get_bind(), checkfirst=True)
    fuel_type.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
