"""PetroLedger — Tenant Management Routes."""

from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.api.deps.tenant import get_current_tenant
from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.core.tenant import get_tenant_org_count, verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.tenant import (
    InviteUserRequest,
    InviteUserResponse,
    TenantOrgSummary,
    TenantResponse,
    TenantUserSummary,
)

router = APIRouter()


# ── GET /tenants/me ──────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=TenantResponse,
    summary="Get current tenant info",
)
async def get_my_tenant(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Return the authenticated user's tenant (business entity).

    Shows subscription plan, org limit, and current org count.
    Accessible by all authenticated users.
    """
    current_orgs = await get_tenant_org_count(tenant.id, db)
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        owner_name=tenant.owner_name,
        owner_email=tenant.owner_email,
        subscription_plan=tenant.subscription_plan,
        max_orgs=tenant.max_orgs,
        current_orgs=current_orgs,
        is_active=tenant.is_active,
    )


# ── GET /tenants/me/organizations ────────────────────────────────────────────


@router.get(
    "/me/organizations",
    response_model=list[TenantOrgSummary],
    summary="List organizations in my tenant",
)
async def get_my_organizations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[TenantOrgSummary]:
    """
    List organizations that belong to the current user's tenant.

    - OWNER / ADMIN: all active orgs in the tenant.
    - MANAGER / WORKER: only the org they are assigned to.
    """
    from app.core.tenant import tenant_scope

    query = select(Organization).where(Organization.is_active == True)  # noqa: E712
    query = tenant_scope(query, Organization, current_user)

    result = await db.execute(query)
    orgs = result.scalars().all()

    return [
        TenantOrgSummary(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            address=org.address,
            is_active=org.is_active,
        )
        for org in orgs
    ]


# ── GET /tenants/me/users ────────────────────────────────────────────────────


@router.get(
    "/me/users",
    response_model=list[TenantUserSummary],
    summary="List users in my tenant",
)
async def get_my_users(
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[TenantUserSummary]:
    """List all active users in the current tenant (owner/admin only)."""
    result = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.is_active == True,  # noqa: E712
        ).order_by(User.email)
    )
    users = result.scalars().all()
    return [
        TenantUserSummary(id=str(u.id), email=u.email, role=u.role if isinstance(u.role, str) else u.role.value, is_active=u.is_active)
        for u in users
    ]


# ── POST /tenants/invite-user ────────────────────────────────────────────────


@router.post(
    "/invite-user",
    response_model=InviteUserResponse,
    summary="Invite a team member to the tenant",
)
async def invite_user(
    data: InviteUserRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> InviteUserResponse:
    """
    Invite a new user to the current tenant (OWNER only).

    Creates an account with a generated temporary password.
    The caller is responsible for communicating the password securely.

    Role rules:
    - ``admin``   → org_id must be **null** (sees all orgs in the tenant)
    - ``manager`` → org_id **required**
    - ``worker``  → org_id **required**
    """
    from app.core.exceptions import DuplicateError, ValidationError

    # Email uniqueness check
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateError(f"Email '{data.email}' is already registered")

    # Validate org_id rules per role
    role_enum = UserRole[data.role.upper()]

    if role_enum in (UserRole.MANAGER, UserRole.WORKER):
        if data.org_id is None:
            raise ValidationError(f"Role '{data.role}' requires an org_id assignment")

        org = await db.get(Organization, data.org_id)
        if org is None or not org.is_active:
            raise NotFoundError(resource="Organization", identifier=str(data.org_id))

        # Ensure org belongs to the same tenant
        verify_tenant_match(org.tenant_id, current_user)

    if role_enum == UserRole.ADMIN and data.org_id is not None:
        raise ValidationError("Admin role must have org_id = null (can see all orgs)")

    # Generate a secure temporary password
    temp_password = secrets.token_urlsafe(12)

    new_user = User(
        email=data.email,
        phone=data.phone,
        hashed_password=hash_password(temp_password),
        role=role_enum,
        tenant_id=current_user.tenant_id,  # Same tenant as the inviting owner
        org_id=data.org_id,
        is_active=True,
        full_name=data.full_name,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    from app.core.email import send_invite_email

    async def _send_email_bg() -> None:
        await asyncio.to_thread(
            send_invite_email,
            to_email=new_user.email,
            full_name=data.full_name,
            role=data.role,
            temporary_password=temp_password,
        )

    background_tasks.add_task(_send_email_bg)

    return InviteUserResponse(
        user_id=str(new_user.id),
        email=new_user.email,
        role=data.role,
        temporary_password=temp_password,
    )
