"""PetroLedger — Organization Schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ── Request Schemas ─────────────────────────────────────────────────────


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    contact_email: EmailStr


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    contact_email: EmailStr | None = None
    is_active: bool | None = None


# ── Response Schemas ────────────────────────────────────────────────────


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    contact_email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
