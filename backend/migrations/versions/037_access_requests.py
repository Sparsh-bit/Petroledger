"""access requests table

Revision ID: 037
Revises: 036
Create Date: 2026-04-18

Adds access_requests table for public ERP access-request submissions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: str = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Idempotent: tolerate a leftover enum type from a partial prior run.
    sa.Enum(
        "NEW",
        "CONTACTED",
        "APPROVED",
        "REJECTED",
        name="access_request_status",
    ).create(bind, checkfirst=True)

    if inspector.has_table("access_requests"):
        # Table already present from a prior partial/manual run — nothing left to do.
        return

    status_enum = sa.Enum(
        "NEW",
        "CONTACTED",
        "APPROVED",
        "REJECTED",
        name="access_request_status",
        create_type=False,
    )

    op.create_table(
        "access_requests",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("pump_count_range", sa.String(length=32), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("provider_notes", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_access_requests_email", "access_requests", ["email"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])
    op.create_index(
        "ix_access_requests_created_at", "access_requests", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_access_requests_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_status", table_name="access_requests")
    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")
    sa.Enum(name="access_request_status").drop(op.get_bind(), checkfirst=True)
