"""PetroLedger — Reconciliation API Routes.

GET  /reconciliation/shifts/{shift_id}         — fetch existing result
POST /reconciliation/shifts/{shift_id}/run     — trigger reconciliation
"""

from __future__ import annotations

from uuid import UUID

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift, ShiftStatus
from app.models.user import User, UserRole
from app.models.nozzle_meter_reading import NozzleMeterReading
from app.models.nozzle_shift_sale import NozzleShiftSale
from app.models.reconciliation import (
    ReconciliationResult,
    ReconciliationStatus,
    VarianceReason,
)
from app.schemas.meter_reading import PerWorkerReconciliationResponse
from app.schemas.reconciliation import ReconciliationRequest, ReconciliationResponse
from app.services.reconciliation.engine import ReconciliationEngine
from app.services.reconciliation.per_worker import reconcile_per_worker

router = APIRouter()

_engine = ReconciliationEngine()


class VarianceReasonPatch(BaseModel):
    reason: VarianceReason
    notes: str | None = Field(default=None, max_length=2000)


@router.patch(
    "/{result_id}/variance-reason",
    response_model=ReconciliationResponse,
    summary="Classify a variance with a reason code (OWNER + ADMIN only)",
)
async def set_variance_reason(
    result_id: UUID,
    payload: VarianceReasonPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> ReconciliationResponse:
    """Persist an owner's classification of why a shift's variance occurred.

    Rejected once the parent shift is LOCKED — the reconciliation is
    frozen and cannot be re-annotated.
    """
    result = (
        await db.execute(
            select(ReconciliationResult).where(ReconciliationResult.id == result_id)
        )
    ).scalar_one_or_none()
    if result is None:
        raise NotFoundError(resource="ReconciliationResult", identifier=result_id)

    shift = await _verify_shift_tenant_access(result.shift_id, current_user, db)

    if shift.status == ShiftStatus.LOCKED:
        raise ValidationError(
            "Shift is LOCKED — the variance reason can no longer be changed."
        )

    from app.services.audit import AuditService

    before = {
        "variance_reason": result.variance_reason,
        "variance_notes": result.variance_notes,
    }
    result.variance_reason = payload.reason.value
    result.variance_notes = payload.notes
    result.reason_set_by_user_id = current_user.id
    result.reason_set_at = datetime.now(UTC)
    await db.flush()

    # Resolve org via shift→pump for audit scoping.
    from app.models.pump import Pump as _Pump
    pump_row = (
        await db.execute(select(_Pump).where(_Pump.id == shift.pump_id))
    ).scalar_one_or_none()
    org_id_for_audit = pump_row.org_id if pump_row is not None else current_user.org_id
    if org_id_for_audit is not None:
        await AuditService.log_event(
            db,
            user=current_user,
            action="reconciliation.variance_reason_set",
            entity_type="ReconciliationResult",
            entity_id=result.id,
            org_id=org_id_for_audit,
            before=before,
            after={
                "variance_reason": result.variance_reason,
                "variance_notes": result.variance_notes,
            },
        )
    await db.refresh(result)
    await db.commit()

    return await _engine.get_result(result.shift_id, db)


# ── GET /shifts/{shift_id} — fetch existing reconciliation ───────────────────


@router.get(
    "/shifts/{shift_id}",
    response_model=ReconciliationResponse,
    summary="Get reconciliation result for a shift",
)
async def get_reconciliation(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ReconciliationResponse:
    """Return the most recent reconciliation result for *shift_id*.

    Raises **404** if the shift has not been reconciled yet.
    """
    await _verify_shift_tenant_access(shift_id, current_user, db)
    return await _engine.get_result(shift_id, db)


# ── POST /shifts/{shift_id}/run — trigger reconciliation ─────────────────────


@router.post(
    "/shifts/{shift_id}/run",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run reconciliation for a shift",
)
async def run_reconciliation(
    shift_id: UUID,
    payload: ReconciliationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> ReconciliationResponse:
    """Trigger cash reconciliation for *shift_id*.

    - Computes expected cash from FMS transactions.
    - Deducts UPI, card, and fleet payments.
    - Compares against *actual_cash* submitted in the request body.
    - Runs anomaly detection and confidence scoring.
    - Persists the result (idempotent — re-running overwrites the previous result).
    - Advances shift status to **RECONCILED** on success.

    The shift must be in **COMPLETED** state before reconciliation can run.
    """
    await _verify_shift_tenant_access(shift_id, current_user, db)

    # Engine call is UNCHANGED — only tenant verification was added above
    return await _engine.reconcile(
        shift_id=shift_id,
        actual_cash=payload.actual_cash,
        db=db,
    )


# ── GET /shifts/{shift_id}/per-worker — fetch existing per-worker results ────


@router.get(
    "/shifts/{shift_id}/per-worker",
    response_model=PerWorkerReconciliationResponse,
    summary="Get per-worker reconciliation results for a shift",
)
async def get_per_worker_reconciliation(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PerWorkerReconciliationResponse:
    """Return cached per-worker reconciliation results for *shift_id*.

    This re-computes the per-worker breakdown from the existing
    ``nozzle_shift_sales`` and ``cash_entries`` data (stateless read).
    Raises **400** if no meter readings exist for the shift.
    """
    await _verify_shift_tenant_access(shift_id, current_user, db)
    results = await reconcile_per_worker(shift_id, db)

    from decimal import ROUND_HALF_UP, Decimal as _Decimal
    _TWO = _Decimal("0.01")
    total_sale = sum(r.shift_sale_amount for r in results)
    total_variance = sum(r.variance for r in results)

    return PerWorkerReconciliationResponse(
        shift_id=shift_id,
        results=results,
        total_shift_sale=total_sale.quantize(_TWO, rounding=ROUND_HALF_UP),
        total_variance=total_variance.quantize(_TWO, rounding=ROUND_HALF_UP),
    )


# ── POST /shifts/{shift_id}/run-per-worker ───────────────────────────────────


@router.post(
    "/shifts/{shift_id}/run-per-worker",
    response_model=PerWorkerReconciliationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run per-worker reconciliation using meter readings",
)
async def run_per_worker_reconciliation(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> PerWorkerReconciliationResponse:
    """Run per-nozzle/worker reconciliation using ETOT meter reading data.

    Requires both opening and closing readings for every nozzle in the shift.
    Returns one result per nozzle with individual variance and MATCH/SHORTAGE/EXCESS status.
    Persists an aggregate result in ``reconciliation_results`` tagged as ``per_worker``.
    """
    await _verify_shift_tenant_access(shift_id, current_user, db)

    # Check all nozzles have complete readings before running
    incomplete_stmt = (
        select(
            NozzleMeterReading.nozzle_id,
            func.count(NozzleMeterReading.id).label("cnt"),
        )
        .where(NozzleMeterReading.shift_id == shift_id)
        .group_by(NozzleMeterReading.nozzle_id)
    )
    reading_counts = (await db.execute(incomplete_stmt)).all()

    incomplete_nozzle_ids = {row.nozzle_id for row in reading_counts if row.cnt < 2}

    if incomplete_nozzle_ids:
        from app.models.pump import Nozzle as _Nozzle

        num_stmt = select(_Nozzle.nozzle_number).where(
            _Nozzle.id.in_(incomplete_nozzle_ids)
        )
        missing_nums = sorted((await db.execute(num_stmt)).scalars().all())
        raise ValidationError(
            message=(
                f"Cannot reconcile. Missing readings for nozzles: {missing_nums}. "
                f"Submit both opening and closing receipts for all nozzles first."
            )
        )

    # Also check we have at least one nozzle_shift_sale (i.e. some readings exist)
    has_sales = (
        await db.execute(
            select(NozzleShiftSale.id).where(
                NozzleShiftSale.shift_id == shift_id
            ).limit(1)
        )
    ).scalar_one_or_none()
    if has_sales is None:
        raise ValidationError(
            message="No meter readings found for this shift. Upload opening and closing receipts first."
        )

    results = await reconcile_per_worker(shift_id, db)

    # Persist aggregate result in reconciliation_results
    from decimal import ROUND_HALF_UP, Decimal as _Decimal
    _TWO = _Decimal("0.01")
    total_sale = sum(r.shift_sale_amount for r in results)
    total_variance = sum(r.variance for r in results)
    total_cash = sum(r.actual_cash for r in results)
    expected_total = (total_sale).quantize(_TWO, rounding=ROUND_HALF_UP)
    variance_q = total_variance.quantize(_TWO, rounding=ROUND_HALF_UP)

    existing_stmt = select(ReconciliationResult).where(
        ReconciliationResult.shift_id == shift_id
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is not None:
        existing.expected_cash = expected_total
        existing.actual_cash = total_cash.quantize(_TWO, rounding=ROUND_HALF_UP)
        existing.variance = variance_q
        existing.status = ReconciliationStatus.COMPLETED
        existing.reconciliation_type = "per_worker"
        await db.flush()
    else:
        recon = ReconciliationResult(
            shift_id=shift_id,
            expected_cash=expected_total,
            actual_cash=total_cash.quantize(_TWO, rounding=ROUND_HALF_UP),
            variance=variance_q,
            status=ReconciliationStatus.COMPLETED,
            reconciliation_type="per_worker",
        )
        db.add(recon)
        await db.flush()

    return PerWorkerReconciliationResponse(
        shift_id=shift_id,
        results=results,
        total_shift_sale=total_sale.quantize(_TWO, rounding=ROUND_HALF_UP),
        total_variance=variance_q,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _verify_shift_tenant_access(
    shift_id: UUID, current_user: User, db: AsyncSession
) -> Shift:
    """Resolve shift → pump → org and verify the org belongs to the user's tenant."""
    shift_row = (
        await db.execute(select(Shift).where(Shift.id == shift_id))
    ).scalar_one_or_none()
    if shift_row is None:
        raise NotFoundError(resource="Shift", identifier=shift_id)

    pump_row = (
        await db.execute(select(Pump).where(Pump.id == shift_row.pump_id))
    ).scalar_one_or_none()
    if pump_row is None:
        raise NotFoundError(resource="Pump", identifier=shift_row.pump_id)

    org_row = (
        await db.execute(select(Organization).where(Organization.id == pump_row.org_id))
    ).scalar_one_or_none()
    if org_row is None:
        raise NotFoundError(resource="Organization", identifier=pump_row.org_id)

    verify_tenant_match(org_row.tenant_id, current_user)
    return shift_row
