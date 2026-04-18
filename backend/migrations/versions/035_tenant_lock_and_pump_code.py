"""tenant lock + subscription fields + pump code

Revision ID: 035
Revises: 034
Create Date: 2026-04-18

Adds tenant lock/subscription fields for the provider portal, and a
unique `code` field on pumps to support pump-code based login.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: str = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tenant — provider-portal management fields
    op.add_column(
        "tenants",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "subscription_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "monthly_price_inr",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Pump — public-facing code for login and signage.
    op.add_column("pumps", sa.Column("code", sa.String(length=32), nullable=True))
    op.create_unique_constraint("uq_pumps_code", "pumps", ["code"])
    op.create_index("ix_pumps_code", "pumps", ["code"])


def downgrade() -> None:
    op.drop_index("ix_pumps_code", table_name="pumps")
    op.drop_constraint("uq_pumps_code", "pumps", type_="unique")
    op.drop_column("pumps", "code")
    op.drop_column("tenants", "monthly_price_inr")
    op.drop_column("tenants", "subscription_expires_at")
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "is_locked")
