"""PetroLedger — Organization CRUD Routes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.api.deps.tenant import get_current_tenant
from app.core.exceptions import NotFoundError
from app.core.tenant import check_org_limit, tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.organization import OrgCreate, OrgResponse, OrgUpdate
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class DeleteOrgRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


# ── POST / — Create Organization ────────────────────────────────────────────


@router.post(
    "/",
    response_model=OrgResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    payload: OrgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
    tenant: Tenant = Depends(get_current_tenant),
) -> OrgResponse:
    """Only owners can create organizations. Subscription plan limits are enforced."""
    # Enforce subscription plan org limit
    await check_org_limit(tenant, db)

    # Auto-generate slug from name if not provided
    slug = payload.slug
    if not slug:
        slug = re.sub(r"[^a-z0-9\s-]", "", payload.name.lower())
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")

    org = Organization(
        name=payload.name,
        slug=slug,
        contact_email=payload.contact_email,
        tenant_id=current_user.tenant_id,  # Inject tenant
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


# ── GET / — List Organizations ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=PagedResponse[OrgResponse],
    summary="List organizations",
)
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[OrgResponse]:
    """
    Return organizations visible to the current user within their tenant.

    OWNER / ADMIN: all active orgs in the tenant.
    MANAGER / WORKER: only the org they are assigned to.
    """
    query = select(Organization).where(Organization.is_deleted == False)  # noqa: E712
    query = tenant_scope(query, Organization, current_user)

    # tenant_scope handles tenant boundary but Organization has no org_id column,
    # so org-scoped roles need an explicit restriction to their assigned org.
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else current_user.role
    )
    if role_str.lower() in ("manager", "worker") and current_user.org_id:
        query = query.where(Organization.id == current_user.org_id)

    return await paginate(db, query, page, page_size, OrgResponse)


# ── GET /{org_id} — Get Organization ─────────────────────────────────────────


@router.get(
    "/{org_id}",
    response_model=OrgResponse,
    summary="Get organization by ID",
)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OrgResponse:
    org = await _get_org_or_404(db, org_id)
    verify_tenant_match(org.tenant_id, current_user)
    return OrgResponse.model_validate(org)


# ── PATCH /{org_id} — Update Organization ────────────────────────────────────


@router.patch(
    "/{org_id}",
    response_model=OrgResponse,
    summary="Update an organization",
)
async def update_organization(
    org_id: UUID,
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> OrgResponse:
    """Owners and admins can update organizations within their tenant."""
    org = await _get_org_or_404(db, org_id)
    verify_tenant_match(org.tenant_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    await db.flush()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


# ── DELETE /{org_id} — Delete Organization ────────────────────────────────────


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization",
)
async def delete_organization(
    org_id: UUID,
    payload: DeleteOrgRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
) -> None:
    """Only owners can delete organizations within their tenant. Soft delete."""
    org = await _get_org_or_404(db, org_id)
    verify_tenant_match(org.tenant_id, current_user)
    from app.services.audit import AuditService

    org.is_active = False
    org.is_deleted = True
    org.deleted_at = datetime.now(timezone.utc)
    org.deleted_reason = payload.reason if payload else None
    await db.flush()
    await AuditService.log_event(
        db,
        user=current_user,
        action="organization.deleted",
        entity_type="Organization",
        entity_id=org.id,
        org_id=org.id,
        after={"deleted_reason": org.deleted_reason},
    )
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_org_or_404(db: AsyncSession, org_id: UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.is_deleted == False,  # noqa: E712
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    return org
