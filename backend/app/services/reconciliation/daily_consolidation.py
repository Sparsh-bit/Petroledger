"""PetroLedger — Daily cross-shift consolidation service.

Aggregates S1/S2/S3 reconciliation results for a given (org, date) into
a single `DailyConsolidation` row. Idempotent: call it whenever a shift
transitions to LOCKED, from the EOD sweep, or on demand.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_consolidation import DailyConsolidation, DailyConsolidationStatus
from app.models.fms import CashEntry
from app.models.pump import Pump
from app.models.reconciliation import ReconciliationResult
from app.models.shift import Shift, ShiftSlot, ShiftStatus

log = structlog.stdlib.get_logger("petroledger.services.daily_consolidation")


async def consolidate_daily(
    db: AsyncSession,
    org_id: uuid.UUID,
    day: date,
    tenant_id: uuid.UUID,
) -> DailyConsolidation:
    """Upsert a DailyConsolidation row for (org_id, day).

    Loads every shift for the org whose `shift_start::date == day`, plus
    their reconciliation results, and sums payment channels + cash.
    Status = COMPLETE only when every shift on the day is LOCKED.
    """
    # 1. Fetch all shifts + pumps scoped to the org on that day.
    shift_stmt = (
        select(Shift)
        .join(Pump, Shift.pump_id == Pump.id)
        .where(
            Pump.org_id == org_id,
            func.date(Shift.start_time) == day,
        )
    )
    shifts: list[Shift] = list((await db.execute(shift_stmt)).scalars().all())

    shift_ids = [s.id for s in shifts]

    # 2. Per-slot mapping (best-effort — some days only have 1 or 2 slots).
    slot_to_shift: dict[str, uuid.UUID] = {}
    for s in shifts:
        if s.slot is not None:
            slot_to_shift.setdefault(s.slot.value, s.id)

    # 3. Aggregate reconciliation totals.
    totals = {
        "fms": Decimal("0"),
        "upi": Decimal("0"),
        "card": Decimal("0"),
        "fleet": Decimal("0"),
        "variance": Decimal("0"),
    }
    anomaly_count = 0
    confidences: list[Decimal] = []

    if shift_ids:
        recon_stmt = select(ReconciliationResult).where(
            ReconciliationResult.shift_id.in_(shift_ids)
        )
        for rr in (await db.execute(recon_stmt)).scalars().all():
            totals["fms"] += rr.fms_total or Decimal("0")
            totals["upi"] += rr.upi_total or Decimal("0")
            totals["card"] += rr.card_total or Decimal("0")
            totals["fleet"] += rr.fleet_total or Decimal("0")
            totals["variance"] += rr.variance or Decimal("0")
            if isinstance(rr.anomalies, list):
                anomaly_count += len(rr.anomalies)
            if rr.confidence_score is not None:
                confidences.append(Decimal(str(rr.confidence_score)))

    # 4. Cash actually collected (from CashEntry) — sum physical_cash.
    cash_total = Decimal("0")
    if shift_ids:
        cash_raw = (
            await db.execute(
                select(func.coalesce(func.sum(CashEntry.physical_cash), 0)).where(
                    CashEntry.shift_id.in_(shift_ids),
                    CashEntry.is_deleted.is_(False),
                )
            )
        ).scalar_one()
        cash_total = Decimal(str(cash_raw))

    # 5. Status: COMPLETE only when every shift that ran is LOCKED.
    if shifts and all(s.status == ShiftStatus.LOCKED for s in shifts):
        status = DailyConsolidationStatus.COMPLETE
    else:
        status = DailyConsolidationStatus.PARTIAL

    confidence_avg: Decimal | None = None
    if confidences:
        confidence_avg = (sum(confidences) / Decimal(len(confidences))).quantize(
            Decimal("0.0001")
        )

    # 6. Upsert.
    existing = (
        await db.execute(
            select(DailyConsolidation).where(
                DailyConsolidation.org_id == org_id,
                DailyConsolidation.date == day,
            )
        )
    ).scalar_one_or_none()

    s1_id = slot_to_shift.get(ShiftSlot.S1.value)
    s2_id = slot_to_shift.get(ShiftSlot.S2.value)
    s3_id = slot_to_shift.get(ShiftSlot.S3.value)

    if existing is None:
        record = DailyConsolidation(
            tenant_id=tenant_id,
            org_id=org_id,
            date=day,
            total_fms_amount=totals["fms"],
            total_upi_amount=totals["upi"],
            total_card_amount=totals["card"],
            total_fleet_amount=totals["fleet"],
            total_cash_collected=cash_total,
            net_variance=totals["variance"],
            s1_shift_id=s1_id,
            s2_shift_id=s2_id,
            s3_shift_id=s3_id,
            anomaly_count=anomaly_count,
            confidence_avg=confidence_avg,
            status=status,
            computed_at=datetime.now(UTC),
        )
        db.add(record)
    else:
        existing.total_fms_amount = totals["fms"]
        existing.total_upi_amount = totals["upi"]
        existing.total_card_amount = totals["card"]
        existing.total_fleet_amount = totals["fleet"]
        existing.total_cash_collected = cash_total
        existing.net_variance = totals["variance"]
        existing.s1_shift_id = s1_id
        existing.s2_shift_id = s2_id
        existing.s3_shift_id = s3_id
        existing.anomaly_count = anomaly_count
        existing.confidence_avg = confidence_avg
        existing.status = status
        existing.computed_at = datetime.now(UTC)
        record = existing

    await db.flush()
    log.info(
        "daily_consolidation_upserted",
        org_id=str(org_id),
        day=day.isoformat(),
        status=status.value,
        variance=str(totals["variance"]),
    )
    return record
