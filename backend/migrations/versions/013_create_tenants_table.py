"""
013 — Create tenants table for multi-tenant architecture.

A tenant represents a dealer/business entity (the billing unit).
One tenant can own multiple physical petrol pump locations (organizations).

Subscription plans:
  BASIC      — max_orgs = 1  (single pump, most Indian dealers)
  PRO        — max_orgs = 5  (small chains)
  ENTERPRISE — max_orgs = 999 (effectively unlimited)

NOTE: This migration ONLY creates the tenants table.
Phase 2 will add tenant_id FK columns to existing tables.

Revision ID: 013
Revises: 012
Create Date: 2026-03-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "013"
down_revision: str = "012"
branch_labels: tuple | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_name", sa.String(255), nullable=False),
        sa.Column("owner_phone", sa.String(15), nullable=False),
        sa.Column("owner_email", sa.String(255), nullable=False),
        sa.Column(
            "subscription_plan",
            sa.String(20),
            server_default="BASIC",
            nullable=False,
        ),
        sa.Column(
            "max_orgs",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_email", name="uq_tenants_owner_email"),
    )

    op.create_index("idx_tenants_owner_email", "tenants", ["owner_email"])
    op.create_index("idx_tenants_is_active", "tenants", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_tenants_is_active", table_name="tenants")
    op.drop_index("idx_tenants_owner_email", table_name="tenants")
    op.drop_table("tenants")
