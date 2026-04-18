"""PetroLedger — Reconciliation Result Model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.shift import Shift


class ReconciliationStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FLAGGED = "flagged"


class VarianceType(enum.StrEnum):
    MATCH = "MATCH"
    SHORTAGE = "SHORTAGE"
    EXCESS = "EXCESS"


class VarianceReason(enum.StrEnum):
    """Owner-selected classification of why a shift's variance occurred."""
    METER_CALIBRATION_ERROR = "METER_CALIBRATION_ERROR"
    MEASUREMENT_TOLERANCE = "MEASUREMENT_TOLERANCE"
    EVAPORATION_LOSS = "EVAPORATION_LOSS"
    SPILLAGE = "SPILLAGE"
    PUMP_TESTING = "PUMP_TESTING"
    SUSPECTED_THEFT = "SUSPECTED_THEFT"
    DIGITAL_PAYMENT_DELAY = "DIGITAL_PAYMENT_DELAY"
    ROUNDING_DIFFERENCE = "ROUNDING_DIFFERENCE"
    OTHER = "OTHER"


class ReconciliationResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_results"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    expected_cash: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    actual_cash: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    variance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, name="reconciliation_status", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ReconciliationStatus.PENDING,
        nullable=False,
    )
    anomalies: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    # PRD formula breakdown (migration 005)
    fms_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    upi_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    card_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fleet_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    variance_type: Mapped[VarianceType | None] = mapped_column(
        Enum(VarianceType, name="recon_variance_type", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-fuel-grade decomposition: {product_code: {volume_litres, amount, unit_price}}
    grade_breakdown: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # ── Variance classification (Task 2.8) ──────────────────────────────
    variance_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    variance_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reason_set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship(
        "Shift", back_populates="reconciliation", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_reconciliation_results_shift_id", "shift_id", unique=True),
        Index("ix_reconciliation_results_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ReconciliationResult shift={self.shift_id} variance={self.variance}>"
