"""PetroLedger — FMS Transaction Routes.

POST   /fms-transactions/          — ingest a single FMS transaction
GET    /fms-transactions/?shift_id — list transactions for a shift
GET    /fms-transactions/{id}      — get single transaction
DELETE /fms-transactions/{id}      — soft delete (owner/admin only)
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
from app.models.fms import FmsTransaction
from app.models.organization import Organization
from app.models.pump import Nozzle, Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.fms import (
    FmsTransactionCreate,
    FmsTransactionResponse,
    FmsTransactionSoftDelete,
)
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


@router.post(
    "/",
    response_model=FmsTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create FMS transaction",
)
async def create_fms_transaction(
    payload: FmsTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> FmsTransactionResponse:
    """Ingest a single FMS dispense event."""
    await _verify_shift_tenant_access(payload.shift_id, current_user, db)
    await _verify_nozzle_fuel_match(
        payload.nozzle_id, payload.product_code, db
    )

    txn = FmsTransaction(
        shift_id=payload.shift_id,
        nozzle_id=payload.nozzle_id,
        txn_reference=payload.txn_reference,
        txn_date=payload.txn_date,
        txn_time=payload.txn_time,
        volume_litres=payload.volume_litres,
        unit_price=payload.unit_price,
        amount=payload.amount,
        product_code=payload.product_code,
        raw_payment_mode=payload.raw_payment_mode,
        status=payload.status,
        subtype=payload.subtype.value,
        is_deleted=False,
    )
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return FmsTransactionResponse.model_validate(txn)


@router.get(
    "/",
    response_model=PagedResponse[FmsTransactionResponse],
    summary="List FMS transactions for a shift (paginated)",
)
async def list_fms_transactions(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    include_deleted: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[FmsTransactionResponse]:
    stmt = (
        select(FmsTransaction)
        .join(Shift, FmsTransaction.shift_id == Shift.id)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(FmsTransaction.shift_id == shift_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)
    if not include_deleted:
        stmt = stmt.where(FmsTransaction.is_deleted.is_(False))
    stmt = stmt.order_by(FmsTransaction.txn_date, FmsTransaction.txn_time)
    return await paginate(db, stmt, page, page_size, FmsTransactionResponse)


@router.get(
    "/{txn_id}",
    response_model=FmsTransactionResponse,
    summary="Get FMS transaction by ID",
)
async def get_fms_transaction(
    txn_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FmsTransactionResponse:
    txn = await _get_or_404(db, txn_id)
    await _verify_shift_tenant_access(txn.shift_id, current_user, db)
    return FmsTransactionResponse.model_validate(txn)


@router.delete(
    "/{txn_id}",
    response_model=FmsTransactionResponse,
    summary="Soft-delete FMS transaction",
)
async def delete_fms_transaction(
    txn_id: UUID,
    payload: FmsTransactionSoftDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> FmsTransactionResponse:
    """Soft-delete a FMS transaction.  Financial records are never hard-deleted."""
    txn = await _get_or_404(db, txn_id)
    await _verify_shift_tenant_access(txn.shift_id, current_user, db)
    if txn.is_deleted:
        raise ValidationError("Transaction is already deleted.")

    from app.services.audit import AuditService
    from app.models.pump import Pump as _Pump
    from app.models.shift import Shift as _Shift

    txn.is_deleted = True
    txn.deleted_reason = payload.deleted_reason
    await db.flush()

    # Resolve org for audit scoping via shift→pump.
    shift_row = (
        await db.execute(select(_Shift).where(_Shift.id == txn.shift_id))
    ).scalar_one_or_none()
    pump_row = None
    if shift_row is not None:
        pump_row = (
            await db.execute(select(_Pump).where(_Pump.id == shift_row.pump_id))
        ).scalar_one_or_none()
    if pump_row is not None:
        await AuditService.log_event(
            db,
            user=current_user,
            action="fms_transaction.deleted",
            entity_type="FmsTransaction",
            entity_id=txn.id,
            org_id=pump_row.org_id,
            after={
                "amount": str(txn.amount),
                "volume_litres": str(txn.volume_litres),
                "deleted_reason": txn.deleted_reason,
            },
        )

    await db.refresh(txn)
    return FmsTransactionResponse.model_validate(txn)


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


async def _get_or_404(db: AsyncSession, txn_id: UUID) -> FmsTransaction:
    row = (
        await db.execute(select(FmsTransaction).where(FmsTransaction.id == txn_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="FmsTransaction", identifier=txn_id)
    return row


# Map fuel_type → accepted FmsTransaction product_code values.
# A nozzle configured for petrol can dispense MS or SPD97; diesel → HSD; cng → CNG.
_FUEL_TYPE_TO_PRODUCTS: dict[str, set[str]] = {
    "petrol": {"MS", "SPD97"},
    "diesel": {"HSD"},
    "cng": {"CNG"},
}


async def _verify_nozzle_fuel_match(
    nozzle_id: UUID, product_code: str | None, db: AsyncSession
) -> None:
    """Raise ValidationError when *product_code* doesn't match *nozzle_id*'s fuel."""
    if product_code is None:
        return
    nozzle = (
        await db.execute(select(Nozzle).where(Nozzle.id == nozzle_id))
    ).scalar_one_or_none()
    if nozzle is None:
        raise NotFoundError(resource="Nozzle", identifier=nozzle_id)

    # Prefer explicit per-nozzle product_code when set.
    if nozzle.product_code is not None:
        if nozzle.product_code.value != product_code:
            raise ValidationError(
                f"Fuel mismatch: nozzle {nozzle_id} is configured for "
                f"{nozzle.product_code.value} but transaction is for {product_code}."
            )
        return

    fuel_key = nozzle.fuel_type.value if hasattr(nozzle.fuel_type, "value") else str(nozzle.fuel_type)
    allowed = _FUEL_TYPE_TO_PRODUCTS.get(fuel_key, set())
    if product_code not in allowed:
        raise ValidationError(
            f"Fuel mismatch: nozzle {nozzle_id} dispenses {fuel_key} "
            f"(allowed product codes: {sorted(allowed) or 'n/a'}) "
            f"but transaction product_code is {product_code}."
        )
