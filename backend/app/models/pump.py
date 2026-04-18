"""PetroLedger — Pump & Nozzle Models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.shift import Shift
    from app.models.transaction import PumpLog
    from app.models.worker import Worker


class FuelType(enum.StrEnum):
    PETROL = "petrol"
    DIESEL = "diesel"
    CNG = "cng"


class FuelProductCode(enum.StrEnum):
    MS = "MS"
    HSD = "HSD"
    SPD97 = "SPD97"
    CNG = "CNG"


class Pump(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pumps"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nozzle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="pumps", lazy="selectin"
    )
    nozzles: Mapped[list[Nozzle]] = relationship(
        "Nozzle", back_populates="pump", lazy="selectin", cascade="all, delete-orphan"
    )
    workers: Mapped[list[Worker]] = relationship(
        "Worker", back_populates="pump", lazy="raise"
    )
    shifts: Mapped[list[Shift]] = relationship(
        "Shift", back_populates="pump", lazy="raise"
    )

    __table_args__ = (
        Index("ix_pumps_org_id", "org_id"),
        Index("ix_pumps_is_active", "is_active"),
        Index("ix_pumps_is_deleted", "is_deleted"),
        Index("ix_pumps_code", "code"),
    )

    def __repr__(self) -> str:
        return f"<Pump {self.name} org={self.org_id}>"


class Nozzle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "nozzles"

    pump_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pumps.id", ondelete="CASCADE"),
        nullable=False,
    )
    nozzle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fuel_type: Mapped[FuelType] = mapped_column(
        Enum(FuelType, name="fuel_type", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    product_code: Mapped[FuelProductCode | None] = mapped_column(
        Enum(FuelProductCode, name="fuel_product_code", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    product_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ───────────────────────────────────────────────────
    pump: Mapped[Pump] = relationship(
        "Pump", back_populates="nozzles", lazy="selectin"
    )
    pump_logs: Mapped[list[PumpLog]] = relationship(
        "PumpLog", back_populates="nozzle", lazy="raise"
    )

    __table_args__ = (
        Index("ix_nozzles_pump_id", "pump_id"),
    )

    def __repr__(self) -> str:
        return f"<Nozzle #{self.nozzle_number} fuel={self.fuel_type.value}>"
