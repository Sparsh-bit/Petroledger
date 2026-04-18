"""PetroLedger — UPI Transaction Routes.

GET /upi-transactions/?shift_id  — list UPI transactions for a shift
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.core.exceptions import NotFoundError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.transaction import UPITransaction
from app.models.user import User
from app.schemas.transaction import UPITransactionResponse
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


@router.get(
    "/",
    response_model=PagedResponse[UPITransactionResponse],
    summary="List UPI transactions for a shift",
)
async def list_upi_transactions(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[UPITransactionResponse]:
    """List all UPI transactions for a shift (read-only; data ingested via CSV upload)."""
    await _verify_shift_tenant(shift_id, current_user, db)

    stmt = (
        select(UPITransaction)
        .where(UPITransaction.shift_id == shift_id)
        .order_by(UPITransaction.timestamp.desc())
    )
    return await paginate(db, stmt, page, page_size, UPITransactionResponse)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _verify_shift_tenant(
    shift_id: UUID, current_user: User, db: AsyncSession
) -> None:
    shift = (await db.execute(select(Shift).where(Shift.id == shift_id))).scalar_one_or_none()
    if shift is None:
        raise NotFoundError(resource="Shift", identifier=shift_id)
    pump = (await db.execute(select(Pump).where(Pump.id == shift.pump_id))).scalar_one_or_none()
    if pump is None:
        raise NotFoundError(resource="Pump", identifier=shift.pump_id)
    org = (await db.execute(select(Organization).where(Organization.id == pump.org_id))).scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
