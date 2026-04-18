"""fix_deduplication_scope

Revision ID: 017
Revises: 016
Create Date: 2026-04-18

Scopes transaction deduplication to the owning organisation.

Problem
-------
`upi_transactions`, `pos_transactions`, and `pump_logs` each carry a
globally-unique `content_hash`. Two different tenants that legitimately
observe the same hash (e.g. identical UPI reference reused across banks
or a collision) would conflict at the DB level, even though the Python
dedup service correctly scopes the lookup by org via Shift→Pump join.

Fix
---
1. Add a denormalised `org_id` column on each table (FK → organizations.id).
2. Backfill from shifts.pump_id → pumps.org_id.
3. Enforce NOT NULL.
4. Drop the global UNIQUE(content_hash) and replace with
   UNIQUE(org_id, content_hash).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str = "016"
branch_labels = None
depends_on = None


TABLES = ["upi_transactions", "pos_transactions", "pump_logs"]


def upgrade() -> None:
    for table in TABLES:
        # 1. Add nullable org_id FK
        op.add_column(
            table,
            sa.Column("org_id", sa.UUID(as_uuid=True), nullable=True),
        )

        # 2. Backfill from shifts → pumps
        op.execute(
            f"""
            UPDATE {table} t
               SET org_id = p.org_id
              FROM shifts s
              JOIN pumps p ON p.id = s.pump_id
             WHERE t.shift_id = s.id
               AND t.org_id IS NULL
            """
        )

        # 3. Enforce NOT NULL + FK
        op.alter_column(table, "org_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_org_id_organizations",
            source_table=table,
            referent_table="organizations",
            local_cols=["org_id"],
            remote_cols=["id"],
            ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])

        # 4. Drop global unique on content_hash and add composite unique
        op.drop_constraint(f"uq_{table}_content_hash", table, type_="unique")
        op.create_unique_constraint(
            f"uq_{table}_org_id_content_hash",
            table,
            ["org_id", "content_hash"],
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(
            f"uq_{table}_org_id_content_hash", table, type_="unique"
        )
        op.create_unique_constraint(
            f"uq_{table}_content_hash", table, ["content_hash"]
        )
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_constraint(
            f"fk_{table}_org_id_organizations", table, type_="foreignkey"
        )
        op.drop_column(table, "org_id")
