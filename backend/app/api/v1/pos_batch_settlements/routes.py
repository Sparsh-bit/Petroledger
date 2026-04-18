"""PetroLedger — POS Batch Settlement Routes.

POST   /pos-batch-settlements/          — create settlement entry
GET    /pos-batch-settlements/?shift_id — list by shift
GET    /pos-batch-settlements/{id}      — get single settlement
PATCH  /pos-batch-settlements/{id}      — update (before shift is reconciled)
DELETE /pos-batch-settlements/{id}      — soft delete
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
from app.models.fms import PosBatchSettlement
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.fms import (
    PosBatchSettlementCreate,
    PosBatchSettlementResponse,
    PosBatchSettlementSoftDelete,
    PosBatchSettlementUpdate,
)

router = APIRouter()


@router.post(
    "/",
    response_model=PosBatchSettlementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create POS batch settlement",
)
async def create_pos_batch_settlement(
    payload: PosBatchSettlementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> PosBatchSettlementResponse:
    await _verify_shift_tenant_access(payload.shift_id, current_user, db)

    row = PosBatchSettlement(
        shift_id=payload.shift_id,
        terminal_id=payload.terminal_id,
        batch_number=payload.batch_number,
        gross_amount=payload.gross_amount,
        visa_amount=payload.visa_amount,
        mastercard_amount=payload.mastercard_amount,
        rupay_amount=payload.rupay_amount,
        amex_amount=payload.amex_amount,
        total_transactions=payload.total_transactions,
        settlement_date=payload.settlement_date,
        entry_method=payload.entry_method,
        is_deleted=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return PosBatchSettlementResponse.model_validate(row)


@router.get(
    "/",
    response_model=list[PosBatchSettlementResponse],
    summary="List POS batch settlements for a shift",
)
async def list_pos_batch_settlements(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[PosBatchSettlementResponse]:
    stmt = (
        select(PosBatchSettlement)
        .join(Shift, PosBatchSettlement.shift_id == Shift.id)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(PosBatchSettlement.shift_id == shift_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)
    if not include_deleted:
        stmt = stmt.where(PosBatchSettlement.is_deleted.is_(False))
    stmt = stmt.order_by(PosBatchSettlement.created_at)
    rows = (await db.execute(stmt)).scalars().all()
    return [PosBatchSettlementResponse.model_validate(r) for r in rows]


@router.get(
    "/{settlement_id}",
    response_model=PosBatchSettlementResponse,
    summary="Get POS batch settlement by ID",
)
async def get_pos_batch_settlement(
    settlement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PosBatchSettlementResponse:
    row = await _get_or_404(db, settlement_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    return PosBatchSettlementResponse.model_validate(row)


@router.patch(
    "/{settlement_id}",
    response_model=PosBatchSettlementResponse,
    summary="Update POS batch settlement",
)
async def update_pos_batch_settlement(
    settlement_id: UUID,
    payload: PosBatchSettlementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> PosBatchSettlementResponse:
    row = await _get_or_404(db, settlement_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    if row.is_deleted:
        raise ValidationError("Cannot update a deleted settlement.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.refresh(row)
    return PosBatchSettlementResponse.model_validate(row)


@router.delete(
    "/{settlement_id}",
    response_model=PosBatchSettlementResponse,
    summary="Soft-delete POS batch settlement",
)
async def delete_pos_batch_settlement(
    settlement_id: UUID,
    payload: PosBatchSettlementSoftDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> PosBatchSettlementResponse:
    row = await _get_or_404(db, settlement_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    if row.is_deleted:
        raise ValidationError("Settlement is already deleted.")
    row.is_deleted = True
    row.deleted_reason = payload.deleted_reason
    await db.flush()
    await db.refresh(row)
    return PosBatchSettlementResponse.model_validate(row)


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


async def _get_or_404(db: AsyncSession, settlement_id: UUID) -> PosBatchSettlement:
    row = (
        await db.execute(
            select(PosBatchSettlement).where(PosBatchSettlement.id == settlement_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="PosBatchSettlement", identifier=settlement_id)
    return row
