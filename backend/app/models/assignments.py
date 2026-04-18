"""PetroLedger — Nozzle Assignment & Anomaly Flag Models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Nozzle
    from app.models.shift import Shift
    from app.models.user import User
    from app.models.worker import Worker


# ── Enums ────────────────────────────────────────────────────────────────


class AnomalySeverity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyFlagType(enum.StrEnum):
    CASH_SHORTAGE = "CASH_SHORTAGE"
    CASH_EXCESS = "CASH_EXCESS"
    FMS_DIP_MISMATCH = "FMS_DIP_MISMATCH"
    REVENUE_BELOW_TREND = "REVENUE_BELOW_TREND"
    UNUSUAL_VOID_RATE = "UNUSUAL_VOID_RATE"
    SAME_AMOUNT_REPEAT = "SAME_AMOUNT_REPEAT"
    LATE_SHIFT_CLOSE = "LATE_SHIFT_CLOSE"
    BATCH_NOT_SETTLED = "BATCH_NOT_SETTLED"
    UNMATCHED_UPI = "UNMATCHED_UPI"
    ZERO_DIGITAL_PAYMENTS = "ZERO_DIGITAL_PAYMENTS"
    WORKER_HISTORY = "WORKER_HISTORY"
    OTHER = "OTHER"


# ── NozzleAssignment ─────────────────────────────────────────────────────


class NozzleAssignment(UUIDMixin, TimestampMixin, Base):
    """Records which attendant is responsible for which nozzle during a shift.

    The partial unique index ``uq_nozzle_assignments_active`` (created in
    migration 010) enforces that only one active assignment exists per
    ``(shift_id, nozzle_id)`` at any time.  A row is "active" when
    ``relieved_at IS NULL``.
    """

    __tablename__ = "nozzle_assignments"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    nozzle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nozzles.id", ondelete="CASCADE"),
        nullable=False,
    )
    attendant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    relieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    relieved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift] = relationship("Shift", lazy="selectin")
    nozzle: Mapped[Nozzle] = relationship("Nozzle", lazy="selectin")
    attendant: Mapped[Worker] = relationship("Worker", lazy="selectin")

    __table_args__ = (
        Index("ix_nozzle_assignments_shift_id", "shift_id"),
        Index("ix_nozzle_assignments_nozzle_id", "nozzle_id"),
        Index("ix_nozzle_assignments_attendant_id", "attendant_id"),
        Index("ix_nozzle_assignments_shift_attendant", "shift_id", "attendant_id"),
        # NOTE: partial unique index uq_nozzle_assignments_active is created
        # via raw SQL in migration 010 and cannot be expressed in ORM metadata.
    )

    def __repr__(self) -> str:
        active = "active" if self.relieved_at is None else "relieved"
        return f"<NozzleAssignment nozzle={self.nozzle_id} attendant={self.attendant_id} {active}>"


# ── AnomalyFlag ──────────────────────────────────────────────────────────


class AnomalyFlag(UUIDMixin, TimestampMixin, Base):
    """Persistent, queryable anomaly record.

    Replaces the JSON blob in ``reconciliation_results.anomalies`` for
    anomalies that require individual tracking and resolution workflows.
    """

    __tablename__ = "anomaly_flags"

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=True,
    )
    attendant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    )

    flag_type: Mapped[AnomalyFlagType] = mapped_column(
        Enum(AnomalyFlagType, name="anomaly_flag_type", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    severity: Mapped[AnomalySeverity] = mapped_column(
        Enum(AnomalySeverity, name="anomaly_severity", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ───────────────────────────────────────────────────
    shift: Mapped[Shift | None] = relationship("Shift", lazy="selectin")
    attendant: Mapped[Worker | None] = relationship("Worker", lazy="selectin")
    resolver: Mapped[User | None] = relationship(
        "User", foreign_keys=[resolved_by], lazy="selectin"
    )

    __table_args__ = (
        Index("ix_anomaly_flags_site_id", "site_id"),
        Index("ix_anomaly_flags_shift_id", "shift_id"),
        Index("ix_anomaly_flags_attendant_id", "attendant_id"),
        Index("ix_anomaly_flags_flag_type", "flag_type"),
        Index("ix_anomaly_flags_severity", "severity"),
        Index("ix_anomaly_flags_is_resolved", "is_resolved"),
        Index("ix_anomaly_flags_created_at", "created_at"),
        Index("ix_anomaly_flags_site_resolved_severity", "site_id", "is_resolved", "severity"),
        Index("ix_anomaly_flags_shift_resolved", "shift_id", "is_resolved"),
    )

    def __repr__(self) -> str:
        return f"<AnomalyFlag {self.flag_type} {self.severity} resolved={self.is_resolved}>"
