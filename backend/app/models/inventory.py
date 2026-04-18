"""PetroLedger — Fuel tank inventory models.

Three append-mostly tables:

- FuelTank       — one row per physical storage tank at a station
- DipReading     — operator-recorded manual dip measurement
- FuelDelivery   — tanker delivery into a tank

Tank level is kept on FuelTank.current_level_litres as a running total
maintained by the service layer (add delivery volume, subtract dispensed
volume, replace by dip). History lives in the two child tables.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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
    from app.models.organization import Organization
    from app.models.user import User


class FuelTank(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fuel_tanks"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tank_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity_litres: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    current_level_litres: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    low_level_threshold: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    last_dip_reading_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(
        "Organization", lazy="selectin"
    )
    dip_readings: Mapped[list[DipReading]] = relationship(
        "DipReading", back_populates="tank", lazy="raise"
    )
    deliveries: Mapped[list[FuelDelivery]] = relationship(
        "FuelDelivery", back_populates="tank", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "tank_number", name="uq_fuel_tanks_org_tank"),
        Index("ix_fuel_tanks_org_id", "org_id"),
        Index("ix_fuel_tanks_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<FuelTank {self.org_id}/#{self.tank_number} {self.fuel_type}>"


class DipReading(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dip_readings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tank_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fuel_tanks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reading_date: Mapped[date] = mapped_column(Date, nullable=False)
    reading_litres: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    temperature_celsius: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tank: Mapped[FuelTank] = relationship(
        "FuelTank", back_populates="dip_readings", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_dip_readings_tank_id", "tank_id"),
        Index("ix_dip_readings_reading_date", "reading_date"),
    )


class FuelDelivery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fuel_deliveries"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tank_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fuel_tanks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delivery_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    challan_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    volume_ordered_litres: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    volume_received_litres: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    unit_cost_per_litre: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    tank: Mapped[FuelTank] = relationship(
        "FuelTank", back_populates="deliveries", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_fuel_deliveries_tank_id", "tank_id"),
        Index("ix_fuel_deliveries_delivery_date", "delivery_date"),
        UniqueConstraint(
            "org_id", "challan_number", name="uq_fuel_deliveries_org_challan"
        ),
    )
