"""daily_consolidation

Revision ID: 028
Revises: 026
Create Date: 2026-04-18

Creates `daily_consolidations` — one row per (org, day) rolling up
the 3-shift reconciliation results into a day-level summary.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "028"
down_revision: str = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_consolidations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_fms_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_upi_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_card_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_fleet_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_cash_collected", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_variance", sa.Numeric(14, 2), nullable=False),
        sa.Column("s1_shift_id", UUID(as_uuid=True),
                  sa.ForeignKey("shifts.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("s2_shift_id", UUID(as_uuid=True),
                  sa.ForeignKey("shifts.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("s3_shift_id", UUID(as_uuid=True),
                  sa.ForeignKey("shifts.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("anomaly_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("confidence_avg", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="PARTIAL"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_daily_consolidations_org_date",
        "daily_consolidations",
        ["org_id", "date"],
    )
    op.create_index(
        "ix_daily_consolidations_tenant_id",
        "daily_consolidations", ["tenant_id"],
    )
    op.create_index(
        "ix_daily_consolidations_org_id",
        "daily_consolidations", ["org_id"],
    )
    op.create_index(
        "ix_daily_consolidations_date",
        "daily_consolidations", ["date"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_consolidations_date", table_name="daily_consolidations")
    op.drop_index("ix_daily_consolidations_org_id", table_name="daily_consolidations")
    op.drop_index("ix_daily_consolidations_tenant_id", table_name="daily_consolidations")
    op.drop_constraint(
        "uq_daily_consolidations_org_date",
        "daily_consolidations",
        type_="unique",
    )
    op.drop_table("daily_consolidations")
