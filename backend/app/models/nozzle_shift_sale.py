"""PetroLedger — NozzleShiftSale Model.

Stores the derived per-nozzle shift sale computed from opening/closing meter
readings.  Populated automatically when the closing reading is submitted.
This is what the per-worker reconciliation engine reads.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Nozzle
    from app.models.shift import Shift
    from app.models.worker import Worker


class NozzleShiftSale(UUIDMixin, TimestampMixin, Base):
    """Computed shift sale for one nozzle — closing minus opening readings."""

    __tablename__ = "nozzle_shift_sales"

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

    # Raw opening/closing values (stored so sale can be verified independently)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    closing_amount: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    opening_volume: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    closing_volume: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    opening_tot_sales: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_tot_sales: Mapped[int] = mapped_column(Integer, nullable=False)

    # Derived shift totals — computed in application layer (not DB generated columns
    # for portability; SQLite used in tests doesn't support GENERATED ALWAYS AS STORED)
    shift_sale_amount: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    shift_sale_volume: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    shift_transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ────────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship("Shift", lazy="selectin")
    nozzle: Mapped[Nozzle] = relationship("Nozzle", lazy="selectin")
    worker: Mapped[Worker] = relationship("Worker", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "shift_id", "nozzle_id",
            name="uq_nozzle_shift_sales_shift_nozzle",
        ),
        Index("ix_nozzle_shift_sales_shift_id", "shift_id"),
        Index("ix_nozzle_shift_sales_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NozzleShiftSale nozzle={self.nozzle_id} "
            f"sale={self.shift_sale_amount}>"
        )
