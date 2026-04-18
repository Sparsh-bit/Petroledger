"""fms_transaction_subtype

Revision ID: 032
Revises: 030
Create Date: 2026-04-18

Adds `subtype` to `fms_transactions` (SALE / PUMP_TEST / CALIBRATION /
SPILLAGE / TANK_TRANSFER). Non-SALE subtypes record operational fuel
movements and are excluded from cash reconciliation.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: str = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fms_transactions",
        sa.Column(
            "subtype",
            sa.String(length=20),
            nullable=False,
            server_default="SALE",
        ),
    )
    op.create_index(
        "ix_fms_transactions_subtype", "fms_transactions", ["subtype"]
    )


def downgrade() -> None:
    op.drop_index("ix_fms_transactions_subtype", table_name="fms_transactions")
    op.drop_column("fms_transactions", "subtype")
