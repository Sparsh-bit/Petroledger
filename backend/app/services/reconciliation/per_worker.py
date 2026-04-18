"""PetroLedger — Per-Worker Reconciliation Service.

Runs the cash reconciliation formula at nozzle/worker granularity using
meter reading data from ``nozzle_shift_sales``.

Formula (per nozzle):
    Shift Sale    = closing_A − opening_A  (already in nozzle_shift_sales)
    Expected Cash = Shift Sale − UPI − Card − Fleet
    Variance      = Expected Cash − Actual Cash

UPI / Card / Fleet are currently shift-level in the data model (not nozzle-
level).  When a shift has a single worker per nozzle, these are surfaced at
the nozzle level only once nozzle-level payment data exists; for now they
return Decimal("0") so the formula uses meter sale vs. cash directly.

Cash is pulled from ``cash_entries.attendant_id`` — the only payment method
that already has worker granularity.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.fms import CashEntry
from app.models.nozzle_shift_sale import NozzleShiftSale
from app.schemas.meter_reading import WorkerReconciliationResult

logger = logging.getLogger(__name__)

_TWO = Decimal("0.01")


async def reconcile_per_worker(
    shift_id: UUID,
    db: AsyncSession,
) -> list[WorkerReconciliationResult]:
    """Run per-nozzle/worker reconciliation for *shift_id*.

    Returns one :class:`WorkerReconciliationResult` per nozzle that has a
    computed ``NozzleShiftSale`` record.

    Raises
    ------
    ValidationError
        When no ``nozzle_shift_sales`` rows exist for the shift (meter
        readings have not been fully submitted yet).
    """
    nozzle_sales = await _get_nozzle_shift_sales(shift_id, db)

    if not nozzle_sales:
        raise ValidationError(
            message=(
                "No meter readings found for this shift. "
                "Upload opening and closing receipts first."
            )
        )

    results: list[WorkerReconciliationResult] = []

    for sale in nozzle_sales:
        # UPI / POS / Fleet are not nozzle-granular yet — return zero.
        # When nozzle-level payment data is available this can be extended.
        upi = Decimal("0.00")
        pos = Decimal("0.00")
        fleet = Decimal("0.00")

        cash = await _get_cash_for_worker(shift_id, sale.worker_id, db)

        shift_sale = Decimal(str(sale.shift_sale_amount)).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )
        expected_cash = (shift_sale - upi - pos - fleet).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )
        variance = (expected_cash - cash).quantize(_TWO, rounding=ROUND_HALF_UP)

        if variance == 0:
            status = "MATCH"
        elif variance > 0:
            status = "SHORTAGE"
        else:
            status = "EXCESS"

        # Worker name from the related Worker → User relationship
        worker_name = _resolve_worker_name(sale)

        results.append(
            WorkerReconciliationResult(
                nozzle_id=sale.nozzle_id,
                nozzle_number=sale.nozzle.nozzle_number if sale.nozzle is not None else 0,
                worker_id=sale.worker_id,
                worker_name=worker_name,
                shift_sale_amount=shift_sale,
                upi_received=upi,
                card_settled=pos,
                fleet_card=fleet,
                expected_cash=expected_cash,
                actual_cash=cash,
                variance=variance,
                status=status,
            )
        )

        logger.info(
            "Per-worker recon | shift=%s nozzle=%s worker=%s "
            "sale=%.2f cash=%.2f variance=%.2f status=%s",
            shift_id, sale.nozzle_id, sale.worker_id,
            shift_sale, cash, variance, status,
        )

    return results


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_nozzle_shift_sales(
    shift_id: UUID, db: AsyncSession
) -> list[NozzleShiftSale]:
    stmt = select(NozzleShiftSale).where(NozzleShiftSale.shift_id == shift_id)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def _get_cash_for_worker(
    shift_id: UUID, worker_id: UUID, db: AsyncSession
) -> Decimal:
    """Sum physical_cash submitted by *worker_id* for *shift_id*."""
    stmt = select(func.coalesce(func.sum(CashEntry.physical_cash), 0)).where(
        CashEntry.shift_id == shift_id,
        CashEntry.attendant_id == worker_id,
        CashEntry.is_deleted.is_(False),
    )
    raw = (await db.execute(stmt)).scalar_one()
    return Decimal(str(raw)).quantize(_TWO, rounding=ROUND_HALF_UP)


def _resolve_worker_name(sale: NozzleShiftSale) -> str:
    """Return a display name from the loaded worker relationship."""
    worker = getattr(sale, "worker", None)
    if worker is None:
        return str(sale.worker_id)
    user = getattr(worker, "user", None)
    if user is None:
        return str(sale.worker_id)
    full_name = getattr(user, "full_name", None) or getattr(user, "email", None)
    return str(full_name or sale.worker_id)


async def get_incomplete_nozzles(
    shift_id: UUID,
    db: AsyncSession,
) -> list[int]:
    """Return nozzle_numbers that have an opening but no closing reading (or vice versa).

    Used by the shift-close guard to produce a warning before the shift is closed.
    """
    from app.models.nozzle_meter_reading import NozzleMeterReading

    stmt = (
        select(
            NozzleMeterReading.nozzle_id,
            func.count(NozzleMeterReading.id).label("cnt"),
        )
        .where(NozzleMeterReading.shift_id == shift_id)
        .group_by(NozzleMeterReading.nozzle_id)
    )
    rows = (await db.execute(stmt)).all()

    # A complete nozzle has exactly 2 readings (opening + closing)
    incomplete_nozzle_ids = {row.nozzle_id for row in rows if row.cnt < 2}

    if not incomplete_nozzle_ids:
        return []

    # Resolve to nozzle_numbers for human-readable output
    from app.models.pump import Nozzle

    nozzle_stmt = select(Nozzle.nozzle_number).where(
        Nozzle.id.in_(incomplete_nozzle_ids)
    )
    numbers = (await db.execute(nozzle_stmt)).scalars().all()
    return sorted(numbers)
