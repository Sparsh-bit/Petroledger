"""PetroLedger — User Schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole

# ── Request Schemas ─────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Public self-registration — owner only. Role and org_id are set by the backend."""
    name: str = Field(..., min_length=1, max_length=128)
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 64:
            raise ValueError("Password must be 64 characters or less")
        return v


class UserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=64)
    role: UserRole
    tenant_id: UUID
    org_id: UUID | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    pump_code: str | None = None


# ── Response Schemas ────────────────────────────────────────────────────


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    phone: str | None = None
    role: UserRole
    org_id: UUID | None = None
    is_active: bool
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ── Auth Token Schemas ──────────────────────────────────────────────────


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """Login response — extends Token with the authenticated user's profile."""
    user: UserResponse


class TokenRefresh(BaseModel):
    refresh_token: str
