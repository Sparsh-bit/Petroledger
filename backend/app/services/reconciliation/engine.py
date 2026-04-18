"""PetroLedger — Reconciliation Engine.

Implements the core cash reconciliation formula for Indian petrol pumps:

    FMS Total   = SUM(fms_transactions.amount)
                  WHERE shift_id = ? AND status = COMPLETED AND is_deleted = false

    UPI Total   = SUM(upi_transactions.amount)
                  WHERE shift_id = ?

    Card Total  = SUM(pos_batch_settlements.gross_amount)
                  WHERE shift_id = ? AND is_deleted = false

    Fleet Total = SUM(fleet_transactions.total_amount)
                  WHERE shift_id = ? AND is_deleted = false

    Expected Cash = FMS Total - UPI Total - Card Total - Fleet Total
    Actual Cash   = SUM(cash_entries.physical_cash)
                    WHERE shift_id = ? AND is_deleted = false
    Variance      = Expected Cash - Actual Cash

A positive variance means the attendant turned in LESS cash than expected
(shortage).  A negative variance means the attendant turned in MORE (excess).

The engine also:
  • Runs anomaly detection (AnomalyDetectionService)
  • Runs confidence scoring (ConfidenceScoringService + FeatureEngineeringService)
  • Persists a ReconciliationResult row (upsert — idempotent)
  • Updates Shift.status → RECONCILED on success
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.fms import (
    FleetTransaction,
    FmsTransaction,
    FmsTxnStatus,
    PosBatchSettlement,
)
from app.models.reconciliation import ReconciliationResult, ReconciliationStatus
from app.models.shift import Shift, ShiftStatus
from app.models.transaction import UPITransaction
from app.schemas.reconciliation import (
    AnomalyDetail,
    ConfidenceBreakdown,
    ReconciliationResponse,
)
from app.services.ml.feature_engineering import FeatureEngineeringService
from app.services.reconciliation.anomaly import AnomalyDetectionService
from app.services.reconciliation.confidence import ConfidenceScoringService

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")
_FOUR_PLACES = Decimal("0.0001")


class ReconciliationEngine:
    """Stateless service.  Call :meth:`reconcile` to run a full reconciliation."""

    def __init__(self) -> None:
        self._anomaly_svc = AnomalyDetectionService()
        self._confidence_svc = ConfidenceScoringService()
        self._feature_svc = FeatureEngineeringService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def reconcile(
        self,
        shift_id: UUID,
        actual_cash: Decimal,
        db: AsyncSession,
    ) -> ReconciliationResponse:
        """Run reconciliation for *shift_id* and persist the result.

        Parameters
        ----------
        shift_id:
            UUID of the shift to reconcile.
        actual_cash:
            Physical cash counted and submitted by the shift in-charge (₹).
            This overrides any existing ``cash_entries`` aggregate — it is
            the value the operator explicitly confirms when triggering
            reconciliation via the API.
        db:
            Async database session (transaction managed by the caller /
            FastAPI dependency).

        Returns
        -------
        ReconciliationResponse
            The persisted reconciliation result.

        Raises
        ------
        NotFoundError
            When the shift does not exist.
        ValidationError
            When the shift is still ACTIVE (must be COMPLETED first).
        ReconciliationError
            On any unrecoverable computation error.
        """
        shift = await self._load_shift(shift_id, db)

        if shift.status == ShiftStatus.ACTIVE:
            raise ValidationError(
                "Shift must be COMPLETED before reconciliation. "
                "Close the shift first (PATCH /shifts/{id}/status)."
            )

        # ── 1. Compute formula totals ────────────────────────────────────
        fms_total = await self._sum_fms(shift_id, db)
        upi_total = await self._sum_upi(shift_id, db)
        card_total = await self._sum_card(shift_id, db)
        fleet_total = await self._sum_fleet(shift_id, db)
        grade_breakdown = await self._fms_grade_breakdown(shift_id, db)

        expected_cash = (fms_total - upi_total - card_total - fleet_total).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )
        actual_cash_q = actual_cash.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        variance = (expected_cash - actual_cash_q).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )

        logger.info(
            "Reconciliation totals | shift=%s fms=%.2f upi=%.2f card=%.2f "
            "fleet=%.2f expected=%.2f actual=%.2f variance=%.2f",
            shift_id,
            fms_total,
            upi_total,
            card_total,
            fleet_total,
            expected_cash,
            actual_cash_q,
            variance,
        )

        # ── 2. Anomaly detection ─────────────────────────────────────────
        try:
            features = await self._feature_svc.extract_shift_features(shift_id, db)
            anomalies = self._anomaly_svc.detect_anomalies(features)
        except Exception:
            logger.exception("Anomaly detection failed | shift=%s", shift_id)
            anomalies = []
            features = None

        # ── 3. Confidence scoring ────────────────────────────────────────
        breakdown: ConfidenceBreakdown | None = None
        confidence_score_db: Decimal | None = None

        if features is not None:
            try:
                breakdown = self._confidence_svc.calculate_confidence(
                    features, anomalies, variance
                )
                # DB column is NUMERIC(5,4) → store as fraction 0.0000–1.0000
                confidence_score_db = (
                    Decimal(str(breakdown.overall_score)) / Decimal("100")
                ).quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)
            except Exception:
                logger.exception("Confidence scoring failed | shift=%s", shift_id)

        # ── 4. Determine status ──────────────────────────────────────────
        has_critical = any(a.severity in ("high", "critical") for a in anomalies)
        recon_status = ReconciliationStatus.FLAGGED if has_critical else ReconciliationStatus.COMPLETED

        # ── 5. Persist (upsert) ──────────────────────────────────────────
        result = await self._upsert_result(
            shift_id=shift_id,
            expected_cash=expected_cash,
            actual_cash=actual_cash_q,
            variance=variance,
            confidence_score=confidence_score_db,
            status=recon_status,
            anomalies=[a.model_dump() for a in anomalies],
            grade_breakdown=grade_breakdown,
            db=db,
        )

        # ── 6. Advance shift status ──────────────────────────────────────
        # COMPLETED / RECONCILED / REJECTED → PENDING_APPROVAL once a
        # reconciliation result exists so an OWNER must sign off before
        # the shift is LOCKED.
        if shift.status in (
            ShiftStatus.COMPLETED,
            ShiftStatus.RECONCILED,
            ShiftStatus.REJECTED,
        ):
            shift.status = ShiftStatus.PENDING_APPROVAL
            await db.flush()

        await db.refresh(result)

        logger.info(
            "Reconciliation complete | shift=%s status=%s variance=%.2f confidence=%s",
            shift_id,
            recon_status.value,
            variance,
            breakdown.overall_score if breakdown else "n/a",
        )

        return ReconciliationResponse(
            id=result.id,
            shift_id=result.shift_id,
            expected_cash=result.expected_cash,
            actual_cash=result.actual_cash,
            variance=result.variance,
            confidence_score=result.confidence_score,
            confidence_breakdown=breakdown,
            status=result.status,
            anomalies=anomalies,
            grade_breakdown=result.grade_breakdown,
            variance_reason=result.variance_reason,
            variance_notes=result.variance_notes,
            reason_set_by_user_id=result.reason_set_by_user_id,
            reason_set_at=result.reason_set_at,
            created_at=result.created_at,
        )

    async def get_result(
        self,
        shift_id: UUID,
        db: AsyncSession,
    ) -> ReconciliationResponse:
        """Return the existing reconciliation result for *shift_id*.

        Raises :class:`NotFoundError` if the shift has not been reconciled.
        """
        stmt = select(ReconciliationResult).where(
            ReconciliationResult.shift_id == shift_id
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                resource="ReconciliationResult",
                identifier=str(shift_id),
                message=f"Shift {shift_id} has not been reconciled yet.",
            )

        anomalies_raw: list[dict] = row.anomalies or []
        anomalies = [AnomalyDetail(**a) for a in anomalies_raw]

        return ReconciliationResponse(
            id=row.id,
            shift_id=row.shift_id,
            expected_cash=row.expected_cash,
            actual_cash=row.actual_cash,
            variance=row.variance,
            confidence_score=row.confidence_score,
            confidence_breakdown=None,  # breakdown not stored; recompute if needed
            status=row.status,
            anomalies=anomalies,
            grade_breakdown=row.grade_breakdown,
            variance_reason=row.variance_reason,
            variance_notes=row.variance_notes,
            reason_set_by_user_id=row.reason_set_by_user_id,
            reason_set_at=row.reason_set_at,
            created_at=row.created_at,
        )

    # ------------------------------------------------------------------
    # Formula helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _sum_fms(shift_id: UUID, db: AsyncSession) -> Decimal:
        """FMS Total: completed, non-deleted, SALE-only FMS transactions.

        Non-SALE subtypes (pump tests, calibrations, spillage, tank
        transfers) are operational fuel movements — they reduce inventory
        but didn't collect cash, so they must not inflate expected_cash.
        """
        stmt = select(func.coalesce(func.sum(FmsTransaction.amount), 0)).where(
            FmsTransaction.shift_id == shift_id,
            FmsTransaction.status == FmsTxnStatus.COMPLETED,
            FmsTransaction.is_deleted.is_(False),
            FmsTransaction.subtype == "SALE",
        )
        raw = (await db.execute(stmt)).scalar_one()
        return Decimal(str(raw))

    @staticmethod
    async def _fms_grade_breakdown(
        shift_id: UUID, db: AsyncSession
    ) -> dict[str, dict[str, str]]:
        """Return {product_code: {volume_litres, amount, unit_price}} for a shift.

        `unit_price` is the volume-weighted average for the grade (or "0" when no
        volume was dispensed — defensive only; the aggregation filters on
        COMPLETED rows). All values are serialised as strings so the JSONB
        column preserves Decimal precision without float coercion.
        """
        stmt = (
            select(
                FmsTransaction.product_code,
                func.coalesce(func.sum(FmsTransaction.volume_litres), 0).label("volume"),
                func.coalesce(func.sum(FmsTransaction.amount), 0).label("amount"),
            )
            .where(
                FmsTransaction.shift_id == shift_id,
                FmsTransaction.status == FmsTxnStatus.COMPLETED,
                FmsTransaction.is_deleted.is_(False),
                FmsTransaction.subtype == "SALE",
            )
            .group_by(FmsTransaction.product_code)
        )
        rows = (await db.execute(stmt)).all()

        breakdown: dict[str, dict[str, str]] = {}
        for row in rows:
            code = row.product_code or "UNKNOWN"
            volume = Decimal(str(row.volume))
            amount = Decimal(str(row.amount))
            unit_price = (
                (amount / volume).quantize(Decimal("0.0001"))
                if volume > 0
                else Decimal("0")
            )
            breakdown[code] = {
                "volume_litres": str(volume),
                "amount": str(amount.quantize(Decimal("0.01"))),
                "unit_price": str(unit_price),
            }
        return breakdown

    @staticmethod
    async def _sum_upi(shift_id: UUID, db: AsyncSession) -> Decimal:
        """UPI Total: sum of all UPI transactions for the shift."""
        stmt = select(func.coalesce(func.sum(UPITransaction.amount), 0)).where(
            UPITransaction.shift_id == shift_id,
        )
        raw = (await db.execute(stmt)).scalar_one()
        return Decimal(str(raw))

    @staticmethod
    async def _sum_card(shift_id: UUID, db: AsyncSession) -> Decimal:
        """Card Total: sum of non-deleted POS batch settlements."""
        stmt = select(func.coalesce(func.sum(PosBatchSettlement.gross_amount), 0)).where(
            PosBatchSettlement.shift_id == shift_id,
            PosBatchSettlement.is_deleted.is_(False),
        )
        raw = (await db.execute(stmt)).scalar_one()
        return Decimal(str(raw))

    @staticmethod
    async def _sum_fleet(shift_id: UUID, db: AsyncSession) -> Decimal:
        """Fleet Total: sum of non-deleted fleet transactions."""
        stmt = select(func.coalesce(func.sum(FleetTransaction.total_amount), 0)).where(
            FleetTransaction.shift_id == shift_id,
            FleetTransaction.is_deleted.is_(False),
        )
        raw = (await db.execute(stmt)).scalar_one()
        return Decimal(str(raw))

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_shift(shift_id: UUID, db: AsyncSession) -> Shift:
        stmt = select(Shift).where(Shift.id == shift_id)
        shift = (await db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise NotFoundError(resource="Shift", identifier=str(shift_id))
        return shift

    @staticmethod
    async def _upsert_result(
        *,
        shift_id: UUID,
        expected_cash: Decimal,
        actual_cash: Decimal,
        variance: Decimal,
        confidence_score: Decimal | None,
        status: ReconciliationStatus,
        anomalies: list[dict],
        grade_breakdown: dict[str, dict[str, str]] | None,
        db: AsyncSession,
    ) -> ReconciliationResult:
        """Insert or update the ReconciliationResult for the shift."""
        stmt = select(ReconciliationResult).where(
            ReconciliationResult.shift_id == shift_id
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            existing.expected_cash = expected_cash
            existing.actual_cash = actual_cash
            existing.variance = variance
            existing.confidence_score = confidence_score
            existing.status = status
            existing.anomalies = anomalies
            existing.grade_breakdown = grade_breakdown
            await db.flush()
            return existing

        result = ReconciliationResult(
            shift_id=shift_id,
            expected_cash=expected_cash,
            actual_cash=actual_cash,
            variance=variance,
            confidence_score=confidence_score,
            status=status,
            anomalies=anomalies,
            grade_breakdown=grade_breakdown,
        )
        db.add(result)
        await db.flush()
        return result
