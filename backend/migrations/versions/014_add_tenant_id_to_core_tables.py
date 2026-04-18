"""
014 — Add tenant_id to organizations, users, and audit_logs.

Strategy per table:
  1. Add column as nullable
  2. Backfill existing rows to a known default tenant
  3. Make column NOT NULL and add FK + index

The default tenant (00000000-0000-0000-0000-000000000001) is created
first so the backfill has a valid FK target.  All pre-existing test
data ends up in this tenant and can be reassigned or kept for testing.

Tables NOT modified (inherit tenant context through FK chains):
  pumps, nozzles, workers, shifts, fms_transactions,
  pos_batch_settlements, fleet_transactions, cash_entries,
  nozzle_assignments, reconciliation_results, anomaly_flags,
  upi_transactions, pos_transactions, pump_logs

Revision ID: 014
Revises: 013
Create Date: 2026-03-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "014"
down_revision: str = "013"
branch_labels: tuple | None = None
depends_on: str | None = None

# Well-known UUID for the system default tenant created during this migration.
# Chosen to be clearly synthetic / easy to grep for in logs.
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ── 0. Create default tenant for existing rows ────────────────────────
    # Insert with ON CONFLICT so re-running a failed migration is safe.
    op.execute(f"""
        INSERT INTO tenants (
            id, name, owner_name, owner_phone, owner_email,
            subscription_plan, max_orgs
        ) VALUES (
            '{_DEFAULT_TENANT_ID}',
            'Default Tenant (Migration)',
            'System',
            '0000000000',
            'system@default.tenant',
            'ENTERPRISE',
            999
        )
        ON CONFLICT (owner_email) DO NOTHING;
    """)

    # ── 1. organizations ──────────────────────────────────────────────────
    op.add_column(
        "organizations",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(f"""
        UPDATE organizations
        SET tenant_id = '{_DEFAULT_TENANT_ID}'
        WHERE tenant_id IS NULL;
    """)
    op.alter_column("organizations", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_organizations_tenant_id",
        "organizations", "tenants",
        ["tenant_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_organizations_tenant_id", "organizations", ["tenant_id"])

    # ── 2. users ──────────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(f"""
        UPDATE users
        SET tenant_id = '{_DEFAULT_TENANT_ID}'
        WHERE tenant_id IS NULL;
    """)
    op.alter_column("users", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_users_tenant_id",
        "users", "tenants",
        ["tenant_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])

    # ── 3. audit_logs ─────────────────────────────────────────────────────
    # audit_logs has no updated_at and is intentionally immutable, so we
    # add tenant_id for scoped querying without altering the insert path yet.
    op.add_column(
        "audit_logs",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(f"""
        UPDATE audit_logs
        SET tenant_id = '{_DEFAULT_TENANT_ID}'
        WHERE tenant_id IS NULL;
    """)
    op.alter_column("audit_logs", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_audit_logs_tenant_id",
        "audit_logs", "tenants",
        ["tenant_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_audit_logs_tenant_id", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    # Remove in reverse order

    # ── 3. audit_logs ─────────────────────────────────────────────────────
    op.drop_index("idx_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_tenant_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "tenant_id")

    # ── 2. users ──────────────────────────────────────────────────────────
    op.drop_index("idx_users_tenant_id", table_name="users")
    op.drop_constraint("fk_users_tenant_id", "users", type_="foreignkey")
    op.drop_column("users", "tenant_id")

    # ── 1. organizations ──────────────────────────────────────────────────
    op.drop_index("idx_organizations_tenant_id", table_name="organizations")
    op.drop_constraint("fk_organizations_tenant_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "tenant_id")

    # ── 0. Remove default tenant ──────────────────────────────────────────
    op.execute(f"""
        DELETE FROM tenants WHERE id = '{_DEFAULT_TENANT_ID}';
    """)
