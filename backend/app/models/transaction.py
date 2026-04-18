"""PetroLedger — Transaction Models (UPI, POS, PumpLog)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Nozzle
    from app.models.shift import Shift


class UpiMatchStatus(enum.StrEnum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    MANUAL = "MANUAL"


class UPITransaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "upi_transactions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    upi_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    bank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    payer_upi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_status: Mapped[UpiMatchStatus | None] = mapped_column(
        Enum(UpiMatchStatus, name="upi_match_status", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="upi_transactions", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_upi_transactions_shift_id", "shift_id"),
        Index("ix_upi_transactions_upi_ref", "upi_ref"),
        Index("ix_upi_transactions_org_id", "org_id"),
        UniqueConstraint(
            "org_id", "content_hash", name="uq_upi_transactions_org_id_content_hash"
        ),
    )

    def __repr__(self) -> str:
        return f"<UPITransaction ₹{self.amount} ref={self.upi_ref}>"


class POSTransaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pos_transactions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    terminal_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="pos_transactions", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_pos_transactions_shift_id", "shift_id"),
        Index("ix_pos_transactions_terminal_id", "terminal_id"),
        Index("ix_pos_transactions_org_id", "org_id"),
        UniqueConstraint(
            "org_id", "content_hash", name="uq_pos_transactions_org_id_content_hash"
        ),
    )

    def __repr__(self) -> str:
        return f"<POSTransaction ₹{self.amount} terminal={self.terminal_id}>"


class PumpLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pump_logs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
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
    start_reading: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    end_reading: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    volume_dispensed: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="pump_logs", lazy="selectin"
    )
    nozzle: Mapped[Nozzle] = relationship(
        "Nozzle", back_populates="pump_logs", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_pump_logs_shift_id", "shift_id"),
        Index("ix_pump_logs_nozzle_id", "nozzle_id"),
        Index("ix_pump_logs_org_id", "org_id"),
        UniqueConstraint(
            "org_id", "content_hash", name="uq_pump_logs_org_id_content_hash"
        ),
    )

    def __repr__(self) -> str:
        return f"<PumpLog vol={self.volume_dispensed} fuel={self.fuel_type}>"
