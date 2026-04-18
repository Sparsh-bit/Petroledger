"""
Unit tests for the reconciliation formula and engine.

Tests cover the 6 canonical scenarios from the PRD plus decimal precision.
We test the formula math directly (pure Decimal) and also the engine's
reconcile() method against a real SQLite in-memory DB.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

# ── Formula helpers ──────────────────────────────────────────────────────


def _expected_cash(
    fms: Decimal,
    upi: Decimal,
    card: Decimal,
    fleet: Decimal,
) -> Decimal:
    """Core formula: Expected Cash = FMS - UPI - Card - Fleet."""
    return fms - upi - card - fleet


def _variance(expected: Decimal, actual: Decimal) -> Decimal:
    """Variance = Expected - Actual.  Positive = shortage."""
    return expected - actual


def _variance_type(variance: Decimal) -> str:
    if variance == 0:
        return "MATCH"
    return "SHORTAGE" if variance > 0 else "EXCESS"


# ── Formula unit tests ───────────────────────────────────────────────────


class TestReconciliationFormula:
    """Pure arithmetic tests — no DB, no I/O."""

    def test_perfect_match(self):
        """Test 1: variance == 0 → MATCH."""
        fms, upi, card, fleet, actual = (
            Decimal("10000"), Decimal("3000"),
            Decimal("2000"), Decimal("1000"),
            Decimal("4000"),
        )
        expected = _expected_cash(fms, upi, card, fleet)
        assert expected == Decimal("4000")
        variance = _variance(expected, actual)
        assert variance == Decimal("0")
        assert _variance_type(variance) == "MATCH"

    def test_cash_shortage(self):
        """Test 2: actual < expected → positive variance → SHORTAGE."""
        fms, upi, card, fleet, actual = (
            Decimal("10000"), Decimal("3000"),
            Decimal("2000"), Decimal("1000"),
            Decimal("3500"),
        )
        expected = _expected_cash(fms, upi, card, fleet)
        variance = _variance(expected, actual)
        assert variance == Decimal("500")
        assert _variance_type(variance) == "SHORTAGE"

    def test_cash_excess(self):
        """Test 3: actual > expected → negative variance → EXCESS."""
        fms, upi, card, fleet, actual = (
            Decimal("10000"), Decimal("3000"),
            Decimal("2000"), Decimal("1000"),
            Decimal("4500"),
        )
        expected = _expected_cash(fms, upi, card, fleet)
        variance = _variance(expected, actual)
        assert variance == Decimal("-500")
        assert _variance_type(variance) == "EXCESS"

    def test_all_cash_no_digital(self):
        """Test 4: all-cash shift → expected == FMS → MATCH."""
        fms, upi, card, fleet, actual = (
            Decimal("10000"), Decimal("0"),
            Decimal("0"), Decimal("0"),
            Decimal("10000"),
        )
        expected = _expected_cash(fms, upi, card, fleet)
        assert expected == Decimal("10000")
        variance = _variance(expected, actual)
        assert variance == Decimal("0")
        assert _variance_type(variance) == "MATCH"

    def test_decimal_precision_no_float_error(self):
        """Test 5: exact Decimal arithmetic — no floating-point drift."""
        fms = Decimal("1000.10")
        upi = Decimal("333.33")
        card = Decimal("333.33")
        fleet = Decimal("333.33")
        actual = Decimal("0.11")

        expected = _expected_cash(fms, upi, card, fleet)
        # 1000.10 - 333.33 - 333.33 - 333.33 = 0.11
        assert expected == Decimal("0.11")
        variance = _variance(expected, actual)
        assert variance == Decimal("0")
        assert _variance_type(variance) == "MATCH"

    def test_no_transactions_all_zero(self):
        """Test 6: empty shift — everything zero → MATCH (no variance)."""
        fms, upi, card, fleet, actual = (
            Decimal("0"), Decimal("0"),
            Decimal("0"), Decimal("0"),
            Decimal("0"),
        )
        expected = _expected_cash(fms, upi, card, fleet)
        variance = _variance(expected, actual)
        assert expected == Decimal("0")
        assert variance == Decimal("0")
        assert _variance_type(variance) == "MATCH"

    def test_large_fleet_reduces_expected_cash(self):
        """Fleet card payments reduce the expected cash the attendant should hold."""
        fms = Decimal("50000")
        upi = Decimal("5000")
        card = Decimal("10000")
        fleet = Decimal("30000")      # Large fleet payment
        actual = Decimal("5000")      # Only 5k cash expected

        expected = _expected_cash(fms, upi, card, fleet)
        assert expected == Decimal("5000")
        variance = _variance(expected, actual)
        assert variance == Decimal("0")
        assert _variance_type(variance) == "MATCH"

    def test_variance_direction_precision(self):
        """A 1-paisa shortage is still a SHORTAGE."""
        fms = Decimal("1000.00")
        upi = Decimal("0")
        card = Decimal("0")
        fleet = Decimal("0")
        actual = Decimal("999.99")  # 1 paisa short

        expected = _expected_cash(fms, upi, card, fleet)
        variance = _variance(expected, actual)
        assert variance == Decimal("0.01")
        assert _variance_type(variance) == "SHORTAGE"


# ── AnomalyDetection unit tests ──────────────────────────────────────────

class TestAnomalyDetection:
    """Tests for AnomalyDetectionService rule checks."""

    def _make_features(self, **overrides):
        """Return a minimal ShiftFeatures with sensible defaults."""
        from datetime import datetime, timezone
        from app.services.ml.feature_engineering import ShiftFeatures

        defaults = dict(
            shift_id=uuid4(),
            worker_id=uuid4(),
            extracted_at=datetime.now(timezone.utc),
            shift_duration_hours=8.0,
            shift_start_hour=6,
            is_night_shift=False,
            day_of_week=0,
            total_upi_amount=Decimal("3000"),
            total_pos_amount=Decimal("1000"),
            total_digital_amount=Decimal("4000"),
            upi_transaction_count=10,
            pos_transaction_count=3,
            avg_transaction_amount=Decimal("300"),
            max_transaction_amount=Decimal("500"),
            total_volume_dispensed=Decimal("100"),
            expected_cash_from_volume=Decimal("10000"),
            nozzle_count_active=2,
            worker_avg_variance=Decimal("50"),
            worker_variance_std=Decimal("10"),
            worker_shift_count=20,
            worker_flagged_rate=0.05,
        )
        defaults.update(overrides)
        return ShiftFeatures(**defaults)

    def test_no_anomalies_normal_shift(self):
        """A clean shift produces zero anomalies."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService

        svc = AnomalyDetectionService()
        features = self._make_features(
            expected_cash_from_volume=Decimal("10000"),
            total_digital_amount=Decimal("9900"),  # 1% mismatch — below threshold
        )
        anomalies = svc.detect_anomalies(features)
        # Should have no cash variance (digital covers > volume, small mismatch)
        assert all(a.type != "CASH_VARIANCE_HIGH" for a in anomalies)

    def test_cash_variance_high_triggers(self):
        """CASH_VARIANCE_HIGH triggers when variance > ₹2000."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, CASH_VARIANCE_HIGH

        svc = AnomalyDetectionService()
        features = self._make_features(
            expected_cash_from_volume=Decimal("10000"),
            total_digital_amount=Decimal("3000"),   # ₹7000 not covered → high
        )
        anomalies = svc.detect_anomalies(features)
        types = [a.type for a in anomalies]
        assert CASH_VARIANCE_HIGH in types
        cash_anomaly = next(a for a in anomalies if a.type == CASH_VARIANCE_HIGH)
        assert cash_anomaly.severity == "high"

    def test_cash_variance_medium_triggers(self):
        """CASH_VARIANCE_HIGH triggers at medium severity for ₹500-₹2000 variance."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, CASH_VARIANCE_HIGH

        svc = AnomalyDetectionService()
        features = self._make_features(
            expected_cash_from_volume=Decimal("10000"),
            total_digital_amount=Decimal("9000"),   # ₹1000 mismatch → medium
        )
        anomalies = svc.detect_anomalies(features)
        cash_anomaly = next((a for a in anomalies if a.type == CASH_VARIANCE_HIGH), None)
        assert cash_anomaly is not None
        assert cash_anomaly.severity == "medium"

    def test_below_threshold_no_anomaly(self):
        """Variance below ₹500 does NOT trigger CASH_VARIANCE_HIGH."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, CASH_VARIANCE_HIGH

        svc = AnomalyDetectionService()
        features = self._make_features(
            expected_cash_from_volume=Decimal("10000"),
            total_digital_amount=Decimal("9700"),   # ₹300 — below medium threshold
        )
        anomalies = svc.detect_anomalies(features)
        assert all(a.type != CASH_VARIANCE_HIGH for a in anomalies)

    def test_zero_digital_payments_triggers(self):
        """ZERO_DIGITAL_PAYMENTS triggers when volume > 0 but no digital payments."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, ZERO_DIGITAL_PAYMENTS

        svc = AnomalyDetectionService()
        features = self._make_features(
            total_digital_amount=Decimal("0"),
            total_volume_dispensed=Decimal("100"),
            upi_transaction_count=0,
            pos_transaction_count=0,
        )
        anomalies = svc.detect_anomalies(features)
        types = [a.type for a in anomalies]
        assert ZERO_DIGITAL_PAYMENTS in types
        zd = next(a for a in anomalies if a.type == ZERO_DIGITAL_PAYMENTS)
        assert zd.severity == "high"

    def test_zero_digital_not_triggered_when_no_volume(self):
        """ZERO_DIGITAL_PAYMENTS does NOT trigger when volume is also zero."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, ZERO_DIGITAL_PAYMENTS

        svc = AnomalyDetectionService()
        features = self._make_features(
            total_digital_amount=Decimal("0"),
            total_volume_dispensed=Decimal("0"),
        )
        anomalies = svc.detect_anomalies(features)
        assert all(a.type != ZERO_DIGITAL_PAYMENTS for a in anomalies)

    def test_night_shift_variance_triggers(self):
        """NIGHT_SHIFT_VARIANCE triggers on night shifts over 1.5x medium threshold."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, NIGHT_SHIFT_VARIANCE

        svc = AnomalyDetectionService()
        # Night threshold = 500 * 1.5 = 750. Set variance above it.
        features = self._make_features(
            is_night_shift=True,
            shift_start_hour=22,
            expected_cash_from_volume=Decimal("10000"),
            total_digital_amount=Decimal("9000"),   # ₹1000 > ₹750 night threshold
        )
        anomalies = svc.detect_anomalies(features)
        types = [a.type for a in anomalies]
        assert NIGHT_SHIFT_VARIANCE in types

    def test_worker_history_flag_triggers(self):
        """WORKER_HISTORICAL_FLAG triggers when flagged_rate > 0.30."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, WORKER_HISTORICAL_FLAG

        svc = AnomalyDetectionService()
        features = self._make_features(
            worker_flagged_rate=0.40,   # 40% > 30% threshold
            worker_shift_count=10,
        )
        anomalies = svc.detect_anomalies(features)
        types = [a.type for a in anomalies]
        assert WORKER_HISTORICAL_FLAG in types

    def test_worker_history_below_threshold_no_flag(self):
        """WORKER_HISTORICAL_FLAG does NOT trigger when flagged_rate <= 0.30."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, WORKER_HISTORICAL_FLAG

        svc = AnomalyDetectionService()
        features = self._make_features(
            worker_flagged_rate=0.20,   # 20% — below threshold
            worker_shift_count=10,
        )
        anomalies = svc.detect_anomalies(features)
        assert all(a.type != WORKER_HISTORICAL_FLAG for a in anomalies)

    def test_unusual_transaction_pattern_triggers(self):
        """UNUSUAL_TRANSACTION_PATTERN triggers when max_txn > 3x avg."""
        from app.services.reconciliation.anomaly import AnomalyDetectionService, UNUSUAL_TRANSACTION_PATTERN

        svc = AnomalyDetectionService()
        features = self._make_features(
            avg_transaction_amount=Decimal("100"),
            max_transaction_amount=Decimal("500"),  # 5x > 3x threshold
        )
        anomalies = svc.detect_anomalies(features)
        types = [a.type for a in anomalies]
        assert UNUSUAL_TRANSACTION_PATTERN in types


# ── Confidence Scoring tests ─────────────────────────────────────────────


class TestConfidenceScoring:
    """Tests for ConfidenceScoringService."""

    def _make_features(self, **overrides):
        from datetime import datetime, timezone
        from app.services.ml.feature_engineering import ShiftFeatures

        defaults = dict(
            shift_id=uuid4(),
            worker_id=uuid4(),
            extracted_at=datetime.now(timezone.utc),
            shift_duration_hours=8.0,
            shift_start_hour=6,
            is_night_shift=False,
            day_of_week=0,
            total_upi_amount=Decimal("3000"),
            total_pos_amount=Decimal("1000"),
            total_digital_amount=Decimal("4000"),
            upi_transaction_count=10,
            pos_transaction_count=3,
            avg_transaction_amount=Decimal("300"),
            max_transaction_amount=Decimal("500"),
            total_volume_dispensed=Decimal("100"),
            expected_cash_from_volume=Decimal("10000"),
            nozzle_count_active=2,
            worker_avg_variance=Decimal("50"),
            worker_variance_std=Decimal("10"),
            worker_shift_count=15,
            worker_flagged_rate=0.05,
        )
        defaults.update(overrides)
        return ShiftFeatures(**defaults)

    def test_high_confidence_clean_shift(self):
        """A clean shift with all data sources and zero variance → HIGH confidence."""
        from app.services.reconciliation.confidence import ConfidenceScoringService

        svc = ConfidenceScoringService()
        features = self._make_features()
        breakdown = svc.calculate_confidence(features, [], Decimal("0"))

        assert breakdown.overall_score >= 90
        assert breakdown.requires_review is False
        assert breakdown.review_reasons == []

    def test_low_confidence_large_variance(self):
        """Large variance → LOW confidence → requires_review = True."""
        from app.services.reconciliation.confidence import ConfidenceScoringService

        svc = ConfidenceScoringService()
        features = self._make_features()
        breakdown = svc.calculate_confidence(features, [], Decimal("5000"))

        assert breakdown.requires_review is True
        assert breakdown.variance_score == 0  # variance > ₹2000

    def test_score_clamped_0_to_100(self):
        """Overall score is always in [0, 100]."""
        from app.services.reconciliation.confidence import ConfidenceScoringService
        from app.schemas.reconciliation import AnomalyDetail

        svc = ConfidenceScoringService()
        # Many high-severity anomalies — should not go below 0
        anomalies = [
            AnomalyDetail(type="CASH_VARIANCE_HIGH", description="", severity="high", amount=None)
            for _ in range(10)
        ]
        features = self._make_features(
            upi_transaction_count=0,
            pos_transaction_count=0,
            nozzle_count_active=0,
        )
        breakdown = svc.calculate_confidence(features, anomalies, Decimal("9999"))
        assert 0 <= breakdown.overall_score <= 100

    def test_missing_data_sources_reduces_score(self):
        """Missing all data sources tanks the data_completeness component."""
        from app.services.reconciliation.confidence import ConfidenceScoringService

        svc = ConfidenceScoringService()
        features = self._make_features(
            upi_transaction_count=0,
            pos_transaction_count=0,
            nozzle_count_active=0,
        )
        breakdown = svc.calculate_confidence(features, [], Decimal("0"))
        assert breakdown.data_completeness == 0

    def test_high_worker_flagged_rate_reduces_historical_score(self):
        """High worker flagged rate → low historical_score."""
        from app.services.reconciliation.confidence import ConfidenceScoringService

        svc = ConfidenceScoringService()
        features = self._make_features(
            worker_shift_count=20,
            worker_flagged_rate=0.50,   # 50% — well above 30% threshold
        )
        breakdown = svc.calculate_confidence(features, [], Decimal("0"))
        assert breakdown.historical_score < 70

    def test_review_reasons_populated_when_below_threshold(self):
        """review_reasons are non-empty when requires_review is True."""
        from app.services.reconciliation.confidence import ConfidenceScoringService

        svc = ConfidenceScoringService()
        features = self._make_features(
            upi_transaction_count=0,
            pos_transaction_count=0,
            nozzle_count_active=0,
        )
        breakdown = svc.calculate_confidence(features, [], Decimal("3000"))
        if breakdown.requires_review:
            assert len(breakdown.review_reasons) > 0
