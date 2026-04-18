"""PetroLedger — Access Request Model.

Stores public 'request access' submissions for the ERP.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AccessRequestStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccessRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "access_requests"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    pump_count_range: Mapped[str] = mapped_column(String(32), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccessRequestStatus] = mapped_column(
        SAEnum(AccessRequestStatus, name="access_request_status"),
        nullable=False,
        default=AccessRequestStatus.NEW,
        index=True,
    )
    provider_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
