"""Add tenant_features, tenant_feature_overrides, tenant_payment_configs tables

Revision ID: 038
Revises: 037
Create Date: 2026-04-19

Adds the feature-access control system and payment-gateway config for the
provider portal. Features are seeded once from the canonical list below;
per-tenant overrides and payment configs are empty on first run.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: str = "037"
branch_labels = None
depends_on = None

# (key, name, module, is_core, included_in_plans)
_FEATURES: list[tuple[str, str, str, bool, str]] = [
    ("shift_management",   "Shift Management",       "core",       True,  "BASIC,PRO,ENTERPRISE"),
    ("pump_management",    "Pump Management",         "core",       True,  "BASIC,PRO,ENTERPRISE"),
    ("basic_reports",      "Basic Reports",           "core",       True,  "BASIC,PRO,ENTERPRISE"),
    ("cash_management",    "Cash Entry Management",   "operations", False, "BASIC,PRO,ENTERPRISE"),
    ("advanced_reports",   "Advanced Analytics",      "analytics",  False, "PRO,ENTERPRISE"),
    ("fleet_management",   "Fleet Management",        "fleet",      False, "PRO,ENTERPRISE"),
    ("inventory_tracking", "Inventory Management",    "inventory",  False, "PRO,ENTERPRISE"),
    ("audit_log",          "Audit Logs",              "compliance", False, "PRO,ENTERPRISE"),
    ("reconciliation",     "Daily Reconciliation",    "compliance", False, "PRO,ENTERPRISE"),
    ("variance_analysis",  "Variance Analysis",       "compliance", False, "PRO,ENTERPRISE"),
    ("multi_org",          "Multiple Organisations",  "operations", False, "ENTERPRISE"),
    ("api_access",         "API / Webhook Access",    "advanced",   False, "ENTERPRISE"),
    ("sms_alerts",         "SMS Notifications",       "advanced",   False, "ENTERPRISE"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("tenant_features") and inspector.has_table(
        "tenant_feature_overrides"
    ) and inspector.has_table("tenant_payment_configs"):
        # Already applied — skip table creation and seed.
        return

    op.create_table(
        "tenant_features",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("is_core", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("included_in_plans", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tenant_feature_overrides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Uuid,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            sa.Integer,
            sa.ForeignKey("tenant_features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "feature_id", name="uq_tenant_feature_override"),
    )

    op.create_table(
        "tenant_payment_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Uuid,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("gateway", sa.String(32), nullable=False, server_default="razorpay"),
        sa.Column("key_id", sa.String(255), nullable=True),
        sa.Column("key_secret", sa.String(512), nullable=True),
        sa.Column("webhook_secret", sa.String(512), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed the canonical feature list.
    features_tbl = sa.table(
        "tenant_features",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
        sa.column("is_core", sa.Boolean),
        sa.column("included_in_plans", sa.String),
    )
    op.bulk_insert(
        features_tbl,
        [
            {
                "key": key,
                "name": name,
                "module": module,
                "is_core": is_core,
                "included_in_plans": plans,
            }
            for key, name, module, is_core, plans in _FEATURES
        ],
    )


def downgrade() -> None:
    op.drop_table("tenant_payment_configs")
    op.drop_table("tenant_feature_overrides")
    op.drop_table("tenant_features")
