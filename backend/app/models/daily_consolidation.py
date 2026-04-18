"""PetroLedger — DailyConsolidation Model.

One row per (org, date). Aggregates the three shift reconciliations
(S1/S2/S3) into a day-level summary used for reporting and the
per-organisation cashflow dashboards.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class DailyConsolidationStatus(enum.StrEnum):
    PARTIAL = "PARTIAL"    # not all 3 shifts are LOCKED yet
    COMPLETE = "COMPLETE"  # every shift that ran that day is LOCKED


class DailyConsolidation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_consolidations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    total_fms_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_upi_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_card_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_fleet_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_cash_collected: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_variance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    s1_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    s2_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    s3_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
    )

    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_avg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    status: Mapped[DailyConsolidationStatus] = mapped_column(
        Enum(
            DailyConsolidationStatus,
            name="daily_consolidation_status",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DailyConsolidationStatus.PARTIAL,
    )

    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("org_id", "date", name="uq_daily_consolidations_org_date"),
        Index("ix_daily_consolidations_tenant_id", "tenant_id"),
        Index("ix_daily_consolidations_org_id", "org_id"),
        Index("ix_daily_consolidations_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<DailyConsolidation {self.org_id} {self.date} variance={self.net_variance}>"
