"""PetroLedger — Anomaly Detection Service.

Rule-based detector that flags suspicious shift patterns.  Each rule
produces zero or one :class:`AnomalyDetail` entries; the full list is
then scored by :meth:`calculate_risk_score` to yield a 0–1 risk value
consumed downstream by the reconciliation engine.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.schemas.reconciliation import AnomalyDetail
from app.services.ml.feature_engineering import ShiftFeatures

logger = logging.getLogger(__name__)


# ── Anomaly type constants ──────────────────────────────────────────────

CASH_VARIANCE_HIGH = "CASH_VARIANCE_HIGH"
VOLUME_MISMATCH = "VOLUME_MISMATCH"
UNUSUAL_TRANSACTION_PATTERN = "UNUSUAL_TRANSACTION_PATTERN"
NIGHT_SHIFT_VARIANCE = "NIGHT_SHIFT_VARIANCE"
WORKER_HISTORICAL_FLAG = "WORKER_HISTORICAL_FLAG"
ZERO_DIGITAL_PAYMENTS = "ZERO_DIGITAL_PAYMENTS"


# ── Risk-score weights per anomaly type ─────────────────────────────────

_RISK_WEIGHTS: dict[str, float] = {
    CASH_VARIANCE_HIGH: 0.40,
    VOLUME_MISMATCH: 0.30,
    UNUSUAL_TRANSACTION_PATTERN: 0.15,
    NIGHT_SHIFT_VARIANCE: 0.10,
    WORKER_HISTORICAL_FLAG: 0.20,
    ZERO_DIGITAL_PAYMENTS: 0.25,
}


# ── Default thresholds ──────────────────────────────────────────────────

_DEFAULT_THRESHOLDS: dict[str, Any] = {
    # Cash variance
    "cash_variance_medium": Decimal("500"),
    "cash_variance_high": Decimal("2000"),
    # Volume mismatch (fraction)
    "volume_mismatch_pct": Decimal("0.10"),
    # Unusual single-transaction multiplier
    "txn_spike_multiplier": Decimal("3"),
    # Night-shift variance multiplier applied to the medium threshold
    "night_variance_multiplier": Decimal("1.5"),
    # Worker history flagged-rate ceiling
    "worker_flagged_rate_limit": 0.30,
}


# ── Service ─────────────────────────────────────────────────────────────


class AnomalyDetectionService:
    """Stateless, rule-based anomaly detector for shift reconciliation."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_anomalies(
        self,
        features: ShiftFeatures,
        threshold_config: dict | None = None,
    ) -> list[AnomalyDetail]:
        """Run all anomaly checks against *features* and return findings.

        *threshold_config* can override any key present in the default
        threshold dict; unset keys fall back to built-in defaults.
        """
        cfg = {**_DEFAULT_THRESHOLDS, **(threshold_config or {})}

        anomalies: list[AnomalyDetail] = []

        anomalies.extend(self._check_cash_variance(features, cfg))
        anomalies.extend(self._check_volume_mismatch(features, cfg))
        anomalies.extend(self._check_unusual_transaction(features, cfg))
        anomalies.extend(self._check_night_shift_variance(features, cfg))
        anomalies.extend(self._check_worker_history(features, cfg))
        anomalies.extend(self._check_zero_digital(features))

        if anomalies:
            logger.info(
                "Shift %s: %d anomalies detected",
                features.shift_id, len(anomalies),
            )

        return anomalies

    @staticmethod
    def calculate_risk_score(anomalies: list[AnomalyDetail]) -> float:
        """Derive a 0.0–1.0 risk score from the detected anomalies.

        Each anomaly type carries a fixed weight; the score is the sum of
        weights for all *distinct* anomaly types present, clamped to 1.0.
        """
        seen_types: set[str] = set()
        score = 0.0
        for a in anomalies:
            if a.type not in seen_types:
                seen_types.add(a.type)
                score += _RISK_WEIGHTS.get(a.type, 0.0)
        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Individual anomaly checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_cash_variance(
        features: ShiftFeatures, cfg: dict,
    ) -> list[AnomalyDetail]:
        """CASH_VARIANCE_HIGH — actual cash deviates from expected."""
        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount
        cash_variance = abs(expected - digital)

        high_thresh = Decimal(str(cfg["cash_variance_high"]))
        med_thresh = Decimal(str(cfg["cash_variance_medium"]))

        if cash_variance > high_thresh:
            severity = "high"
        elif cash_variance > med_thresh:
            severity = "medium"
        else:
            return []

        return [
            AnomalyDetail(
                type=CASH_VARIANCE_HIGH,
                description=(
                    f"Cash variance of \u20b9{cash_variance:.2f} exceeds "
                    f"{severity} threshold (\u20b9{med_thresh if severity == 'medium' else high_thresh})."
                ),
                severity=severity,
                amount=cash_variance,
            )
        ]

    @staticmethod
    def _check_volume_mismatch(
        features: ShiftFeatures, cfg: dict,
    ) -> list[AnomalyDetail]:
        """VOLUME_MISMATCH — pump-log volume doesn't align with payments."""
        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount

        if expected == 0:
            return []

        mismatch_pct = abs(expected - digital) / expected
        limit = Decimal(str(cfg["volume_mismatch_pct"]))

        if mismatch_pct <= limit:
            return []

        return [
            AnomalyDetail(
                type=VOLUME_MISMATCH,
                description=(
                    f"Volume-based expected revenue (\u20b9{expected:.2f}) differs from "
                    f"digital payments (\u20b9{digital:.2f}) by {mismatch_pct:.1%}, "
                    f"exceeding the {limit:.0%} threshold. Possible meter tampering."
                ),
                severity="high" if mismatch_pct > 2 * limit else "medium",
                amount=abs(expected - digital),
            )
        ]

    @staticmethod
    def _check_unusual_transaction(
        features: ShiftFeatures, cfg: dict,
    ) -> list[AnomalyDetail]:
        """UNUSUAL_TRANSACTION_PATTERN — single txn far above average."""
        avg = features.avg_transaction_amount
        max_txn = features.max_transaction_amount
        multiplier = Decimal(str(cfg["txn_spike_multiplier"]))

        if avg == 0 or max_txn <= avg * multiplier:
            return []

        return [
            AnomalyDetail(
                type=UNUSUAL_TRANSACTION_PATTERN,
                description=(
                    f"Largest transaction (\u20b9{max_txn:.2f}) is more than "
                    f"{multiplier}\u00d7 the average (\u20b9{avg:.2f}). "
                    f"Could indicate an inflated transaction."
                ),
                severity="medium",
                amount=max_txn,
            )
        ]

    @staticmethod
    def _check_night_shift_variance(
        features: ShiftFeatures, cfg: dict,
    ) -> list[AnomalyDetail]:
        """NIGHT_SHIFT_VARIANCE — higher-risk variance on night shifts."""
        if not features.is_night_shift:
            return []

        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount
        cash_variance = abs(expected - digital)

        night_thresh = Decimal(str(cfg["cash_variance_medium"])) * Decimal(
            str(cfg["night_variance_multiplier"])
        )

        if cash_variance <= night_thresh:
            return []

        return [
            AnomalyDetail(
                type=NIGHT_SHIFT_VARIANCE,
                description=(
                    f"Night-shift cash variance of \u20b9{cash_variance:.2f} exceeds the "
                    f"adjusted threshold of \u20b9{night_thresh:.2f} "
                    f"(1.5\u00d7 daytime). Higher theft risk during night shifts."
                ),
                severity="high",
                amount=cash_variance,
            )
        ]

    @staticmethod
    def _check_worker_history(
        features: ShiftFeatures, cfg: dict,
    ) -> list[AnomalyDetail]:
        """WORKER_HISTORICAL_FLAG — worker has a pattern of flagged shifts."""
        rate_limit = float(cfg["worker_flagged_rate_limit"])

        if features.worker_shift_count == 0:
            return []

        if features.worker_flagged_rate <= rate_limit:
            return []

        return [
            AnomalyDetail(
                type=WORKER_HISTORICAL_FLAG,
                description=(
                    f"Worker has been flagged in {features.worker_flagged_rate:.0%} of "
                    f"their last {features.worker_shift_count} shifts "
                    f"(threshold: {rate_limit:.0%}). Historical pattern of issues."
                ),
                severity="medium",
                amount=None,
            )
        ]

    @staticmethod
    def _check_zero_digital(features: ShiftFeatures) -> list[AnomalyDetail]:
        """ZERO_DIGITAL_PAYMENTS — fuel dispensed but no digital trace."""
        if features.total_digital_amount != 0:
            return []

        if features.total_volume_dispensed <= 0:
            return []

        return [
            AnomalyDetail(
                type=ZERO_DIGITAL_PAYMENTS,
                description=(
                    f"{features.total_volume_dispensed:.2f} litres dispensed but "
                    f"zero digital payments recorded. All-cash shift with no "
                    f"UPI/POS trail is suspicious."
                ),
                severity="high",
                amount=features.expected_cash_from_volume,
            )
        ]
