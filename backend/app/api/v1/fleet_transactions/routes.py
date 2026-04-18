"""PetroLedger — Fleet Transaction Routes.

POST   /fleet-transactions/          — create fleet card entry
GET    /fleet-transactions/?shift_id — list by shift
GET    /fleet-transactions/{id}      — get single transaction
PATCH  /fleet-transactions/{id}      — update
DELETE /fleet-transactions/{id}      — soft delete
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
from app.models.fms import FleetTransaction
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.fms import (
    FleetTransactionCreate,
    FleetTransactionResponse,
    FleetTransactionSoftDelete,
    FleetTransactionUpdate,
)

router = APIRouter()


@router.post(
    "/",
    response_model=FleetTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create fleet transaction",
)
async def create_fleet_transaction(
    payload: FleetTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> FleetTransactionResponse:
    await _verify_shift_tenant_access(payload.shift_id, current_user, db)

    row = FleetTransaction(
        shift_id=payload.shift_id,
        fleet_provider=payload.fleet_provider,
        total_transactions=payload.total_transactions,
        total_amount=payload.total_amount,
        entry_method=payload.entry_method,
        notes=payload.notes,
        is_deleted=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return FleetTransactionResponse.model_validate(row)


@router.get(
    "/",
    response_model=list[FleetTransactionResponse],
    summary="List fleet transactions for a shift",
)
async def list_fleet_transactions(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[FleetTransactionResponse]:
    stmt = (
        select(FleetTransaction)
        .join(Shift, FleetTransaction.shift_id == Shift.id)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(FleetTransaction.shift_id == shift_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)
    if not include_deleted:
        stmt = stmt.where(FleetTransaction.is_deleted.is_(False))
    stmt = stmt.order_by(FleetTransaction.fleet_provider)
    rows = (await db.execute(stmt)).scalars().all()
    return [FleetTransactionResponse.model_validate(r) for r in rows]


@router.get(
    "/{fleet_txn_id}",
    response_model=FleetTransactionResponse,
    summary="Get fleet transaction by ID",
)
async def get_fleet_transaction(
    fleet_txn_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FleetTransactionResponse:
    row = await _get_or_404(db, fleet_txn_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    return FleetTransactionResponse.model_validate(row)


@router.patch(
    "/{fleet_txn_id}",
    response_model=FleetTransactionResponse,
    summary="Update fleet transaction",
)
async def update_fleet_transaction(
    fleet_txn_id: UUID,
    payload: FleetTransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> FleetTransactionResponse:
    row = await _get_or_404(db, fleet_txn_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    if row.is_deleted:
        raise ValidationError("Cannot update a deleted fleet transaction.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    return FleetTransactionResponse.model_validate(row)


@router.delete(
    "/{fleet_txn_id}",
    response_model=FleetTransactionResponse,
    summary="Soft-delete fleet transaction",
)
async def delete_fleet_transaction(
    fleet_txn_id: UUID,
    payload: FleetTransactionSoftDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> FleetTransactionResponse:
    row = await _get_or_404(db, fleet_txn_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    if row.is_deleted:
        raise ValidationError("Fleet transaction is already deleted.")
    row.is_deleted = True
    row.deleted_reason = payload.deleted_reason
    await db.flush()
    await db.refresh(row)
    return FleetTransactionResponse.model_validate(row)


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


async def _get_or_404(db: AsyncSession, fleet_txn_id: UUID) -> FleetTransaction:
    row = (
        await db.execute(
            select(FleetTransaction).where(FleetTransaction.id == fleet_txn_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="FleetTransaction", identifier=fleet_txn_id)
    return row
