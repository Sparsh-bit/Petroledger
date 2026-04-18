"""PetroLedger — NozzleMeterReading Model.

Stores raw ETOT receipt data exactly as read off the pump display — one row
per (shift, nozzle, reading_type).  This is an immutable audit trail: never
update or delete these rows; instead delete+re-insert if a correction is needed.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Nozzle
    from app.models.shift import Shift
    from app.models.worker import Worker


class NozzleMeterReading(UUIDMixin, TimestampMixin, Base):
    """One ETOT receipt reading for a single nozzle at shift open or close."""

    __tablename__ = "nozzle_meter_readings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    nozzle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nozzles.id", ondelete="CASCADE"),
        nullable=False,
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
    )

    reading_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'opening' | 'closing' — enforced by CHECK constraint in migration

    # Raw ETOT meter values — cumulative lifetime totals since machine install
    amount_cumulative: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), nullable=False
    )
    volume_cumulative: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), nullable=False
    )
    tot_sales_cumulative: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reserved for future Cloudflare R2 receipt image storage
    receipt_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    entered_manually: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship("Shift", lazy="selectin")
    nozzle: Mapped[Nozzle] = relationship("Nozzle", lazy="selectin")
    worker: Mapped[Worker] = relationship("Worker", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "reading_type IN ('opening', 'closing')",
            name="ck_nozzle_meter_readings_reading_type",
        ),
        UniqueConstraint(
            "shift_id", "nozzle_id", "reading_type",
            name="uq_nozzle_meter_readings_shift_nozzle_type",
        ),
        Index("ix_nozzle_meter_readings_shift_id", "shift_id"),
        Index("ix_nozzle_meter_readings_tenant_id", "tenant_id"),
        Index("ix_nozzle_meter_readings_nozzle_id", "nozzle_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NozzleMeterReading nozzle={self.nozzle_id} "
            f"type={self.reading_type} amount={self.amount_cumulative}>"
        )
