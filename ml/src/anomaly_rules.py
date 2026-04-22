"""PetroLedger ML Sandbox — Rule-Based Anomaly Detection.

Exact port of the backend's ``AnomalyDetectionService`` — same 6 checks
and risk-score calculation.  Uses the standalone :class:`ShiftFeatures`,
returns plain dicts instead of Pydantic ``AnomalyDetail`` models.

⚠️  Throwaway sandbox code — the production backend has its own copy.
"""

from __future__ import annotations

from typing import Any

from .features import ShiftFeatures

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

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "cash_variance_medium": 500.0,
    "cash_variance_high": 2000.0,
    "volume_mismatch_pct": 0.10,
    "txn_spike_multiplier": 3.0,
    "night_variance_multiplier": 1.5,
    "worker_flagged_rate_limit": 0.30,
}


# ── Service ─────────────────────────────────────────────────────────────


class AnomalyRulesService:
    """Stateless, rule-based anomaly detector for shift reconciliation."""

    def detect_anomalies(
        self,
        features: ShiftFeatures,
        threshold_config: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Run all anomaly checks against *features* and return findings.

        Each finding is a plain dict with keys:
        ``type``, ``description``, ``severity``, ``amount``.
        """
        cfg = {**DEFAULT_THRESHOLDS, **(threshold_config or {})}
        anomalies: list[dict[str, Any]] = []

        anomalies.extend(self._check_cash_variance(features, cfg))
        anomalies.extend(self._check_volume_mismatch(features, cfg))
        anomalies.extend(self._check_unusual_transaction(features, cfg))
        anomalies.extend(self._check_night_shift_variance(features, cfg))
        anomalies.extend(self._check_worker_history(features, cfg))
        anomalies.extend(self._check_zero_digital(features))

        return anomalies

    @staticmethod
    def calculate_risk_score(anomalies: list[dict[str, Any]]) -> float:
        """Derive a 0.0–1.0 risk score from the detected anomalies."""
        seen: set[str] = set()
        score = 0.0
        for a in anomalies:
            atype = a["type"]
            if atype not in seen:
                seen.add(atype)
                score += _RISK_WEIGHTS.get(atype, 0.0)
        return min(score, 1.0)

    # ── Individual checks ───────────────────────────────────────────────

    @staticmethod
    def _check_cash_variance(
        features: ShiftFeatures, cfg: dict,
    ) -> list[dict]:
        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount
        cash_variance = abs(expected - digital)

        high_thresh = cfg["cash_variance_high"]
        med_thresh = cfg["cash_variance_medium"]

        if cash_variance > high_thresh:
            severity = "high"
        elif cash_variance > med_thresh:
            severity = "medium"
        else:
            return []

        return [
            {
                "type": CASH_VARIANCE_HIGH,
                "description": (
                    f"Cash variance of ₹{cash_variance:.2f} exceeds "
                    f"{severity} threshold "
                    f"(₹{med_thresh if severity == 'medium' else high_thresh})."
                ),
                "severity": severity,
                "amount": cash_variance,
            }
        ]

    @staticmethod
    def _check_volume_mismatch(
        features: ShiftFeatures, cfg: dict,
    ) -> list[dict]:
        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount

        if expected == 0:
            return []

        mismatch_pct = abs(expected - digital) / expected
        limit = cfg["volume_mismatch_pct"]

        if mismatch_pct <= limit:
            return []

        return [
            {
                "type": VOLUME_MISMATCH,
                "description": (
                    f"Volume-based expected revenue (₹{expected:.2f}) differs from "
                    f"digital payments (₹{digital:.2f}) by {mismatch_pct:.1%}, "
                    f"exceeding the {limit:.0%} threshold. Possible meter tampering."
                ),
                "severity": "high" if mismatch_pct > 2 * limit else "medium",
                "amount": abs(expected - digital),
            }
        ]

    @staticmethod
    def _check_unusual_transaction(
        features: ShiftFeatures, cfg: dict,
    ) -> list[dict]:
        avg = features.avg_transaction_amount
        max_txn = features.max_transaction_amount
        multiplier = cfg["txn_spike_multiplier"]

        if avg == 0 or max_txn <= avg * multiplier:
            return []

        return [
            {
                "type": UNUSUAL_TRANSACTION_PATTERN,
                "description": (
                    f"Largest transaction (₹{max_txn:.2f}) is more than "
                    f"{multiplier}× the average (₹{avg:.2f}). "
                    f"Could indicate an inflated transaction."
                ),
                "severity": "medium",
                "amount": max_txn,
            }
        ]

    @staticmethod
    def _check_night_shift_variance(
        features: ShiftFeatures, cfg: dict,
    ) -> list[dict]:
        if not features.is_night_shift:
            return []

        expected = features.expected_cash_from_volume
        digital = features.total_digital_amount
        cash_variance = abs(expected - digital)

        night_thresh = cfg["cash_variance_medium"] * cfg["night_variance_multiplier"]

        if cash_variance <= night_thresh:
            return []

        return [
            {
                "type": NIGHT_SHIFT_VARIANCE,
                "description": (
                    f"Night-shift cash variance of ₹{cash_variance:.2f} exceeds the "
                    f"adjusted threshold of ₹{night_thresh:.2f} "
                    f"(1.5× daytime). Higher theft risk during night shifts."
                ),
                "severity": "high",
                "amount": cash_variance,
            }
        ]

    @staticmethod
    def _check_worker_history(
        features: ShiftFeatures, cfg: dict,
    ) -> list[dict]:
        rate_limit = cfg["worker_flagged_rate_limit"]

        if features.worker_shift_count == 0:
            return []

        if features.worker_flagged_rate <= rate_limit:
            return []

        return [
            {
                "type": WORKER_HISTORICAL_FLAG,
                "description": (
                    f"Worker has been flagged in {features.worker_flagged_rate:.0%} of "
                    f"their last {features.worker_shift_count} shifts "
                    f"(threshold: {rate_limit:.0%}). Historical pattern of issues."
                ),
                "severity": "medium",
                "amount": None,
            }
        ]

    @staticmethod
    def _check_zero_digital(features: ShiftFeatures) -> list[dict]:
        if features.total_digital_amount != 0:
            return []

        if features.total_volume_dispensed <= 0:
            return []

        return [
            {
                "type": ZERO_DIGITAL_PAYMENTS,
                "description": (
                    f"{features.total_volume_dispensed:.2f} litres dispensed but "
                    f"zero digital payments recorded. All-cash shift with no "
                    f"UPI/POS trail is suspicious."
                ),
                "severity": "high",
                "amount": features.expected_cash_from_volume,
            }
        ]
