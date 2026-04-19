"""contact submissions table

Revision ID: 036
Revises: 035
Create Date: 2026-04-18

Adds a public contact_submissions table for the marketing-site
contact form.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: str = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_submissions",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
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
    op.create_index(
        "ix_contact_submissions_email",
        "contact_submissions",
        ["email"],
    )
    op.create_index(
        "ix_contact_submissions_created_at",
        "contact_submissions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_submissions_created_at", table_name="contact_submissions")
    op.drop_index("ix_contact_submissions_email", table_name="contact_submissions")
    op.drop_table("contact_submissions")
