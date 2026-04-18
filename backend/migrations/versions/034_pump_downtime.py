"""pump_downtime

Revision ID: 034
Revises: 033
Create Date: 2026-04-18

Creates `pump_downtimes` — per-pump availability log.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "034"
down_revision: str = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pump_downtimes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("pump_id", UUID(as_uuid=True),
                  sa.ForeignKey("pumps.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pump_downtimes_pump_id", "pump_downtimes", ["pump_id"])
    op.create_index("ix_pump_downtimes_started_at", "pump_downtimes", ["started_at"])
    op.create_index("ix_pump_downtimes_ended_at", "pump_downtimes", ["ended_at"])


def downgrade() -> None:
    op.drop_index("ix_pump_downtimes_ended_at", table_name="pump_downtimes")
    op.drop_index("ix_pump_downtimes_started_at", table_name="pump_downtimes")
    op.drop_index("ix_pump_downtimes_pump_id", table_name="pump_downtimes")
    op.drop_table("pump_downtimes")
