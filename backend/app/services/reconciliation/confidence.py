"""PetroLedger — Confidence Scoring Service.

Produces a 0–100 confidence score that tells operators how much they can
trust an automated reconciliation result.  Low scores trigger a
``requires_review`` flag so a human can inspect the shift.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from app.schemas.reconciliation import AnomalyDetail, ConfidenceBreakdown
from app.services.ml.feature_engineering import ShiftFeatures

logger = logging.getLogger(__name__)

# ── Component weights (must sum to 1.0) ─────────────────────────────────

_W_DATA_COMPLETENESS = 0.30
_W_VARIANCE = 0.30
_W_ANOMALY = 0.25
_W_HISTORICAL = 0.15

# ── Review threshold ────────────────────────────────────────────────────

_REVIEW_THRESHOLD = 70  # overall_score < this → requires_review = True


# ── Service ─────────────────────────────────────────────────────────────


class ConfidenceScoringService:
    """Stateless service that turns features + anomalies into a confidence score."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_confidence(
        self,
        features: ShiftFeatures,
        anomalies: list[AnomalyDetail],
        variance: Decimal,
    ) -> ConfidenceBreakdown:
        """Return a full :class:`ConfidenceBreakdown` for the shift.

        Parameters
        ----------
        features:
            Pre-extracted numeric features for the shift.
        anomalies:
            Anomalies detected by :class:`AnomalyDetectionService`.
        variance:
            Signed cash variance (expected − actual).
        """
        data_comp = self._score_data_completeness(features)
        var_score = self._score_variance(variance)
        anom_score = self._score_anomalies(anomalies)
        hist_score = self._score_historical(features)

        overall = round(
            data_comp * _W_DATA_COMPLETENESS
            + var_score * _W_VARIANCE
            + anom_score * _W_ANOMALY
            + hist_score * _W_HISTORICAL
        )
        overall = max(0, min(100, overall))

        review_reasons = self._build_review_reasons(
            overall, data_comp, var_score, anom_score, hist_score, features,
        )
        requires_review = overall < _REVIEW_THRESHOLD or bool(review_reasons)

        breakdown = ConfidenceBreakdown(
            overall_score=overall,
            data_completeness=data_comp,
            variance_score=var_score,
            anomaly_score=anom_score,
            historical_score=hist_score,
            requires_review=requires_review,
            review_reasons=review_reasons,
        )

        logger.info(
            "Shift %s confidence=%d requires_review=%s",
            features.shift_id, overall, requires_review,
        )
        return breakdown

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_data_completeness(features: ShiftFeatures) -> int:
        """0–100 based on how many of the 3 data sources have records."""
        sources_present = sum([
            features.upi_transaction_count > 0,
            features.pos_transaction_count > 0,
            features.nozzle_count_active > 0,
        ])
        if sources_present >= 3:
            return 100
        if sources_present == 2:
            return 70
        if sources_present == 1:
            return 40
        return 0

    @staticmethod
    def _score_variance(variance: Decimal) -> int:
        """0–100 based on the absolute cash variance magnitude."""
        magnitude = abs(variance)
        if magnitude < 50:
            return 100
        if magnitude < 200:
            return 80
        if magnitude < 500:
            return 60
        if magnitude < 1000:
            return 40
        if magnitude < 2000:
            return 20
        return 0

    @staticmethod
    def _score_anomalies(anomalies: list[AnomalyDetail]) -> int:
        """0–100; deduct points per anomaly based on severity."""
        score = 100
        for a in anomalies:
            if a.severity == "high":
                score -= 30
            elif a.severity == "medium":
                score -= 15
        return max(score, 0)

    @staticmethod
    def _score_historical(features: ShiftFeatures) -> int:
        """0–100 based on the worker's track record."""
        if features.worker_shift_count >= 10 and features.worker_flagged_rate < 0.1:
            base = 100
        elif features.worker_shift_count >= 5:
            base = 70
        else:
            base = 50  # new worker — limited history

        if features.worker_flagged_rate > 0.3:
            base -= 20

        return max(base, 0)

    # ------------------------------------------------------------------
    # Review reasons
    # ------------------------------------------------------------------

    @staticmethod
    def _build_review_reasons(
        overall: int,
        data_comp: int,
        var_score: int,
        anom_score: int,
        hist_score: int,
        features: ShiftFeatures,
    ) -> list[str]:
        """Build human-readable reasons when the score is below threshold."""
        reasons: list[str] = []

        if data_comp <= 40:
            sources = []
            if features.upi_transaction_count == 0:
                sources.append("UPI")
            if features.pos_transaction_count == 0:
                sources.append("POS")
            if features.nozzle_count_active == 0:
                sources.append("PumpLog")
            reasons.append(f"Missing data sources: {', '.join(sources)}.")

        if var_score <= 40:
            reasons.append("Cash variance is unusually high.")

        if anom_score <= 40:
            reasons.append("Multiple or severe anomalies detected.")

        if hist_score <= 50:
            if features.worker_shift_count < 5:
                reasons.append(
                    "Worker has limited shift history — insufficient baseline."
                )
            if features.worker_flagged_rate > 0.3:
                reasons.append(
                    "Worker has a high historical flagged rate."
                )

        return reasons
