"""PetroLedger — Tenant Pydantic Schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Registration ────────────────────────────────────────────────────────────


class TenantRegistrationRequest(BaseModel):
    """Request body for new tenant (dealer) sign-up.

    Creates both a Tenant record and an OWNER user in one atomic transaction.
    """

    tenant_name: str = Field(..., min_length=2, max_length=255, description="Business / pump name")
    owner_name: str = Field(..., min_length=2, max_length=255, description="Owner's full name")
    owner_phone: str = Field(..., description="10-digit mobile number")
    owner_email: EmailStr = Field(..., description="Owner's email — becomes login credential")
    password: str = Field(..., min_length=8, max_length=64, description="Strong password")

    @field_validator("owner_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = v.strip()
        if not digits.isdigit() or len(digits) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return digits


class TenantRegistrationResponse(BaseModel):
    """Response returned after successful tenant + owner creation."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    message: str = "Tenant and owner account created successfully"


# ── Tenant Info ─────────────────────────────────────────────────────────────


class TenantResponse(BaseModel):
    """Full tenant info including subscription state."""

    id: str
    name: str
    owner_name: str
    owner_email: str
    subscription_plan: str
    max_orgs: int
    current_orgs: int
    is_active: bool


class TenantOrgSummary(BaseModel):
    """Lightweight organization summary for the tenant dashboard."""

    id: str
    name: str
    slug: str
    address: str | None
    is_active: bool


# ── User summary ────────────────────────────────────────────────────────────


class TenantUserSummary(BaseModel):
    """Lightweight user summary for dropdowns / team management."""

    id: str
    email: str
    role: str
    is_active: bool


# ── Invite ──────────────────────────────────────────────────────────────────


class InviteUserRequest(BaseModel):
    """Request body for owner to invite a team member."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(..., description="10-digit mobile number")
    role: str = Field(
        ...,
        description="Role to assign: admin | manager | worker",
    )
    org_id: UUID | None = Field(
        None,
        description="Required for manager/worker roles; null for admin (sees all orgs)",
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = v.strip()
        if not digits.isdigit() or len(digits) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return digits

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"admin", "manager", "worker"}
        if v.lower() not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


class InviteUserResponse(BaseModel):
    """Response after inviting a user."""

    user_id: str
    email: str
    role: str
    temporary_password: str
    message: str = "User invited successfully. Share the temporary password securely."
