"""user_oauth_fields

Revision ID: 020
Revises: 019
Create Date: 2026-04-18

Adds Google OAuth fields to users:
- `auth_provider` — "local" | "google" (default "local")
- `google_id` — the Google `sub` claim, nullable, unique when non-null
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: str = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=20),
            nullable=False,
            server_default="local",
        ),
    )
    op.add_column(
        "users",
        sa.Column("google_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.create_index("ix_users_auth_provider", "users", ["auth_provider"])


def downgrade() -> None:
    op.drop_index("ix_users_auth_provider", table_name="users")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")
    op.drop_column("users", "auth_provider")
