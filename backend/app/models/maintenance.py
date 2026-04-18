"""PetroLedger — Pump downtime / maintenance log.

Tracks periods when a pump was not available for sales, either because
it was undergoing scheduled maintenance, had broken down, or was being
calibrated. An open interval has `ended_at IS NULL`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Pump


class DowntimeReason(enum.StrEnum):
    SCHEDULED_MAINTENANCE = "SCHEDULED_MAINTENANCE"
    BREAKDOWN = "BREAKDOWN"
    CALIBRATION = "CALIBRATION"
    POWER_OUTAGE = "POWER_OUTAGE"
    FUEL_SHORTAGE = "FUEL_SHORTAGE"
    SAFETY_INSPECTION = "SAFETY_INSPECTION"
    OTHER = "OTHER"


class PumpDowntime(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pump_downtimes"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pump_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pumps.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    pump: Mapped[Pump] = relationship("Pump", lazy="selectin")

    __table_args__ = (
        Index("ix_pump_downtimes_pump_id", "pump_id"),
        Index("ix_pump_downtimes_started_at", "started_at"),
        Index("ix_pump_downtimes_ended_at", "ended_at"),
    )
