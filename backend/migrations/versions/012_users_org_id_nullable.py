"""
012 — Make users.org_id nullable for owner self-registration.

Owners register without an organisation. org_id is set later when
they create their first pump/organisation.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "org_id",
        existing_type=sa.UUID(),
        nullable=True,
        existing_nullable=False,
    )
    # Update FK to SET NULL on org delete (drop old FK, add new one)
    op.drop_constraint("users_org_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_org_id_fkey",
        "users",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("users_org_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_org_id_fkey",
        "users",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "users",
        "org_id",
        existing_type=sa.UUID(),
        nullable=False,
        existing_nullable=True,
    )
