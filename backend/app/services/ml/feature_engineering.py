"""PetroLedger — ML Feature Engineering Service.

Extracts structured numeric features from raw shift data (transactions,
pump-logs, worker history) so they can be fed into anomaly-detection and
cash-variance attribution models.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.reconciliation import ReconciliationResult, ReconciliationStatus
from app.models.shift import Shift
from app.models.transaction import POSTransaction, PumpLog, UPITransaction
from app.utils.datetime import get_ist_now, to_ist

logger = logging.getLogger(__name__)

# Placeholder fuel price — will be replaced by a dynamic lookup later.
_DEFAULT_FUEL_PRICE_PER_LITRE = Decimal("100")

# How many past shifts to consider for worker-level features.
_WORKER_HISTORY_WINDOW = 30


# ── Dataclass ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ShiftFeatures:
    """Flat feature vector describing a single shift for ML models."""

    # Identifiers
    shift_id: UUID
    worker_id: UUID
    extracted_at: datetime

    # ── Temporal ────────────────────────────────────────────────────────
    shift_duration_hours: float
    shift_start_hour: int
    is_night_shift: bool
    day_of_week: int

    # ── Transaction ─────────────────────────────────────────────────────
    total_upi_amount: Decimal
    total_pos_amount: Decimal
    total_digital_amount: Decimal
    upi_transaction_count: int
    pos_transaction_count: int
    avg_transaction_amount: Decimal
    max_transaction_amount: Decimal

    # ── Pump / Volume ───────────────────────────────────────────────────
    total_volume_dispensed: Decimal
    expected_cash_from_volume: Decimal
    nozzle_count_active: int

    # ── Worker history ──────────────────────────────────────────────────
    worker_avg_variance: Decimal
    worker_variance_std: Decimal
    worker_shift_count: int
    worker_flagged_rate: float


# ── Service ─────────────────────────────────────────────────────────────


class FeatureEngineeringService:
    """Stateless service that turns raw shift data into :class:`ShiftFeatures`."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_shift_features(
        self,
        shift_id: UUID,
        db: AsyncSession,
    ) -> ShiftFeatures:
        """Load all data for *shift_id* and return a complete feature vector.

        Raises :class:`NotFoundError` when the shift does not exist.
        """
        shift = await self._load_shift(shift_id, db)

        temporal = self._extract_temporal_features(shift)
        transaction = self._extract_transaction_features(
            shift.upi_transactions,
            shift.pos_transactions,
        )
        volume = self._extract_volume_features(shift.pump_logs)
        worker = await self._extract_worker_features(
            shift.worker_id, shift_id, db,
        )

        return ShiftFeatures(
            shift_id=shift.id,
            worker_id=shift.worker_id,
            extracted_at=get_ist_now(),
            **temporal,
            **transaction,
            **volume,
            **worker,
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_shift(shift_id: UUID, db: AsyncSession) -> Shift:
        """Eagerly load a shift with all relationships needed for features."""
        stmt = (
            select(Shift)
            .where(Shift.id == shift_id)
            .options(
                selectinload(Shift.upi_transactions),
                selectinload(Shift.pos_transactions),
                selectinload(Shift.pump_logs),
            )
        )
        result = await db.execute(stmt)
        shift = result.scalar_one_or_none()
        if shift is None:
            raise NotFoundError(resource="Shift", identifier=str(shift_id))
        return shift

    # ------------------------------------------------------------------
    # Temporal features
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_temporal_features(shift: Shift) -> dict:
        start_ist = to_ist(shift.start_time)
        end_ist = to_ist(shift.end_time) if shift.end_time else get_ist_now()

        duration_seconds = (end_ist - start_ist).total_seconds()
        duration_hours = max(duration_seconds / 3600.0, 0.0)

        start_hour = start_ist.hour
        # Night shift: start hour in [22, 23] or [0, 5] (i.e. 22:00‑05:59)
        is_night = start_hour >= 22 or start_hour < 6

        return {
            "shift_duration_hours": round(duration_hours, 4),
            "shift_start_hour": start_hour,
            "is_night_shift": is_night,
            "day_of_week": start_ist.weekday(),
        }

    # ------------------------------------------------------------------
    # Transaction features
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_transaction_features(
        upi_txns: Sequence[UPITransaction],
        pos_txns: Sequence[POSTransaction],
    ) -> dict:
        upi_amounts = [Decimal(str(t.amount)) for t in upi_txns]
        pos_amounts = [Decimal(str(t.amount)) for t in pos_txns]
        all_amounts = upi_amounts + pos_amounts

        total_upi = sum(upi_amounts, Decimal("0"))
        total_pos = sum(pos_amounts, Decimal("0"))
        total_digital = total_upi + total_pos

        count_upi = len(upi_amounts)
        count_pos = len(pos_amounts)
        total_count = count_upi + count_pos

        avg_amount = (
            (total_digital / total_count) if total_count > 0 else Decimal("0")
        )
        max_amount = max(all_amounts) if all_amounts else Decimal("0")

        return {
            "total_upi_amount": total_upi,
            "total_pos_amount": total_pos,
            "total_digital_amount": total_digital,
            "upi_transaction_count": count_upi,
            "pos_transaction_count": count_pos,
            "avg_transaction_amount": avg_amount.quantize(Decimal("0.01")),
            "max_transaction_amount": max_amount,
        }

    # ------------------------------------------------------------------
    # Pump / Volume features
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_volume_features(pump_logs: Sequence[PumpLog]) -> dict:
        volumes = [Decimal(str(p.volume_dispensed)) for p in pump_logs]
        total_volume = sum(volumes, Decimal("0"))
        expected_cash = total_volume * _DEFAULT_FUEL_PRICE_PER_LITRE

        # Distinct nozzles that recorded readings in this shift.
        active_nozzles = {p.nozzle_id for p in pump_logs}

        return {
            "total_volume_dispensed": total_volume,
            "expected_cash_from_volume": expected_cash,
            "nozzle_count_active": len(active_nozzles),
        }

    # ------------------------------------------------------------------
    # Worker history features
    # ------------------------------------------------------------------

    @staticmethod
    async def _extract_worker_features(
        worker_id: UUID,
        current_shift_id: UUID,
        db: AsyncSession,
    ) -> dict:
        """Compute rolling statistics over the worker's last N reconciled shifts.

        Only shifts *other* than ``current_shift_id`` are included so we
        never leak the target variable into the feature set.
        """
        # Sub-query: the worker's most recent reconciled shifts (excluding current).
        stmt = (
            select(ReconciliationResult.variance, ReconciliationResult.status)
            .join(Shift, ReconciliationResult.shift_id == Shift.id)
            .where(
                Shift.worker_id == worker_id,
                Shift.id != current_shift_id,
                ReconciliationResult.status.in_([
                    ReconciliationStatus.COMPLETED,
                    ReconciliationStatus.FLAGGED,
                ]),
            )
            .order_by(Shift.start_time.desc())
            .limit(_WORKER_HISTORY_WINDOW)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return {
                "worker_avg_variance": Decimal("0"),
                "worker_variance_std": Decimal("0"),
                "worker_shift_count": 0,
                "worker_flagged_rate": 0.0,
            }

        variances = [Decimal(str(r.variance)) for r in rows]
        statuses = [r.status for r in rows]
        n = len(variances)

        avg_var = sum(variances, Decimal("0")) / n

        # Population standard deviation (we have the full window, not a sample).
        if n > 1:
            sum_sq = sum((v - avg_var) ** 2 for v in variances)
            std_var = Decimal(str(math.sqrt(float(sum_sq / n))))
        else:
            std_var = Decimal("0")

        flagged_count = sum(
            1 for s in statuses if s == ReconciliationStatus.FLAGGED
        )

        return {
            "worker_avg_variance": avg_var.quantize(Decimal("0.01")),
            "worker_variance_std": std_var.quantize(Decimal("0.01")),
            "worker_shift_count": n,
            "worker_flagged_rate": round(flagged_count / n, 4),
        }
