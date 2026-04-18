"""PetroLedger — Reconciliation Data Preparation Layer.

Provides a backward-compatible way to get the total shift sale figure used
by the reconciliation engine.

Priority:
  1. Sum from ``nozzle_shift_sales`` — populated when meter readings are used.
  2. Fallback to ``fms_transactions`` — for legacy shifts that pre-date ETOT
     receipt integration.

The engine itself is never modified; only this prep layer changes.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fms import FmsTransaction, FmsTxnStatus
from app.models.nozzle_shift_sale import NozzleShiftSale


async def get_total_shift_sale(shift_id: UUID, db: AsyncSession) -> Decimal:
    """Return total shift fuel sale for *shift_id* in ₹.

    Uses meter-reading-derived ``nozzle_shift_sales`` when available; falls
    back to legacy ``fms_transactions`` for older shifts so existing
    reconciliations continue to work unchanged.
    """
    meter_total = await _sum_nozzle_shift_sales(shift_id, db)
    if meter_total is not None:
        return meter_total

    return await _sum_fms_transactions(shift_id, db)


async def _sum_nozzle_shift_sales(
    shift_id: UUID, db: AsyncSession
) -> Decimal | None:
    """Return sum of nozzle_shift_sales.shift_sale_amount, or None if no rows."""
    stmt = select(func.sum(NozzleShiftSale.shift_sale_amount)).where(
        NozzleShiftSale.shift_id == shift_id
    )
    raw = (await db.execute(stmt)).scalar_one_or_none()
    if raw is None:
        return None
    total = Decimal(str(raw))
    return total if total > 0 else None


async def _sum_fms_transactions(shift_id: UUID, db: AsyncSession) -> Decimal:
    """Legacy fallback: sum completed, non-deleted FMS transactions."""
    stmt = select(func.coalesce(func.sum(FmsTransaction.amount), 0)).where(
        FmsTransaction.shift_id == shift_id,
        FmsTransaction.status == FmsTxnStatus.COMPLETED,
        FmsTransaction.is_deleted.is_(False),
    )
    raw = (await db.execute(stmt)).scalar_one()
    return Decimal(str(raw))
