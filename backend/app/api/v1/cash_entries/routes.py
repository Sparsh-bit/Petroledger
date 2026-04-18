"""PetroLedger — Cash Entry Routes.

POST   /cash-entries/          — submit a cash count
GET    /cash-entries/?shift_id — list by shift
GET    /cash-entries/{id}      — get single entry
DELETE /cash-entries/{id}      — soft delete (only if not locked)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.fms import CashEntry
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.fms import CashEntryCreate, CashEntryResponse, CashEntrySoftDelete

router = APIRouter()


@router.post(
    "/",
    response_model=CashEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit cash count for a shift",
)
async def create_cash_entry(
    payload: CashEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> CashEntryResponse:
    """Submit a physical cash count.

    Sets ``submitted_by`` to the authenticated user and ``submitted_at`` to
    the current UTC timestamp.
    """
    await _verify_shift_tenant_access(payload.shift_id, current_user, db)

    row = CashEntry(
        shift_id=payload.shift_id,
        attendant_id=payload.attendant_id,
        nozzle_id=payload.nozzle_id,
        physical_cash=payload.physical_cash,
        denomination_2000=payload.denomination_2000,
        denomination_500=payload.denomination_500,
        denomination_200=payload.denomination_200,
        denomination_100=payload.denomination_100,
        denomination_50=payload.denomination_50,
        denomination_20=payload.denomination_20,
        denomination_10=payload.denomination_10,
        coins=payload.coins,
        submitted_by=current_user.id,
        submitted_at=datetime.now(UTC),
        is_locked=False,
        is_deleted=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return CashEntryResponse.model_validate(row)


@router.get(
    "/",
    response_model=list[CashEntryResponse],
    summary="List cash entries for a shift",
)
async def list_cash_entries(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CashEntryResponse]:
    stmt = (
        select(CashEntry)
        .join(Shift, CashEntry.shift_id == Shift.id)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(CashEntry.shift_id == shift_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)
    if not include_deleted:
        stmt = stmt.where(CashEntry.is_deleted.is_(False))
    stmt = stmt.order_by(CashEntry.submitted_at)
    rows = (await db.execute(stmt)).scalars().all()
    return [CashEntryResponse.model_validate(r) for r in rows]


@router.get(
    "/{entry_id}",
    response_model=CashEntryResponse,
    summary="Get cash entry by ID",
)
async def get_cash_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CashEntryResponse:
    row = await _get_or_404(db, entry_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    return CashEntryResponse.model_validate(row)


@router.delete(
    "/{entry_id}",
    response_model=CashEntryResponse,
    summary="Soft-delete cash entry",
)
async def delete_cash_entry(
    entry_id: UUID,
    payload: CashEntrySoftDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> CashEntryResponse:
    """Soft-delete a cash entry.

    Raises **422** if the entry is locked — a locked entry requires an
    owner-level override that writes an audit log entry (not yet implemented).
    """
    row = await _get_or_404(db, entry_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    if row.is_deleted:
        raise ValidationError("Cash entry is already deleted.")
    if row.is_locked:
        raise ValidationError(
            "Cash entry is locked and cannot be deleted without an owner override."
        )
    row.is_deleted = True
    row.deleted_reason = payload.deleted_reason
    await db.flush()
    await db.refresh(row)
    return CashEntryResponse.model_validate(row)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _verify_shift_tenant_access(
    shift_id: UUID, current_user: User, db: AsyncSession
) -> Shift:
    """Resolve shift → pump → org and verify the org belongs to the user's tenant."""
    shift_row = (await db.execute(select(Shift).where(Shift.id == shift_id))).scalar_one_or_none()
    if shift_row is None:
        raise NotFoundError(resource="Shift", identifier=shift_id)

    pump_row = (await db.execute(select(Pump).where(Pump.id == shift_row.pump_id))).scalar_one_or_none()
    if pump_row is None:
        raise NotFoundError(resource="Pump", identifier=shift_row.pump_id)

    org_row = (await db.execute(select(Organization).where(Organization.id == pump_row.org_id))).scalar_one_or_none()
    if org_row is None:
        raise NotFoundError(resource="Organization", identifier=pump_row.org_id)

    verify_tenant_match(org_row.tenant_id, current_user)
    return shift_row


async def _get_or_404(db: AsyncSession, entry_id: UUID) -> CashEntry:
    row = (
        await db.execute(select(CashEntry).where(CashEntry.id == entry_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="CashEntry", identifier=entry_id)
    return row
