"""audit_log_ip_address

Revision ID: 024
Revises: 022
Create Date: 2026-04-18

Adds `ip_address` to audit_logs so every write records the originating
client IP. Nullable for historic rows and Celery-originated events.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: str = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "ip_address")
