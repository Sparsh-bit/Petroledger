"""PetroLedger — Tenant Model.

A tenant represents a dealer/business entity (the billing unit).
One tenant can own multiple physical petrol pump locations (organizations).

Subscription plans:
  BASIC      — max_orgs = 1  (single pump, most Indian dealers)
  PRO        — max_orgs = 5  (small chains)
  ENTERPRISE — max_orgs = 999 (effectively unlimited)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.organization import Organization
    from app.models.user import User


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    subscription_plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="BASIC", server_default="BASIC"
    )
    max_orgs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    subscription_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    monthly_price_inr: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # ── Relationships ───────────────────────────────────────────────────
    organizations: Mapped[list[Organization]] = relationship(
        "Organization", back_populates="tenant", lazy="raise"
    )
    users: Mapped[list[User]] = relationship(
        "User", back_populates="tenant", lazy="raise"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="tenant", lazy="raise"
    )

    __table_args__ = (
        Index("idx_tenants_owner_email", "owner_email"),
        Index("idx_tenants_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.name} plan={self.subscription_plan}>"
