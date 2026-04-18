"""PetroLedger — Worker Model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Pump
    from app.models.shift import Shift
    from app.models.user import User


class Worker(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    pump_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pumps.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User", back_populates="worker_profile", lazy="selectin"
    )
    pump: Mapped[Pump] = relationship(
        "Pump", back_populates="workers", lazy="selectin"
    )
    shifts: Mapped[list[Shift]] = relationship(
        "Shift", back_populates="worker", lazy="raise"
    )

    __table_args__ = (
        Index("ix_workers_user_id", "user_id"),
        Index("ix_workers_pump_id", "pump_id"),
        Index("ix_workers_employee_code", "employee_code"),
        Index("ix_workers_is_deleted", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<Worker {self.employee_code}>"
