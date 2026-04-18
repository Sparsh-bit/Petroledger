"""add_nozzle_meter_readings_and_shift_sales

Revision ID: 015
Revises: 014
Create Date: 2026-03-31

Adds:
  - nozzle_meter_readings  — immutable ETOT receipt audit trail (one row per
                             shift + nozzle + reading_type)
  - nozzle_shift_sales     — derived shift sale per nozzle (computed from
                             opening/closing readings)
  - reconciliation_results.reconciliation_type — tag to distinguish
                             'standard' (FMS-based) vs 'per_worker' (meter-based)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. nozzle_meter_readings ──────────────────────────────────────────

    op.create_table(
        "nozzle_meter_readings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("shift_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nozzle_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("reading_type", sa.String(10), nullable=False),
        sa.Column("amount_cumulative", sa.Numeric(15, 3), nullable=False),
        sa.Column("volume_cumulative", sa.Numeric(15, 3), nullable=False),
        sa.Column("tot_sales_cumulative", sa.Integer(), nullable=False),
        sa.Column("receipt_image_url", sa.Text(), nullable=True),
        sa.Column("entered_manually", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["nozzle_id"], ["nozzles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "reading_type IN ('opening', 'closing')",
            name="ck_nozzle_meter_readings_reading_type",
        ),
        sa.UniqueConstraint(
            "shift_id", "nozzle_id", "reading_type",
            name="uq_nozzle_meter_readings_shift_nozzle_type",
        ),
    )
    op.create_index(
        "idx_nozzle_meter_readings_shift",
        "nozzle_meter_readings", ["shift_id"]
    )
    op.create_index(
        "idx_nozzle_meter_readings_tenant",
        "nozzle_meter_readings", ["tenant_id"]
    )
    op.create_index(
        "idx_nozzle_meter_readings_nozzle",
        "nozzle_meter_readings", ["nozzle_id"]
    )

    # ── 2. nozzle_shift_sales ─────────────────────────────────────────────

    op.create_table(
        "nozzle_shift_sales",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("shift_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nozzle_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("opening_amount", sa.Numeric(15, 3), nullable=False),
        sa.Column("closing_amount", sa.Numeric(15, 3), nullable=False),
        sa.Column("shift_sale_amount", sa.Numeric(15, 3), nullable=False),
        sa.Column("opening_volume", sa.Numeric(15, 3), nullable=False),
        sa.Column("closing_volume", sa.Numeric(15, 3), nullable=False),
        sa.Column("shift_sale_volume", sa.Numeric(15, 3), nullable=False),
        sa.Column("opening_tot_sales", sa.Integer(), nullable=False),
        sa.Column("closing_tot_sales", sa.Integer(), nullable=False),
        sa.Column("shift_transaction_count", sa.Integer(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["nozzle_id"], ["nozzles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "shift_id", "nozzle_id",
            name="uq_nozzle_shift_sales_shift_nozzle",
        ),
    )
    op.create_index(
        "idx_nozzle_shift_sales_shift",
        "nozzle_shift_sales", ["shift_id"]
    )
    op.create_index(
        "idx_nozzle_shift_sales_tenant",
        "nozzle_shift_sales", ["tenant_id"]
    )

    # ── 3. reconciliation_results — add reconciliation_type column ────────

    op.add_column(
        "reconciliation_results",
        sa.Column(
            "reconciliation_type",
            sa.String(20),
            nullable=False,
            server_default="standard",
        ),
    )


def downgrade() -> None:
    op.drop_column("reconciliation_results", "reconciliation_type")

    op.drop_index("idx_nozzle_shift_sales_tenant", table_name="nozzle_shift_sales")
    op.drop_index("idx_nozzle_shift_sales_shift", table_name="nozzle_shift_sales")
    op.drop_table("nozzle_shift_sales")

    op.drop_index("idx_nozzle_meter_readings_nozzle", table_name="nozzle_meter_readings")
    op.drop_index("idx_nozzle_meter_readings_tenant", table_name="nozzle_meter_readings")
    op.drop_index("idx_nozzle_meter_readings_shift", table_name="nozzle_meter_readings")
    op.drop_table("nozzle_meter_readings")
