"""
PetroLedger — Reconciliation Celery Tasks.

Single-shift and end-of-day reconciliation with Celery Beat scheduling.

Async/sync bridge:
    Celery workers are synchronous.  All DB and service code is async.
    Each task uses ``asyncio.run()`` with a *fresh* SQLAlchemy engine
    (never shared from the FastAPI process) to avoid cross-loop errors.

Decimal serialization:
    Celery serializes task args as JSON.  Decimal values are passed as
    strings and reconstructed with ``Decimal(str_value)`` inside the async
    implementation to preserve full precision with no floating-point drift.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from celery import shared_task
from celery.schedules import crontab
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.tasks.celery_app import celery_app

log = structlog.stdlib.get_logger("petroledger.tasks.reconciliation")
settings = get_settings()

_IST = ZoneInfo("Asia/Kolkata")


async def _tenant_from_org(db: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    """Resolve org_id → tenant_id for audit scoping."""
    from app.models.organization import Organization

    stmt = select(Organization.tenant_id).where(Organization.id == org_id)
    result = await db.execute(stmt)
    tenant_id = result.scalar_one_or_none()
    if tenant_id is None:
        raise ValueError(f"Organization {org_id} not found")
    return tenant_id

# ── Anomaly type → AnomalyFlagType mapping ──────────────────────────────
# anomaly.py emits uppercase string constants; AnomalyFlagType enum values
# are identical uppercase strings — map the few that differ.

_ANOMALY_TYPE_MAP: dict[str, str] = {
    "CASH_VARIANCE_HIGH": "CASH_SHORTAGE",        # sign-resolved at persist time
    "VOLUME_MISMATCH": "FMS_DIP_MISMATCH",
    "UNUSUAL_TRANSACTION_PATTERN": "OTHER",
    "NIGHT_SHIFT_VARIANCE": "CASH_SHORTAGE",      # sign-resolved at persist time
    "WORKER_HISTORICAL_FLAG": "WORKER_HISTORY",
    "ZERO_DIGITAL_PAYMENTS": "ZERO_DIGITAL_PAYMENTS",
}

# anomaly.py uses lowercase severity; AnomalySeverity enum is uppercase
_SEVERITY_MAP: dict[str, str] = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "HIGH",   # no CRITICAL level in enum — collapse to HIGH
}

# Sentinel UUID used for system-initiated actions in audit logs
_SYSTEM_USER_ID = uuid.UUID(int=0)


# ── DB session factory (Celery-local, fresh per task) ───────────────────

def _make_session_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create a fresh async engine + session factory for this Celery task.

    Celery workers run in separate OS processes with their own event loop.
    We must NOT reuse the FastAPI engine (different loop, different process).

    Returns (engine, factory) so the caller can call ``await engine.dispose()``
    in a finally block to cleanly return connections to the PostgreSQL pool.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# ═══════════════════════════════════════════════════════════════════════
#  TASK 1 — run_reconciliation
# ═══════════════════════════════════════════════════════════════════════


@shared_task(bind=True, name="reconciliation.run_reconciliation", max_retries=3)
def run_reconciliation(
    self,
    shift_id: str,
    actual_cash_str: str,
    user_id: str,
    org_id: str,
) -> dict:
    """Reconcile a single shift (Celery task wrapper).

    Parameters
    ----------
    shift_id:
        UUID string of the shift to reconcile.
    actual_cash_str:
        Physical cash counted by the attendant, serialised as a decimal
        string (e.g. ``"4500.00"``) to survive JSON serialisation.
    user_id:
        UUID string of the user who triggered reconciliation (or the
        system sentinel ``"00000000-0000-0000-0000-000000000000"`` for
        EOD-initiated runs).
    org_id:
        UUID string of the organisation / site.

    Retry policy
    ------------
    Up to 3 retries with exponential back-off (60s → 120s → 240s).
    ``ValidationError`` (e.g. shift still ACTIVE) is *not* retried.
    """
    log.info("reconciliation_task_started", shift_id=shift_id, user_id=user_id)

    try:
        result = asyncio.run(
            _reconcile_shift_async(
                shift_id=shift_id,
                actual_cash_str=actual_cash_str,
                user_id=user_id,
                org_id=org_id,
            )
        )
        log.info(
            "reconciliation_task_complete",
            shift_id=shift_id,
            variance=result["variance"],
            status=result["status"],
        )
        return result

    except _NoRetryError:
        # Domain errors that should not be retried (ACTIVE shift, not found, etc.)
        log.warning("reconciliation_task_no_retry", shift_id=shift_id)
        raise

    except Exception as exc:
        log.exception("reconciliation_task_failed", shift_id=shift_id)
        countdown = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=countdown) from exc


class _NoRetryError(Exception):
    """Wraps domain errors that must not trigger Celery retries."""


async def _reconcile_shift_async(
    *,
    shift_id: str,
    actual_cash_str: str,
    user_id: str,
    org_id: str,
) -> dict[str, Any]:
    """Full async reconciliation pipeline for a single shift."""
    # Deferred imports avoid heavy module loading at worker startup and
    # prevent circular-import issues between tasks ↔ services.
    from app.core.exceptions import NotFoundError, ValidationError
    from app.services.audit import AuditService
    from app.services.reconciliation.engine import ReconciliationEngine

    _engine, session_factory = _make_session_factory()
    shift_uuid = uuid.UUID(shift_id)
    actual_cash = Decimal(actual_cash_str)

    try:
        async with session_factory() as db:
            try:
                engine = ReconciliationEngine()
                response = await engine.reconcile(
                    shift_id=shift_uuid,
                    actual_cash=actual_cash,
                    db=db,
                )

                # Persist structured AnomalyFlag rows for dashboard / resolution flow
                await _persist_anomaly_flags(
                    anomalies=response.anomalies,
                    shift_id=shift_uuid,
                    site_id=uuid.UUID(org_id),
                    variance=response.variance,
                    db=db,
                )

                # Immutable audit entry
                await AuditService.log(
                    db,
                    action="reconciliation_completed",
                    entity_type="reconciliation_result",
                    entity_id=response.id,
                    user_id=uuid.UUID(user_id),
                    org_id=uuid.UUID(org_id),
                    tenant_id=await _tenant_from_org(db, uuid.UUID(org_id)),
                    before=None,
                    after={
                        "shift_id": shift_id,
                        "variance": str(response.variance),
                        "expected_cash": str(response.expected_cash),
                        "actual_cash": str(response.actual_cash),
                        "status": response.status.value,
                        "anomaly_count": len(response.anomalies),
                        "confidence_score": (
                            str(response.confidence_score)
                            if response.confidence_score is not None
                            else None
                        ),
                    },
                    metadata={
                        "triggered_by": "celery_task",
                        "actual_cash_submitted": actual_cash_str,
                    },
                )

                await db.commit()

                return {
                    "shift_id": shift_id,
                    "result_id": str(response.id),
                    "status": response.status.value,
                    "variance": str(response.variance),
                    "expected_cash": str(response.expected_cash),
                    "actual_cash": str(response.actual_cash),
                    "confidence_score": (
                        str(response.confidence_score)
                        if response.confidence_score is not None
                        else None
                    ),
                    "anomaly_count": len(response.anomalies),
                    "reconciled_at": datetime.now(UTC).isoformat(),
                }

            except (NotFoundError, ValidationError) as exc:
                await db.rollback()
                # These are domain errors — retrying will not help
                raise _NoRetryError(str(exc)) from exc

            except Exception:
                await db.rollback()
                raise
    finally:
        await _engine.dispose()


async def _persist_anomaly_flags(
    *,
    anomalies: list,
    shift_id: uuid.UUID,
    site_id: uuid.UUID,
    variance: Decimal,
    db: AsyncSession,
) -> None:
    """Write AnomalyFlag rows for every detected anomaly.

    Idempotent: existing *unresolved* flags for the shift are cleared
    before inserting the new set so re-runs don't accumulate duplicates.
    Already-resolved flags are preserved (they represent human actions).
    """
    from sqlalchemy import delete as sa_delete

    from app.models.assignments import AnomalyFlag, AnomalyFlagType, AnomalySeverity

    # Clear previous unresolved flags for this shift (safe re-run)
    await db.execute(
        sa_delete(AnomalyFlag).where(
            AnomalyFlag.shift_id == shift_id,
            AnomalyFlag.is_resolved.is_(False),
        )
    )

    for anomaly in anomalies:
        # Cash-variance anomalies: assign SHORTAGE vs EXCESS based on sign
        raw_type: str = anomaly.type
        flag_type_str = _ANOMALY_TYPE_MAP.get(raw_type, "OTHER")

        if raw_type in ("CASH_VARIANCE_HIGH", "NIGHT_SHIFT_VARIANCE"):
            flag_type_str = "CASH_SHORTAGE" if variance > 0 else "CASH_EXCESS"

        try:
            flag_type = AnomalyFlagType(flag_type_str)
        except ValueError:
            flag_type = AnomalyFlagType.OTHER

        severity_raw = anomaly.severity.lower() if anomaly.severity else "medium"
        severity = AnomalySeverity(_SEVERITY_MAP.get(severity_raw, "MEDIUM"))

        db.add(
            AnomalyFlag(
                site_id=site_id,
                shift_id=shift_id,
                flag_type=flag_type,
                severity=severity,
                description=anomaly.description,
                amount=anomaly.amount,
                is_resolved=False,
            )
        )

    await db.flush()


# ═══════════════════════════════════════════════════════════════════════
#  TASK 2 — run_eod_reconciliation
# ═══════════════════════════════════════════════════════════════════════


@shared_task(name="reconciliation.run_eod_reconciliation")
def run_eod_reconciliation() -> dict:
    """End-of-day reconciliation sweep (Celery Beat task).

    Scheduled nightly at 23:45 IST.  Steps:

    1. Auto-close any ACTIVE shifts that are more than 9 hours old
       (stale / forgotten shifts).
    2. Find all COMPLETED shifts for today without a
       ``ReconciliationResult``.
    3. For each shift, sum ``cash_entries.physical_cash`` to get the
       actual cash count.
    4. Dispatch ``run_reconciliation`` for each shift.

    Shift-3 midnight handling:
        Shift 3 spans 22:00–06:00.  A shift started at, say, 22:30
        yesterday belongs to "today's" EOD sweep.  This function
        includes shifts whose ``start_time`` falls in the window
        [yesterday 22:00 IST, today 06:00 IST) as well as
        [today 00:00 IST, today 23:45 IST).
    """
    log.info("eod_reconciliation_sweep_started")

    try:
        result = asyncio.run(_eod_sweep_async())
        log.info(
            "eod_reconciliation_sweep_complete",
            dispatched=result["shifts_queued"],
            skipped=result["shifts_skipped"],
            auto_closed=result["auto_closed"],
        )
        return result

    except Exception:
        log.exception("eod_reconciliation_sweep_failed")
        raise


async def _eod_sweep_async() -> dict[str, Any]:
    """Full async EOD sweep implementation."""
    from sqlalchemy import or_

    from app.models.fms import CashEntry
    from app.models.pump import Pump
    from app.models.reconciliation import ReconciliationResult
    from app.models.shift import Shift, ShiftStatus
    from app.services.audit import AuditService

    _engine, session_factory = _make_session_factory()

    try:
        async with session_factory() as db:
            now_ist = datetime.now(_IST)
            today_ist = now_ist.date()
            yesterday_ist = today_ist - timedelta(days=1)

            # ── UTC boundaries for today (IST) ────────────────────────────
            today_start_utc = datetime(
                today_ist.year, today_ist.month, today_ist.day, tzinfo=_IST
            ).astimezone(UTC)
            today_end_utc = today_start_utc + timedelta(days=1)

            # Shift 3 window: yesterday 22:00 IST → today 06:00 IST
            s3_window_start_utc = datetime(
                yesterday_ist.year, yesterday_ist.month, yesterday_ist.day,
                22, 0, tzinfo=_IST,
            ).astimezone(UTC)
            s3_window_end_utc = datetime(
                today_ist.year, today_ist.month, today_ist.day,
                6, 0, tzinfo=_IST,
            ).astimezone(UTC)

            # ── Step 1: Auto-close stale ACTIVE shifts ────────────────────
            stale_cutoff_utc = (now_ist - timedelta(hours=9)).astimezone(UTC)

            stale_result = await db.execute(
                select(Shift).where(
                    Shift.status == ShiftStatus.ACTIVE,
                    Shift.start_time < stale_cutoff_utc,
                )
            )
            stale_shifts = list(stale_result.scalars().all())
            auto_closed = 0

            for shift in stale_shifts:
                shift.status = ShiftStatus.COMPLETED
                if shift.end_time is None:
                    shift.end_time = now_ist.astimezone(UTC)
                auto_closed += 1
                log.warning(
                    "eod_auto_closed_stale_shift",
                    shift_id=str(shift.id),
                    started_at=shift.start_time.isoformat(),
                )

            if auto_closed:
                await db.flush()

            # ── Step 2: Find COMPLETED shifts for today without a result ──
            already_reconciled_subq = select(ReconciliationResult.shift_id)

            unreconciled_result = await db.execute(
                select(Shift).where(
                    Shift.status == ShiftStatus.COMPLETED,
                    Shift.id.not_in(already_reconciled_subq),
                    or_(
                        # Regular shifts (S1/S2): started today
                        (Shift.start_time >= today_start_utc)
                        & (Shift.start_time < today_end_utc),
                        # Shift 3: started yesterday evening
                        (Shift.start_time >= s3_window_start_utc)
                        & (Shift.start_time < s3_window_end_utc),
                    ),
                )
            )
            shifts_to_reconcile = list(unreconciled_result.scalars().all())

            if not shifts_to_reconcile:
                log.info("eod_no_shifts_to_reconcile", date=today_ist.isoformat())
                await db.commit()
                return {
                    "status": "no_work",
                    "shifts_queued": 0,
                    "shifts_skipped": 0,
                    "auto_closed": auto_closed,
                    "triggered_at": now_ist.isoformat(),
                }

            # ── Step 3: Load pumps to resolve org_id per shift ────────────
            pump_ids = {s.pump_id for s in shifts_to_reconcile}
            pump_rows = await db.execute(select(Pump).where(Pump.id.in_(pump_ids)))
            pumps: dict[uuid.UUID, Pump] = {p.id: p for p in pump_rows.scalars().all()}

            # ── Step 4: Sum cash entries and dispatch tasks ────────────────
            dispatched: list[str] = []
            skipped: list[str] = []
            org_shift_map: dict[str, list[str]] = {}

            for shift in shifts_to_reconcile:
                pump = pumps.get(shift.pump_id)
                if pump is None:
                    log.warning("eod_skipped_shift_no_pump", shift_id=str(shift.id))
                    skipped.append(str(shift.id))
                    continue

                org_id_str = str(pump.org_id)

                cash_raw = (
                    await db.execute(
                        select(func.coalesce(func.sum(CashEntry.physical_cash), 0)).where(
                            CashEntry.shift_id == shift.id,
                            CashEntry.is_deleted.is_(False),
                        )
                    )
                ).scalar_one()
                actual_cash_str = str(Decimal(str(cash_raw)))

                run_reconciliation.delay(
                    shift_id=str(shift.id),
                    actual_cash_str=actual_cash_str,
                    user_id=str(_SYSTEM_USER_ID),
                    org_id=org_id_str,
                )

                dispatched.append(str(shift.id))
                org_shift_map.setdefault(org_id_str, []).append(str(shift.id))

                log.info(
                    "eod_dispatched_reconciliation",
                    shift_id=str(shift.id),
                    actual_cash=actual_cash_str,
                    org_id=org_id_str,
                )

            # ── Step 5: Write one audit entry per organisation ────────────
            # Rollup partial daily consolidations per org (final pass after
            # the EOD sweep — will be recomputed as each shift transitions to
            # LOCKED). Uses today_ist because that's the operational day just
            # closed; handled best-effort so a consolidation failure doesn't
            # block the sweep.
            from app.services.reconciliation.daily_consolidation import consolidate_daily

            for org_id_str, _shift_list in org_shift_map.items():
                org_uuid = uuid.UUID(org_id_str)
                try:
                    await consolidate_daily(
                        db,
                        org_id=org_uuid,
                        day=today_ist,
                        tenant_id=await _tenant_from_org(db, org_uuid),
                    )
                except Exception:
                    log.exception(
                        "eod_consolidation_failed", org_id=org_id_str
                    )

            for org_id_str, shift_list in org_shift_map.items():
                await AuditService.log(
                    db,
                    action="eod_reconciliation_sweep",
                    entity_type="organization",
                    entity_id=uuid.UUID(org_id_str),
                    user_id=_SYSTEM_USER_ID,
                    org_id=uuid.UUID(org_id_str),
                    tenant_id=await _tenant_from_org(db, uuid.UUID(org_id_str)),
                    after={
                        "dispatched_shifts": shift_list,
                        "auto_closed": auto_closed,
                        "sweep_date": today_ist.isoformat(),
                    },
                    metadata={
                        "triggered_by": "celery_beat",
                        "sweep_time_ist": now_ist.isoformat(),
                    },
                )

            await db.commit()

            return {
                "status": "dispatched",
                "shifts_queued": len(dispatched),
                "shifts_skipped": len(skipped),
                "auto_closed": auto_closed,
                "triggered_at": now_ist.isoformat(),
            }
    finally:
        await _engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
#  BEAT SCHEDULE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════


def register_eod_schedule() -> None:
    """Register (or update) the EOD reconciliation beat entry.

    23:45 IST — 15 minutes before midnight gives attendants time to
    close out their cash before the date rolls over.
    """
    celery_app.conf.beat_schedule["eod-reconciliation"] = {
        "task": "app.tasks.reconciliation.run_eod_reconciliation",
        "schedule": crontab(hour=23, minute=45),
        "options": {"timezone": "Asia/Kolkata"},
    }
    log.info("eod_schedule_registered", schedule="23:45 IST daily")
