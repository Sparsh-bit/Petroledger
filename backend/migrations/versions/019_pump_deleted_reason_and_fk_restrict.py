"""pump_deleted_reason_and_fk_restrict

Revision ID: 019
Revises: 018
Create Date: 2026-04-18

Adds `deleted_reason` to pumps and switches incoming FKs from CASCADE
to RESTRICT so a hard-delete attempt surfaces as an error instead of
silently destroying dependent rows (nozzles, shifts, workers).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str = "018"
branch_labels = None
depends_on = None


_FK_TABLES: list[tuple[str, str]] = [
    ("nozzles", "nozzles_pump_id_fkey"),
    ("shifts", "shifts_pump_id_fkey"),
    ("workers", "workers_pump_id_fkey"),
]


def upgrade() -> None:
    op.add_column(
        "pumps",
        sa.Column("deleted_reason", sa.String(length=500), nullable=True),
    )

    for table, fk_name in _FK_TABLES:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            source_table=table,
            referent_table="pumps",
            local_cols=["pump_id"],
            remote_cols=["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table, fk_name in _FK_TABLES:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            source_table=table,
            referent_table="pumps",
            local_cols=["pump_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )

    op.drop_column("pumps", "deleted_reason")
