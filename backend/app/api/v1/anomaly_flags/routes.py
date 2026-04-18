"""PetroLedger — Anomaly Flag Routes.

POST   /anomaly-flags/                       — create flag (system or manual)
GET    /anomaly-flags/?site_id=...           — list with filters
GET    /anomaly-flags/{id}                   — get single flag
PATCH  /anomaly-flags/{id}/resolve           — mark as resolved
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.assignments import AnomalyFlag, AnomalyFlagType, AnomalySeverity
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.assignments import (
    AnomalyFlagCreate,
    AnomalyFlagResolve,
    AnomalyFlagResponse,
)
from app.utils.datetime import get_ist_now
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


@router.post(
    "/",
    response_model=AnomalyFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create anomaly flag",
)
async def create_anomaly_flag(
    payload: AnomalyFlagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> AnomalyFlagResponse:
    """Manually raise an anomaly flag.  The reconciliation engine also creates
    flags automatically during reconciliation."""
    # Verify the target org (site) belongs to the current user's tenant
    org = await _get_org_or_404(db, payload.site_id)
    verify_tenant_match(org.tenant_id, current_user)

    row = AnomalyFlag(
        site_id=payload.site_id,
        shift_id=payload.shift_id,
        attendant_id=payload.attendant_id,
        flag_type=payload.flag_type,
        severity=payload.severity,
        description=payload.description,
        amount=payload.amount,
        is_resolved=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return AnomalyFlagResponse.model_validate(row)


@router.get(
    "/",
    response_model=PagedResponse[AnomalyFlagResponse],
    summary="List anomaly flags",
)
async def list_anomaly_flags(
    site_id: UUID = Query(..., description="Filter by site (organization) ID"),
    shift_id: UUID | None = Query(None),
    is_resolved: bool | None = Query(None),
    severity: AnomalySeverity | None = Query(None),
    flag_type: AnomalyFlagType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[AnomalyFlagResponse]:
    """Dashboard query: unresolved flags for a site, optionally filtered by
    shift, severity, or type.  Results ordered by severity (HIGH first) then
    created_at descending."""
    # AnomalyFlag.site_id is an FK to organizations.id — join to apply tenant boundary
    stmt = (
        select(AnomalyFlag)
        .join(Organization, AnomalyFlag.site_id == Organization.id)
        .where(AnomalyFlag.site_id == site_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)

    if shift_id is not None:
        stmt = stmt.where(AnomalyFlag.shift_id == shift_id)
    if is_resolved is not None:
        stmt = stmt.where(AnomalyFlag.is_resolved.is_(is_resolved))
    if severity is not None:
        stmt = stmt.where(AnomalyFlag.severity == severity)
    if flag_type is not None:
        stmt = stmt.where(AnomalyFlag.flag_type == flag_type)
    stmt = stmt.order_by(AnomalyFlag.created_at.desc())
    return await paginate(db, stmt, page, page_size, AnomalyFlagResponse)


@router.get(
    "/{flag_id}",
    response_model=AnomalyFlagResponse,
    summary="Get anomaly flag by ID",
)
async def get_anomaly_flag(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AnomalyFlagResponse:
    row = await _get_or_404(db, flag_id)
    org = await _get_org_or_404(db, row.site_id)
    verify_tenant_match(org.tenant_id, current_user)
    return AnomalyFlagResponse.model_validate(row)


@router.patch(
    "/{flag_id}/resolve",
    response_model=AnomalyFlagResponse,
    summary="Resolve an anomaly flag",
)
async def resolve_anomaly_flag(
    flag_id: UUID,
    payload: AnomalyFlagResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> AnomalyFlagResponse:
    """Mark an anomaly flag as resolved with a mandatory explanation note."""
    row = await _get_or_404(db, flag_id)
    org = await _get_org_or_404(db, row.site_id)
    verify_tenant_match(org.tenant_id, current_user)

    if row.is_resolved:
        raise ValidationError("Anomaly flag is already resolved.")
    row.is_resolved = True
    row.resolved_by = current_user.id
    row.resolved_at = get_ist_now()
    row.resolution_note = payload.resolution_note
    await db.flush()
    await db.refresh(row)
    return AnomalyFlagResponse.model_validate(row)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_or_404(db: AsyncSession, flag_id: UUID) -> AnomalyFlag:
    row = (
        await db.execute(select(AnomalyFlag).where(AnomalyFlag.id == flag_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="AnomalyFlag", identifier=flag_id)
    return row


async def _get_org_or_404(db: AsyncSession, org_id: UUID) -> Organization:
    row = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    return row
