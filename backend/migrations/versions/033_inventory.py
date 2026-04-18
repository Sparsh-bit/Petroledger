"""inventory

Revision ID: 033
Revises: 032
Create Date: 2026-04-18

Creates `fuel_tanks`, `dip_readings`, `fuel_deliveries`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "033"
down_revision: str = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── fuel_tanks ──────────────────────────────────────────────────────
    op.create_table(
        "fuel_tanks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("tank_number", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("capacity_litres", sa.Numeric(14, 3), nullable=False),
        sa.Column("current_level_litres", sa.Numeric(14, 3), nullable=False,
                  server_default="0"),
        sa.Column("low_level_threshold", sa.Numeric(14, 3), nullable=False,
                  server_default="0"),
        sa.Column("last_dip_reading_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_fuel_tanks_org_tank", "fuel_tanks", ["org_id", "tank_number"]
    )
    op.create_index("ix_fuel_tanks_org_id", "fuel_tanks", ["org_id"])
    op.create_index("ix_fuel_tanks_tenant_id", "fuel_tanks", ["tenant_id"])

    # ── dip_readings ────────────────────────────────────────────────────
    op.create_table(
        "dip_readings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("tank_id", UUID(as_uuid=True),
                  sa.ForeignKey("fuel_tanks.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("reading_date", sa.Date(), nullable=False),
        sa.Column("reading_litres", sa.Numeric(14, 3), nullable=False),
        sa.Column("temperature_celsius", sa.Numeric(5, 2), nullable=True),
        sa.Column("recorded_by_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dip_readings_tank_id", "dip_readings", ["tank_id"])
    op.create_index("ix_dip_readings_reading_date", "dip_readings", ["reading_date"])

    # ── fuel_deliveries ─────────────────────────────────────────────────
    op.create_table(
        "fuel_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("tank_id", UUID(as_uuid=True),
                  sa.ForeignKey("fuel_tanks.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supplier_name", sa.String(255), nullable=False),
        sa.Column("challan_number", sa.String(100), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("vehicle_number", sa.String(50), nullable=True),
        sa.Column("volume_ordered_litres", sa.Numeric(14, 3), nullable=False),
        sa.Column("volume_received_litres", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost_per_litre", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fuel_deliveries_tank_id", "fuel_deliveries", ["tank_id"])
    op.create_index("ix_fuel_deliveries_delivery_date", "fuel_deliveries",
                    ["delivery_date"])
    op.create_unique_constraint(
        "uq_fuel_deliveries_org_challan", "fuel_deliveries",
        ["org_id", "challan_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_fuel_deliveries_org_challan", "fuel_deliveries",
                       type_="unique")
    op.drop_index("ix_fuel_deliveries_delivery_date", table_name="fuel_deliveries")
    op.drop_index("ix_fuel_deliveries_tank_id", table_name="fuel_deliveries")
    op.drop_table("fuel_deliveries")
    op.drop_index("ix_dip_readings_reading_date", table_name="dip_readings")
    op.drop_index("ix_dip_readings_tank_id", table_name="dip_readings")
    op.drop_table("dip_readings")
    op.drop_index("ix_fuel_tanks_tenant_id", table_name="fuel_tanks")
    op.drop_index("ix_fuel_tanks_org_id", table_name="fuel_tanks")
    op.drop_constraint("uq_fuel_tanks_org_tank", "fuel_tanks", type_="unique")
    op.drop_table("fuel_tanks")
