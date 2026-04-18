"""PetroLedger — Dashboard analytics.

Read-only endpoints that power the owner dashboard charts. All queries
are org-scoped and tenant-guarded via the standard `verify_tenant_match`.
Results are returned as plain lists of dicts so recharts can plot them
directly without per-chart reshape code on the client.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date as SADate

from app.api.deps.auth import get_current_active_user
from app.core.exceptions import NotFoundError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.assignments import AnomalyFlag
from app.models.fms import CashEntry, FleetTransaction, FmsTransaction, PosBatchSettlement, FmsTxnStatus
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.reconciliation import ReconciliationResult
from app.models.shift import Shift
from app.models.transaction import UPITransaction
from app.models.user import User
from app.models.worker import Worker

router = APIRouter()


async def _guard_org(db: AsyncSession, org_id: UUID, current_user: User) -> None:
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    verify_tenant_match(org.tenant_id, current_user)


def _window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


@router.get("/variance-trend", summary="Daily variance trend for an organization")
async def variance_trend(
    org_id: UUID = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    """Return per-day totals of variance amount + shortage/excess counts."""
    await _guard_org(db, org_id, current_user)
    start, end = _window(days)

    day_col = cast(Shift.start_time, SADate).label("day")
    stmt = (
        select(
            day_col,
            func.coalesce(func.sum(ReconciliationResult.variance), 0).label("variance"),
            func.sum(
                case(
                    (ReconciliationResult.variance > 0, 1), else_=0
                )
            ).label("shortages"),
            func.sum(
                case(
                    (ReconciliationResult.variance < 0, 1), else_=0
                )
            ).label("excesses"),
        )
        .select_from(ReconciliationResult)
        .join(Shift, Shift.id == ReconciliationResult.shift_id)
        .join(Pump, Pump.id == Shift.pump_id)
        .where(
            Pump.org_id == org_id,
            Shift.start_time >= start,
            Shift.start_time <= end,
        )
        .group_by(day_col)
        .order_by(day_col)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": r.day.isoformat() if r.day else None,
            "total_variance": str(Decimal(str(r.variance))),
            "shortage_count": int(r.shortages or 0),
            "excess_count": int(r.excesses or 0),
        }
        for r in rows
    ]


@router.get("/grade-sales", summary="Per-day sales broken out by fuel grade")
async def grade_sales(
    org_id: UUID = Query(...),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    await _guard_org(db, org_id, current_user)
    start, end = _window(days)

    day_col = FmsTransaction.txn_date.label("day")
    stmt = (
        select(
            day_col,
            FmsTransaction.product_code.label("fuel_type"),
            func.coalesce(func.sum(FmsTransaction.volume_litres), 0).label("volume"),
            func.coalesce(func.sum(FmsTransaction.amount), 0).label("amount"),
        )
        .select_from(FmsTransaction)
        .join(Shift, Shift.id == FmsTransaction.shift_id)
        .join(Pump, Pump.id == Shift.pump_id)
        .where(
            Pump.org_id == org_id,
            FmsTransaction.txn_date >= start.date(),
            FmsTransaction.txn_date <= end.date(),
            FmsTransaction.status == FmsTxnStatus.COMPLETED,
            FmsTransaction.is_deleted.is_(False),
            FmsTransaction.subtype == "SALE",
        )
        .group_by(day_col, FmsTransaction.product_code)
        .order_by(day_col, FmsTransaction.product_code)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": r.day.isoformat(),
            "fuel_type": r.fuel_type or "UNKNOWN",
            "volume": str(Decimal(str(r.volume))),
            "amount": str(Decimal(str(r.amount))),
        }
        for r in rows
    ]


@router.get("/top-anomaly-workers", summary="Workers ranked by anomaly count")
async def top_anomaly_workers(
    org_id: UUID = Query(...),
    limit: int = Query(5, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    await _guard_org(db, org_id, current_user)
    start, end = _window(days)

    stmt = (
        select(
            Worker.id.label("worker_id"),
            Worker.employee_code.label("worker_code"),
            func.count(AnomalyFlag.id).label("anomaly_count"),
            func.coalesce(
                func.sum(
                    case(
                        (ReconciliationResult.variance > 0, ReconciliationResult.variance),
                        else_=0,
                    )
                ),
                0,
            ).label("total_shortage"),
        )
        .select_from(AnomalyFlag)
        .join(Shift, Shift.id == AnomalyFlag.shift_id)
        .join(Worker, Worker.id == Shift.worker_id)
        .join(Pump, Pump.id == Shift.pump_id)
        .outerjoin(ReconciliationResult, ReconciliationResult.shift_id == Shift.id)
        .where(
            Pump.org_id == org_id,
            Shift.start_time >= start,
            Shift.start_time <= end,
        )
        .group_by(Worker.id, Worker.employee_code)
        .order_by(func.count(AnomalyFlag.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "worker_id": str(r.worker_id),
            "worker_code": r.worker_code,
            "anomaly_count": int(r.anomaly_count),
            "total_shortage": str(Decimal(str(r.total_shortage))),
        }
        for r in rows
    ]


@router.get("/daily-cashflow", summary="Daily totals by payment mode")
async def daily_cashflow(
    org_id: UUID = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    await _guard_org(db, org_id, current_user)
    start, end = _window(days)

    shift_day = cast(Shift.start_time, SADate).label("day")

    async def _sum(col, table, extra_where: list | None = None) -> dict[date, Decimal]:
        stmt = (
            select(shift_day, func.coalesce(func.sum(col), 0))
            .select_from(table)
            .join(Shift, Shift.id == table.shift_id)
            .join(Pump, Pump.id == Shift.pump_id)
            .where(Pump.org_id == org_id, Shift.start_time >= start, Shift.start_time <= end)
            .group_by(shift_day)
        )
        for cond in extra_where or []:
            stmt = stmt.where(cond)
        rows = (await db.execute(stmt)).all()
        return {r[0]: Decimal(str(r[1])) for r in rows if r[0] is not None}

    upi = await _sum(UPITransaction.amount, UPITransaction)
    card = await _sum(
        PosBatchSettlement.gross_amount,
        PosBatchSettlement,
        extra_where=[PosBatchSettlement.is_deleted.is_(False)],
    )
    fleet = await _sum(
        FleetTransaction.total_amount,
        FleetTransaction,
        extra_where=[FleetTransaction.is_deleted.is_(False)],
    )
    cash = await _sum(
        CashEntry.physical_cash,
        CashEntry,
        extra_where=[CashEntry.is_deleted.is_(False)],
    )

    all_days = sorted(set(upi) | set(card) | set(fleet) | set(cash))
    out: list[dict[str, Any]] = []
    for d in all_days:
        u = upi.get(d, Decimal("0"))
        c = card.get(d, Decimal("0"))
        f = fleet.get(d, Decimal("0"))
        ca = cash.get(d, Decimal("0"))
        out.append({
            "date": d.isoformat(),
            "cash": str(ca),
            "upi": str(u),
            "card": str(c),
            "fleet": str(f),
            "total": str(ca + u + c + f),
        })
    return out
