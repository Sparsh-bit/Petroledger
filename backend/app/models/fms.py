"""PetroLedger — FMS Transaction, POS Batch Settlement, Fleet Transaction, Cash Entry Models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Nozzle
    from app.models.shift import Shift
    from app.models.worker import Worker


# ── Enums ────────────────────────────────────────────────────────────────


class FmsTxnStatus(enum.StrEnum):
    COMPLETED = "COMPLETED"
    VOID = "VOID"
    CANCELLED = "CANCELLED"


class FmsTransactionSubtype(enum.StrEnum):
    """Classifies *why* fuel was dispensed.

    Only SALE transactions contribute to the cash reconciliation total;
    the rest are operational losses / internal movements tracked for
    inventory reasons (Task 2.11).
    """
    SALE = "SALE"
    PUMP_TEST = "PUMP_TEST"
    CALIBRATION = "CALIBRATION"
    SPILLAGE = "SPILLAGE"
    TANK_TRANSFER = "TANK_TRANSFER"


class PosEntryMethod(enum.StrEnum):
    MANUAL = "MANUAL"
    OCR = "OCR"


class FleetProvider(enum.StrEnum):
    XTRAPOWER = "XTRAPOWER"
    IOCL = "IOCL"
    HPCL = "HPCL"
    PRIVATE = "PRIVATE"
    OTHER = "OTHER"


class FleetEntryMethod(enum.StrEnum):
    MANUAL = "MANUAL"
    CSV = "CSV"


# ── FmsTransaction ───────────────────────────────────────────────────────


class FmsTransaction(UUIDMixin, TimestampMixin, Base):
    """One fuel dispense event as exported from the Fuel Management System."""

    __tablename__ = "fms_transactions"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    nozzle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nozzles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    txn_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date(), nullable=False)
    txn_time: Mapped[time] = mapped_column(Time(), nullable=False)
    volume_litres: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_payment_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[FmsTxnStatus] = mapped_column(
        Enum(FmsTxnStatus, name="fms_txn_status", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=FmsTxnStatus.COMPLETED,
        nullable=False,
    )
    subtype: Mapped[str] = mapped_column(
        String(20),
        default=FmsTransactionSubtype.SALE.value,
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="fms_transactions", lazy="selectin"
    )
    nozzle: Mapped[Nozzle] = relationship("Nozzle", lazy="selectin")

    __table_args__ = (
        Index("ix_fms_transactions_shift_id", "shift_id"),
        Index("ix_fms_transactions_nozzle_id", "nozzle_id"),
        Index("ix_fms_transactions_txn_reference", "txn_reference"),
        Index("ix_fms_transactions_txn_date", "txn_date"),
        Index("ix_fms_transactions_status", "status"),
        Index("ix_fms_transactions_is_deleted", "is_deleted"),
        Index("ix_fms_transactions_shift_status_deleted", "shift_id", "status", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<FmsTransaction ₹{self.amount} ref={self.txn_reference}>"


# ── PosBatchSettlement ───────────────────────────────────────────────────


class PosBatchSettlement(UUIDMixin, TimestampMixin, Base):
    """EOD POS batch settlement total — one row per terminal per shift."""

    __tablename__ = "pos_batch_settlements"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    terminal_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    visa_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    mastercard_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rupay_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amex_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    total_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settlement_date: Mapped[date | None] = mapped_column(Date(), nullable=True)

    entry_method: Mapped[PosEntryMethod] = mapped_column(
        Enum(PosEntryMethod, name="pos_entry_method", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=PosEntryMethod.MANUAL,
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="pos_batch_settlements", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_pos_batch_settlements_shift_id", "shift_id"),
        Index("ix_pos_batch_settlements_terminal_id", "terminal_id"),
        Index("ix_pos_batch_settlements_settlement_date", "settlement_date"),
        Index("ix_pos_batch_settlements_is_deleted", "is_deleted"),
        Index("ix_pos_batch_settlements_shift_deleted", "shift_id", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<PosBatchSettlement ₹{self.gross_amount} terminal={self.terminal_id}>"


# ── FleetTransaction ─────────────────────────────────────────────────────


class FleetTransaction(UUIDMixin, TimestampMixin, Base):
    """Fleet card total per provider per shift."""

    __tablename__ = "fleet_transactions"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    fleet_provider: Mapped[FleetProvider] = mapped_column(
        Enum(FleetProvider, name="fleet_provider", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    total_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    entry_method: Mapped[FleetEntryMethod] = mapped_column(
        Enum(FleetEntryMethod, name="fleet_entry_method", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=FleetEntryMethod.MANUAL,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="fleet_transactions", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_fleet_transactions_shift_id", "shift_id"),
        Index("ix_fleet_transactions_fleet_provider", "fleet_provider"),
        Index("ix_fleet_transactions_is_deleted", "is_deleted"),
        Index("ix_fleet_transactions_shift_deleted", "shift_id", "is_deleted"),
        UniqueConstraint(
            "shift_id", "fleet_provider", "is_deleted",
            name="uq_fleet_transactions_shift_provider_active",
        ),
    )

    def __repr__(self) -> str:
        return f"<FleetTransaction ₹{self.total_amount} provider={self.fleet_provider}>"


# ── CashEntry ────────────────────────────────────────────────────────────


class CashEntry(UUIDMixin, TimestampMixin, Base):
    """Physical cash count submitted by an attendant at shift end."""

    __tablename__ = "cash_entries"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    attendant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    )
    nozzle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("nozzles.id", ondelete="SET NULL"),
        nullable=True,
    )

    physical_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Denomination breakdown (optional)
    denomination_2000: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_500: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_200: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_100: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_50: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_20: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denomination_10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coins: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="cash_entries", lazy="selectin"
    )
    attendant: Mapped[Worker | None] = relationship("Worker", lazy="selectin")

    __table_args__ = (
        Index("ix_cash_entries_shift_id", "shift_id"),
        Index("ix_cash_entries_attendant_id", "attendant_id"),
        Index("ix_cash_entries_nozzle_id", "nozzle_id"),
        Index("ix_cash_entries_is_deleted", "is_deleted"),
        Index("ix_cash_entries_is_locked", "is_locked"),
        Index("ix_cash_entries_shift_deleted", "shift_id", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<CashEntry ₹{self.physical_cash} shift={self.shift_id}>"
