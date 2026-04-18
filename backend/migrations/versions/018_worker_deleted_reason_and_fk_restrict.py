"""worker_deleted_reason_and_fk_restrict

Revision ID: 018
Revises: 017
Create Date: 2026-04-18

Adds `deleted_reason` to workers (complement to the existing
is_deleted + deleted_at) and changes every incoming FK that referenced
`workers.id` from ON DELETE CASCADE to ON DELETE RESTRICT, so that any
attempt to hard-delete a worker with dependent shifts, meter readings,
or shift sales fails loudly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str = "017"
branch_labels = None
depends_on = None


_FK_TABLES: list[tuple[str, str]] = [
    ("shifts", "shifts_worker_id_fkey"),
    ("nozzle_meter_readings", "nozzle_meter_readings_worker_id_fkey"),
    ("nozzle_shift_sales", "nozzle_shift_sales_worker_id_fkey"),
]


def upgrade() -> None:
    op.add_column(
        "workers",
        sa.Column("deleted_reason", sa.String(length=500), nullable=True),
    )

    for table, fk_name in _FK_TABLES:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            source_table=table,
            referent_table="workers",
            local_cols=["worker_id"],
            remote_cols=["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table, fk_name in _FK_TABLES:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            source_table=table,
            referent_table="workers",
            local_cols=["worker_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )

    op.drop_column("workers", "deleted_reason")
