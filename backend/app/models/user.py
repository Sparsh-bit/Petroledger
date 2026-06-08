"""PetroLedger — User Model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.tenant import Tenant
    from app.models.worker import Worker


class UserRole(enum.StrEnum):
    """Roles in the org hierarchy: Owner → Admin → Manager → Worker."""

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    WORKER = "worker"
    SUPERADMIN = "superadmin"
    PROVIDER = "provider"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── OAuth ───────────────────────────────────────────────────────────
    auth_provider: Mapped[str] = mapped_column(
        String(20), default="local", nullable=False
    )
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    # ── SMS OTP ─────────────────────────────────────────────────────────
    phone_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    otp_code_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Password reset ──────────────────────────────────────────────────
    reset_token_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # All JWTs issued before this timestamp are rejected. Bumped on password
    # reset so a lost refresh token cannot be replayed after the rotation.
    tokens_invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ───────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant", back_populates="users", lazy="selectin"
    )
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="users", lazy="selectin"
    )
    worker_profile: Mapped[Worker | None] = relationship(
        "Worker", back_populates="user", uselist=False, lazy="raise"
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_org_id", "org_id"),
        Index("ix_users_role", "role"),
        Index("idx_users_tenant_id", "tenant_id"),
        Index("ix_users_auth_provider", "auth_provider"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"
