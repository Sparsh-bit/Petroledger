"""Add full_name to users table

Revision ID: 041
Revises: 040
Create Date: 2026-06-08
"""

import sqlalchemy as sa
from alembic import op


revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")
