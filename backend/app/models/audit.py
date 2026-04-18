"""PetroLedger — Audit Log Model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class AuditLog(Base):
    """
    Immutable audit-trail record.

    Every significant data mutation (upload, override, status change)
    is captured here for compliance and debugging.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="e.g. upi_upload, shift_complete"
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g. shift, transaction"
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    before_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    after_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ───────────────────────────────────────────────────
    tenant: Mapped[Tenant] = relationship(
        "Tenant", back_populates="audit_logs", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.action} {self.entity_type}={self.entity_id}>"
        )
