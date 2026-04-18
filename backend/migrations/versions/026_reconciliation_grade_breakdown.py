"""reconciliation_grade_breakdown

Revision ID: 026
Revises: 025
Create Date: 2026-04-18

Adds `grade_breakdown` JSONB column to `reconciliation_results` so
station owners can see variance decomposed per fuel grade (MS / HSD /
SPD97 / CNG), not only a rolled-up total.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "026"
down_revision: str = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reconciliation_results",
        sa.Column("grade_breakdown", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reconciliation_results", "grade_breakdown")
