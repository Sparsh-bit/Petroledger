"""user_reset_token

Revision ID: 022
Revises: 021
Create Date: 2026-04-18

Adds password-reset columns to users and a `tokens_invalidated_at`
timestamp so that on reset/logout-all we can globally reject all JWTs
issued before the mark without maintaining a per-token blacklist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reset_token_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "reset_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "tokens_invalidated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "tokens_invalidated_at")
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
