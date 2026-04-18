"""user_otp_fields

Revision ID: 021
Revises: 020
Create Date: 2026-04-18

Adds SMS-OTP columns to users:
- `phone_number` — E.164-formatted Indian mobile, nullable, unique when non-null
- `otp_code_hash` — bcrypt hash of the current 6-digit OTP (cleared on verify)
- `otp_expires_at` — UTC expiry for the current OTP
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone_number", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("otp_code_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "otp_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_unique_constraint(
        "uq_users_phone_number", "users", ["phone_number"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "otp_expires_at")
    op.drop_column("users", "otp_code_hash")
    op.drop_column("users", "phone_number")
