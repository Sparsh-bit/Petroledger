"""PetroLedger — Shift Model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.fms import (
        CashEntry,
        FleetTransaction,
        FmsTransaction,
        PosBatchSettlement,
    )
    from app.models.pump import Pump
    from app.models.reconciliation import ReconciliationResult
    from app.models.transaction import POSTransaction, PumpLog, UPITransaction
    from app.models.worker import Worker


class ShiftStatus(enum.StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    RECONCILED = "reconciled"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    LOCKED = "locked"
    CANCELLED = "cancelled"


class ShiftSlot(enum.StrEnum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class Shift(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    pump_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pumps.id", ondelete="CASCADE"),
        nullable=False,
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus, name="shift_status", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ShiftStatus.ACTIVE,
        nullable=False,
    )
    shift_number: Mapped[ShiftSlot | None] = mapped_column(
        Enum(ShiftSlot, name="shift_slot", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    shift_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    signed_off_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    signed_off_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Approval workflow (Task 2.9) ────────────────────────────────────
    approval_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    pump: Mapped[Pump] = relationship(
        "Pump", back_populates="shifts", lazy="selectin"
    )
    worker: Mapped[Worker] = relationship(
        "Worker", back_populates="shifts", lazy="selectin"
    )
    upi_transactions: Mapped[list[UPITransaction]] = relationship(
        "UPITransaction", back_populates="shift", lazy="raise"
    )
    pos_transactions: Mapped[list[POSTransaction]] = relationship(
        "POSTransaction", back_populates="shift", lazy="raise"
    )
    pump_logs: Mapped[list[PumpLog]] = relationship(
        "PumpLog", back_populates="shift", lazy="raise"
    )
    reconciliation: Mapped[ReconciliationResult | None] = relationship(
        "ReconciliationResult", back_populates="shift", uselist=False, lazy="raise"
    )
    fms_transactions: Mapped[list[FmsTransaction]] = relationship(
        "FmsTransaction", back_populates="shift", lazy="raise"
    )
    pos_batch_settlements: Mapped[list[PosBatchSettlement]] = relationship(
        "PosBatchSettlement", back_populates="shift", lazy="raise"
    )
    fleet_transactions: Mapped[list[FleetTransaction]] = relationship(
        "FleetTransaction", back_populates="shift", lazy="raise"
    )
    cash_entries: Mapped[list[CashEntry]] = relationship(
        "CashEntry", back_populates="shift", lazy="raise"
    )

    __table_args__ = (
        Index("ix_shifts_pump_id", "pump_id"),
        Index("ix_shifts_worker_id", "worker_id"),
        Index("ix_shifts_status", "status"),
        Index("ix_shifts_shift_date", "shift_date"),
        Index("ix_shifts_shift_number", "shift_number"),
    )

    def __repr__(self) -> str:
        return f"<Shift {self.id} status={self.status.value}>"
