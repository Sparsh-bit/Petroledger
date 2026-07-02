"""PetroLedger — Pump & Nozzle CRUD Routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Nozzle, Pump
from app.models.user import User, UserRole
from app.schemas.pump import (
    NozzleCreate,
    NozzleResponse,
    PumpCreate,
    PumpResponse,
    PumpUpdate,
)
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class DeletePumpRequest(BaseModel):
    """Optional soft-delete payload."""
    reason: str | None = Field(default=None, max_length=500)


# ═══════════════════════════════════════════════════════════════════════
#  PUMP ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/",
    response_model=PumpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new pump",
)
async def create_pump(
    payload: PumpCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> PumpResponse:
    """Owner/admin can create pumps within their tenant's organizations."""
    # Resolve target org. If the caller didn't specify one (or specified an
    # org outside their tenant), fall back to the first active org in the
    # current user's tenant — covers freshly-provisioned owners whose
    # frontend hasn't yet hydrated its org picker.
    target_org_id = payload.org_id
    if target_org_id is not None:
        org = await _get_org_or_404(db, target_org_id)
        verify_tenant_match(org.tenant_id, current_user)
    else:
        first_org = (
            await db.execute(
                select(Organization)
                .where(
                    Organization.tenant_id == current_user.tenant_id,
                    Organization.is_deleted == False,  # noqa: E712
                    Organization.is_active == True,  # noqa: E712
                )
                .order_by(Organization.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if first_org is None:
            # Self-heal: legacy tenants or those whose workspace was never
            # fully provisioned may own zero organizations. Rather than
            # blocking the owner forever, mint a default org here using
            # the tenant's own name/email — this is idempotent (owner
            # can rename it later from Settings).
            from app.models.tenant import Tenant
            import re as _re

            tenant = (
                await db.execute(
                    select(Tenant).where(Tenant.id == current_user.tenant_id)
                )
            ).scalar_one_or_none()
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Your account is not attached to a tenant. "
                        "Contact your provider."
                    ),
                )
            slug_base = _re.sub(
                r"[^a-z0-9]+", "-", tenant.name.strip().lower()
            ).strip("-") or f"tenant-{str(tenant.id)[:8]}"
            slug = slug_base
            n = 2
            while True:
                collision = (
                    await db.execute(
                        select(Organization.id).where(Organization.slug == slug)
                    )
                ).scalar_one_or_none()
                if collision is None:
                    break
                slug = f"{slug_base}-{n}"
                n += 1
            new_org = Organization(
                name=tenant.name,
                slug=slug,
                contact_email=tenant.owner_email,
                tenant_id=tenant.id,
                is_active=True,
            )
            db.add(new_org)
            await db.flush()
            target_org_id = new_org.id
        else:
            target_org_id = first_org.id

    # Reject duplicate pump names within the same organization (case-insensitive,
    # ignoring soft-deleted rows so a name freed by deletion can be reused).
    pump_name = payload.name.strip()
    existing = (
        await db.execute(
            select(Pump.id).where(
                Pump.org_id == target_org_id,
                Pump.is_deleted == False,  # noqa: E712
                func.lower(Pump.name) == pump_name.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f'A pump named "{pump_name}" already exists in this organisation. '
                "Pick a different name or delete the existing pump first."
            ),
        )

    pump = Pump(
        org_id=target_org_id,
        name=pump_name,
        location=payload.location,
        nozzle_count=payload.nozzle_count,
    )
    db.add(pump)
    await db.flush()
    await db.refresh(pump)

    # Create inline nozzles if provided
    for n in payload.nozzles:
        nozzle = Nozzle(
            pump_id=pump.id,
            nozzle_number=n.nozzle_number,
            fuel_type=n.fuel_type,
        )
        db.add(nozzle)

    await db.flush()
    await db.refresh(pump)
    return PumpResponse.model_validate(pump)


@router.get(
    "/",
    response_model=PagedResponse[PumpResponse],
    summary="List pumps",
)
async def list_pumps(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    org_id: UUID | None = Query(None, description="Filter pumps by organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[PumpResponse]:
    """Return pumps within the current user's tenant. Managers/workers see only their org."""
    # Join through Organization to apply tenant boundary
    query = (
        select(Pump)
        .join(Organization, Pump.org_id == Organization.id)
        .where(Pump.is_deleted == False)  # noqa: E712
    )
    query = tenant_scope(query, Organization, current_user)

    # Organization has no org_id column so tenant_scope won't add the secondary filter;
    # apply it explicitly for org-scoped roles.
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else current_user.role
    )
    if role_str.lower() in ("manager", "worker") and current_user.org_id:
        query = query.where(Pump.org_id == current_user.org_id)
    elif org_id is not None:
        query = query.where(Pump.org_id == org_id)

    return await paginate(db, query, page, page_size, PumpResponse)


@router.get(
    "/{pump_id}",
    response_model=PumpResponse,
    summary="Get pump by ID",
)
async def get_pump(
    pump_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PumpResponse:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
    return PumpResponse.model_validate(pump)


@router.patch(
    "/{pump_id}",
    response_model=PumpResponse,
    summary="Update a pump",
)
async def update_pump(
    pump_id: UUID,
    payload: PumpUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)),
) -> PumpResponse:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    updates = payload.model_dump(exclude_unset=True)

    # If the name is being changed, enforce per-org uniqueness on the new value.
    if "name" in updates and updates["name"] is not None:
        new_name = str(updates["name"]).strip()
        if new_name and new_name.lower() != pump.name.lower():
            clash = (
                await db.execute(
                    select(Pump.id).where(
                        Pump.org_id == pump.org_id,
                        Pump.id != pump.id,
                        Pump.is_deleted == False,  # noqa: E712
                        func.lower(Pump.name) == new_name.lower(),
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f'A pump named "{new_name}" already exists in this '
                        "organisation. Pick a different name."
                    ),
                )
        updates["name"] = new_name

    for field, value in updates.items():
        setattr(pump, field, value)

    await db.flush()
    await db.refresh(pump)
    return PumpResponse.model_validate(pump)


@router.delete(
    "/{pump_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a pump",
)
async def delete_pump(
    pump_id: UUID,
    payload: DeletePumpRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> None:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
    from app.services.audit import AuditService

    pump.is_deleted = True
    pump.deleted_at = datetime.now(timezone.utc)
    pump.deleted_reason = payload.reason if payload else None
    await db.flush()
    await AuditService.log_event(
        db,
        user=current_user,
        action="pump.deleted",
        entity_type="Pump",
        entity_id=pump.id,
        org_id=pump.org_id,
        after={"deleted_reason": pump.deleted_reason},
    )
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════
#  NOZZLE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/{pump_id}/nozzles",
    response_model=NozzleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a nozzle to a pump",
)
async def create_nozzle(
    pump_id: UUID,
    payload: NozzleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)),
) -> NozzleResponse:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    nozzle = Nozzle(
        pump_id=pump_id,
        nozzle_number=payload.nozzle_number,
        fuel_type=payload.fuel_type,
    )
    db.add(nozzle)
    await db.flush()
    await db.refresh(nozzle)
    return NozzleResponse.model_validate(nozzle)


@router.get(
    "/{pump_id}/nozzles",
    response_model=PagedResponse[NozzleResponse],
    summary="List nozzles for a pump",
)
async def list_nozzles(
    pump_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[NozzleResponse]:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    stmt = select(Nozzle).where(Nozzle.pump_id == pump_id)
    return await paginate(db, stmt, page, page_size, NozzleResponse)


@router.delete(
    "/{pump_id}/nozzles/{nozzle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a nozzle from a pump",
)
async def delete_nozzle(
    pump_id: UUID,
    nozzle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)),
) -> None:
    pump = await _get_pump_or_404(db, pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    result = await db.execute(
        select(Nozzle).where(Nozzle.id == nozzle_id, Nozzle.pump_id == pump_id)
    )
    nozzle = result.scalar_one_or_none()
    if nozzle is None:
        raise NotFoundError(resource="Nozzle", identifier=nozzle_id)
    await db.delete(nozzle)
    await db.flush()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_pump_or_404(db: AsyncSession, pump_id: UUID) -> Pump:
    result = await db.execute(
        select(Pump).where(Pump.id == pump_id, Pump.is_deleted == False)  # noqa: E712
    )
    pump = result.scalar_one_or_none()
    if pump is None:
        raise NotFoundError(resource="Pump", identifier=pump_id)
    return pump


async def _get_org_or_404(db: AsyncSession, org_id: UUID) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    return org
