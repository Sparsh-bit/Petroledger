"""PetroLedger — Organization Model."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.pump import Pump
    from app.models.tenant import Tenant
    from app.models.user import User


class OmcType(enum.StrEnum):
    BPCL = "BPCL"
    IOCL = "IOCL"
    HPCL = "HPCL"


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    dealer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dealer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    omc_type: Mapped[OmcType | None] = mapped_column(
        Enum(OmcType, name="omc_type", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    site_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Relationships ───────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant", back_populates="organizations", lazy="selectin"
    )
    users: Mapped[list[User]] = relationship("User", back_populates="organization", lazy="raise")
    pumps: Mapped[list[Pump]] = relationship("Pump", back_populates="organization", lazy="raise")

    __table_args__ = (
        Index("ix_organizations_slug", "slug"),
        Index("ix_organizations_is_active", "is_active"),
        Index("ix_organizations_site_code", "site_code"),
        Index("idx_organizations_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.slug})>"
