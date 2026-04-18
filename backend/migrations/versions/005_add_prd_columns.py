"""
005 — Add missing FuelRecon PRD columns to existing tables.

Adds all columns required by the FuelRecon PRD v1.0 that are absent
from the initial schema (migrations 001–004).  Every new column is
nullable so existing rows are unaffected.

Tables modified:
  • organizations  — address, dealer_name, dealer_phone, omc_type, site_code, gstin
  • nozzles        — product_code, product_name, is_active
  • shifts         — shift_number, shift_date, signed_off_by, signed_off_at
                     + adds 'locked' value to shift_status enum
  • upi_transactions      — payer_upi, match_status
  • reconciliation_results — fms_total, upi_total, card_total, fleet_total,
                             variance_type, computed_at

Note: upi_transactions.matched_fms_txn_id (FK → fms_transactions) is added
in migration 006 after the fms_transactions table exists.

Revision ID: 005
Revises: 004
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ── Alembic metadata ───────────────────────────────────────────────────

revision: str = "005"
down_revision: str = "004"
branch_labels: tuple | None = None
depends_on: str | None = None


# ── New enum type definitions ──────────────────────────────────────────
# Using descriptive type names to avoid clashing with column names or
# existing PostgreSQL enums (user_role, fuel_type, shift_status,
# reconciliation_status).

omc_type = sa.Enum("BPCL", "IOCL", "HPCL", name="omc_type")
fuel_product_code = sa.Enum("MS", "HSD", "SPD97", "CNG", name="fuel_product_code")
shift_slot = sa.Enum("S1", "S2", "S3", name="shift_slot")
upi_match_status = sa.Enum("MATCHED", "UNMATCHED", "MANUAL", name="upi_match_status")
recon_variance_type = sa.Enum("MATCH", "SHORTAGE", "EXCESS", name="recon_variance_type")


def upgrade() -> None:

    # ── 1. Create new PostgreSQL enum types ───────────────────────────
    omc_type.create(op.get_bind(), checkfirst=True)
    fuel_product_code.create(op.get_bind(), checkfirst=True)
    shift_slot.create(op.get_bind(), checkfirst=True)
    upi_match_status.create(op.get_bind(), checkfirst=True)
    recon_variance_type.create(op.get_bind(), checkfirst=True)

    # Add 'locked' to the existing shift_status enum.
    # PostgreSQL supports ADD VALUE IF NOT EXISTS since v9.3.
    op.execute("ALTER TYPE shift_status ADD VALUE IF NOT EXISTS 'locked'")

    # ── 2. organizations — site-level fields ──────────────────────────
    op.add_column(
        "organizations",
        sa.Column("address", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("dealer_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("dealer_phone", sa.String(20), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("omc_type", omc_type, nullable=True),
    )
    op.add_column(
        "organizations",
        # Unique pump-station code assigned by OMC (e.g. BPCL dealer code)
        sa.Column("site_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "organizations",
        # GST Identification Number — 15 chars per Indian GST format
        sa.Column("gstin", sa.String(15), nullable=True),
    )
    op.create_index("ix_organizations_site_code", "organizations", ["site_code"])

    # ── 3. nozzles — Indian fuel product codes + active flag ──────────
    op.add_column(
        "nozzles",
        # Indian OMC product codes: MS=petrol, HSD=diesel, SPD97=speed97, CNG
        sa.Column("product_code", fuel_product_code, nullable=True),
    )
    op.add_column(
        "nozzles",
        sa.Column("product_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "nozzles",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index("ix_nozzles_is_active", "nozzles", ["is_active"])

    # ── 4. shifts — shift slot, date, and sign-off fields ─────────────
    op.add_column(
        "shifts",
        # S1=06:00–14:00, S2=14:00–22:00, S3=22:00–06:00 (spans midnight)
        sa.Column("shift_number", shift_slot, nullable=True),
    )
    op.add_column(
        "shifts",
        # Calendar date of shift start (Shift 3 ends on start_date+1)
        sa.Column("shift_date", sa.Date(), nullable=True),
    )
    # signed_off_by: add column first, then add FK constraint separately
    # (Alembic best practice for adding FK columns to existing tables)
    op.add_column(
        "shifts",
        sa.Column("signed_off_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shifts_signed_off_by_users",
        "shifts",
        "users",
        ["signed_off_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "shifts",
        sa.Column("signed_off_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shifts_shift_date", "shifts", ["shift_date"])
    op.create_index("ix_shifts_shift_number", "shifts", ["shift_number"])

    # ── 5. upi_transactions — UPI-specific matching fields ────────────
    op.add_column(
        "upi_transactions",
        # VPA of the payer (customer's UPI ID)
        sa.Column("payer_upi", sa.String(100), nullable=True),
    )
    op.add_column(
        "upi_transactions",
        sa.Column("match_status", upi_match_status, nullable=True),
    )
    # Note: matched_fms_txn_id (FK → fms_transactions) is added in
    # migration 006 after fms_transactions is created.

    # ── 6. reconciliation_results — full formula breakdown ────────────
    # All financial columns use Numeric(12,2) — NEVER float.
    op.add_column(
        "reconciliation_results",
        sa.Column("fms_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("upi_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("card_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("fleet_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("variance_type", recon_variance_type, nullable=True),
    )
    op.add_column(
        "reconciliation_results",
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:

    # ── 6. reconciliation_results ──────────────────────────────────────
    op.drop_column("reconciliation_results", "computed_at")
    op.drop_column("reconciliation_results", "variance_type")
    op.drop_column("reconciliation_results", "fleet_total")
    op.drop_column("reconciliation_results", "card_total")
    op.drop_column("reconciliation_results", "upi_total")
    op.drop_column("reconciliation_results", "fms_total")

    # ── 5. upi_transactions ────────────────────────────────────────────
    op.drop_column("upi_transactions", "match_status")
    op.drop_column("upi_transactions", "payer_upi")

    # ── 4. shifts ──────────────────────────────────────────────────────
    op.drop_index("ix_shifts_shift_number", table_name="shifts")
    op.drop_index("ix_shifts_shift_date", table_name="shifts")
    op.drop_column("shifts", "signed_off_at")
    op.drop_constraint(
        "fk_shifts_signed_off_by_users", "shifts", type_="foreignkey"
    )
    op.drop_column("shifts", "signed_off_by")
    op.drop_column("shifts", "shift_date")
    op.drop_column("shifts", "shift_number")

    # ── 3. nozzles ─────────────────────────────────────────────────────
    op.drop_index("ix_nozzles_is_active", table_name="nozzles")
    op.drop_column("nozzles", "is_active")
    op.drop_column("nozzles", "product_name")
    op.drop_column("nozzles", "product_code")

    # ── 2. organizations ───────────────────────────────────────────────
    op.drop_index("ix_organizations_site_code", table_name="organizations")
    op.drop_column("organizations", "gstin")
    op.drop_column("organizations", "site_code")
    op.drop_column("organizations", "omc_type")
    op.drop_column("organizations", "dealer_phone")
    op.drop_column("organizations", "dealer_name")
    op.drop_column("organizations", "address")

    # ── 1. Drop new enum types ─────────────────────────────────────────
    # NOTE: The 'locked' value added to shift_status CANNOT be removed in
    # PostgreSQL without recreating the enum type entirely. This is a known
    # PostgreSQL limitation. The downgrade leaves 'locked' in shift_status.
    recon_variance_type.drop(op.get_bind(), checkfirst=True)
    upi_match_status.drop(op.get_bind(), checkfirst=True)
    shift_slot.drop(op.get_bind(), checkfirst=True)
    fuel_product_code.drop(op.get_bind(), checkfirst=True)
    omc_type.drop(op.get_bind(), checkfirst=True)
