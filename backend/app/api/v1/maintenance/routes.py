"""PetroLedger — Pump downtime / maintenance routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.maintenance import DowntimeReason, PumpDowntime
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.user import User, UserRole
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class DowntimeStart(BaseModel):
    pump_id: UUID
    started_at: datetime | None = None
    reason_type: DowntimeReason
    description: str | None = Field(default=None, max_length=4000)


class DowntimeEnd(BaseModel):
    ended_at: datetime | None = None


class DowntimeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pump_id: UUID
    org_id: UUID
    started_at: datetime
    ended_at: datetime | None
    reason_type: str
    description: str | None
    created_by_user_id: UUID | None
    created_at: datetime


async def _get_pump(db: AsyncSession, pump_id: UUID, user: User) -> Pump:
    pump = (
        await db.execute(
            select(Pump).where(Pump.id == pump_id, Pump.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if pump is None:
        raise NotFoundError(resource="Pump", identifier=pump_id)
    org = (
        await db.execute(select(Organization).where(Organization.id == pump.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=pump.org_id)
    verify_tenant_match(org.tenant_id, user)
    return pump


@router.post(
    "/downtime/start",
    response_model=DowntimeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new pump downtime window",
)
async def start_downtime(
    payload: DowntimeStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> DowntimeResponse:
    pump = await _get_pump(db, payload.pump_id, current_user)

    # Reject if an open (ended_at IS NULL) downtime already exists.
    open_row = (
        await db.execute(
            select(PumpDowntime).where(
                PumpDowntime.pump_id == pump.id,
                PumpDowntime.ended_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if open_row is not None:
        raise ValidationError(
            f"Pump {pump.id} already has an open downtime (id={open_row.id}). "
            "Close it before opening a new one."
        )

    row = PumpDowntime(
        org_id=pump.org_id,
        pump_id=pump.id,
        started_at=payload.started_at or datetime.now(UTC),
        reason_type=payload.reason_type.value,
        description=payload.description,
        created_by_user_id=current_user.id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return DowntimeResponse.model_validate(row)


@router.post(
    "/downtime/{downtime_id}/end",
    response_model=DowntimeResponse,
    summary="Close an open pump downtime window",
)
async def end_downtime(
    downtime_id: UUID,
    payload: DowntimeEnd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> DowntimeResponse:
    row = (
        await db.execute(select(PumpDowntime).where(PumpDowntime.id == downtime_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="PumpDowntime", identifier=downtime_id)

    await _get_pump(db, row.pump_id, current_user)

    if row.ended_at is not None:
        raise ValidationError("Downtime is already closed.")

    end = payload.ended_at or datetime.now(UTC)
    if end < row.started_at:
        raise ValidationError("ended_at cannot precede started_at.")

    row.ended_at = end
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return DowntimeResponse.model_validate(row)


@router.get(
    "/downtime",
    response_model=PagedResponse[DowntimeResponse],
    summary="List pump downtime windows",
)
async def list_downtimes(
    pump_id: UUID | None = Query(None),
    org_id: UUID | None = Query(None),
    open_only: bool = Query(False, description="Only return open (ended_at IS NULL) windows"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[DowntimeResponse]:
    stmt = select(PumpDowntime).order_by(PumpDowntime.started_at.desc())

    if pump_id is not None:
        await _get_pump(db, pump_id, current_user)
        stmt = stmt.where(PumpDowntime.pump_id == pump_id)
    elif org_id is not None:
        org = (
            await db.execute(select(Organization).where(Organization.id == org_id))
        ).scalar_one_or_none()
        if org is None:
            raise NotFoundError(resource="Organization", identifier=org_id)
        verify_tenant_match(org.tenant_id, current_user)
        stmt = stmt.where(PumpDowntime.org_id == org_id)
    else:
        # Default: scope to the caller's assigned org when available, else
        # return an empty page to avoid cross-tenant leakage.
        if current_user.org_id is not None:
            stmt = stmt.where(PumpDowntime.org_id == current_user.org_id)
        else:
            # Owners without a pinned org_id must pass org_id or pump_id.
            raise ValidationError("Pass either pump_id or org_id.")

    if open_only:
        stmt = stmt.where(PumpDowntime.ended_at.is_(None))

    return await paginate(db, stmt, page, page_size, DowntimeResponse)
