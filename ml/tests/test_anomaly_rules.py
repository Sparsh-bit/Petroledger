"""Tests for rule-based anomaly detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.anomaly_rules import (
    CASH_VARIANCE_HIGH,
    NIGHT_SHIFT_VARIANCE,
    UNUSUAL_TRANSACTION_PATTERN,
    VOLUME_MISMATCH,
    WORKER_HISTORICAL_FLAG,
    ZERO_DIGITAL_PAYMENTS,
    AnomalyRulesService,
)
from src.features import ShiftFeatures


def _make_features(**kwargs) -> ShiftFeatures:
    """Create a ShiftFeatures with sensible defaults, overriding with kwargs."""
    defaults = {
        "shift_duration_hours": 8.0,
        "shift_start_hour": 10,
        "is_night_shift": False,
        "day_of_week": 2,
        "total_upi_amount": 5000.0,
        "total_pos_amount": 3000.0,
        "total_digital_amount": 8000.0,
        "upi_transaction_count": 20,
        "pos_transaction_count": 10,
        "avg_transaction_amount": 266.67,
        "max_transaction_amount": 500.0,
        "total_volume_dispensed": 80.0,
        "expected_cash_from_volume": 8000.0,
        "nozzle_count_active": 4,
        "worker_avg_variance": 100.0,
        "worker_variance_std": 50.0,
        "worker_shift_count": 20,
        "worker_flagged_rate": 0.1,
    }
    defaults.update(kwargs)
    return ShiftFeatures(**defaults)


class TestCashVariance:
    svc = AnomalyRulesService()

    def test_no_anomaly_under_threshold(self):
        f = _make_features(expected_cash_from_volume=10000, total_digital_amount=9600)
        anomalies = self.svc.detect_anomalies(f)
        types = {a["type"] for a in anomalies}
        assert CASH_VARIANCE_HIGH not in types

    def test_medium_cash_variance(self):
        # variance = 800 (> 500 medium, < 2000 high)
        f = _make_features(expected_cash_from_volume=10000, total_digital_amount=9200)
        anomalies = self.svc.detect_anomalies(f)
        cash_anomalies = [a for a in anomalies if a["type"] == CASH_VARIANCE_HIGH]
        assert len(cash_anomalies) == 1
        assert cash_anomalies[0]["severity"] == "medium"

    def test_high_cash_variance(self):
        # variance = 3000 (> 2000 high)
        f = _make_features(expected_cash_from_volume=10000, total_digital_amount=7000)
        anomalies = self.svc.detect_anomalies(f)
        cash_anomalies = [a for a in anomalies if a["type"] == CASH_VARIANCE_HIGH]
        assert len(cash_anomalies) == 1
        assert cash_anomalies[0]["severity"] == "high"


class TestVolumeMismatch:
    svc = AnomalyRulesService()

    def test_no_mismatch_under_threshold(self):
        f = _make_features(expected_cash_from_volume=10000, total_digital_amount=9500)
        anomalies = self.svc.detect_anomalies(f)
        types = {a["type"] for a in anomalies}
        assert VOLUME_MISMATCH not in types

    def test_volume_mismatch_detected(self):
        # 15% mismatch (> 10% threshold)
        f = _make_features(expected_cash_from_volume=10000, total_digital_amount=8500)
        anomalies = self.svc.detect_anomalies(f)
        vol_anomalies = [a for a in anomalies if a["type"] == VOLUME_MISMATCH]
        assert len(vol_anomalies) == 1

    def test_zero_expected_no_crash(self):
        f = _make_features(expected_cash_from_volume=0, total_digital_amount=100)
        anomalies = self.svc.detect_anomalies(f)
        vol_anomalies = [a for a in anomalies if a["type"] == VOLUME_MISMATCH]
        assert len(vol_anomalies) == 0


class TestUnusualTransaction:
    svc = AnomalyRulesService()

    def test_no_spike(self):
        f = _make_features(avg_transaction_amount=100, max_transaction_amount=250)
        anomalies = self.svc.detect_anomalies(f)
        types = {a["type"] for a in anomalies}
        assert UNUSUAL_TRANSACTION_PATTERN not in types

    def test_spike_detected(self):
        # max = 500, avg = 100 → 5× (> 3× threshold)
        f = _make_features(avg_transaction_amount=100, max_transaction_amount=500)
        anomalies = self.svc.detect_anomalies(f)
        spike = [a for a in anomalies if a["type"] == UNUSUAL_TRANSACTION_PATTERN]
        assert len(spike) == 1

    def test_zero_avg_no_crash(self):
        f = _make_features(avg_transaction_amount=0, max_transaction_amount=500)
        anomalies = self.svc.detect_anomalies(f)
        spike = [a for a in anomalies if a["type"] == UNUSUAL_TRANSACTION_PATTERN]
        assert len(spike) == 0


class TestNightShiftVariance:
    svc = AnomalyRulesService()

    def test_day_shift_no_flag(self):
        f = _make_features(is_night_shift=False, expected_cash_from_volume=10000, total_digital_amount=7000)
        anomalies = self.svc.detect_anomalies(f)
        night = [a for a in anomalies if a["type"] == NIGHT_SHIFT_VARIANCE]
        assert len(night) == 0

    def test_night_shift_flagged(self):
        # Night shift, variance = 3000 > 500*1.5 = 750
        f = _make_features(
            is_night_shift=True, shift_start_hour=23,
            expected_cash_from_volume=10000, total_digital_amount=7000,
        )
        anomalies = self.svc.detect_anomalies(f)
        night = [a for a in anomalies if a["type"] == NIGHT_SHIFT_VARIANCE]
        assert len(night) == 1
        assert night[0]["severity"] == "high"


class TestWorkerHistory:
    svc = AnomalyRulesService()

    def test_low_flagged_rate_ok(self):
        f = _make_features(worker_flagged_rate=0.15, worker_shift_count=20)
        anomalies = self.svc.detect_anomalies(f)
        worker = [a for a in anomalies if a["type"] == WORKER_HISTORICAL_FLAG]
        assert len(worker) == 0

    def test_high_flagged_rate_detected(self):
        f = _make_features(worker_flagged_rate=0.50, worker_shift_count=20)
        anomalies = self.svc.detect_anomalies(f)
        worker = [a for a in anomalies if a["type"] == WORKER_HISTORICAL_FLAG]
        assert len(worker) == 1

    def test_zero_shift_count_no_crash(self):
        f = _make_features(worker_shift_count=0, worker_flagged_rate=0.9)
        anomalies = self.svc.detect_anomalies(f)
        worker = [a for a in anomalies if a["type"] == WORKER_HISTORICAL_FLAG]
        assert len(worker) == 0


class TestZeroDigital:
    svc = AnomalyRulesService()

    def test_digital_present_ok(self):
        f = _make_features(total_digital_amount=5000, total_volume_dispensed=100)
        anomalies = self.svc.detect_anomalies(f)
        zd = [a for a in anomalies if a["type"] == ZERO_DIGITAL_PAYMENTS]
        assert len(zd) == 0

    def test_zero_digital_with_volume(self):
        f = _make_features(
            total_digital_amount=0, total_upi_amount=0, total_pos_amount=0,
            total_volume_dispensed=100, expected_cash_from_volume=10000,
        )
        anomalies = self.svc.detect_anomalies(f)
        zd = [a for a in anomalies if a["type"] == ZERO_DIGITAL_PAYMENTS]
        assert len(zd) == 1
        assert zd[0]["severity"] == "high"

    def test_zero_digital_zero_volume_ok(self):
        f = _make_features(total_digital_amount=0, total_volume_dispensed=0)
        anomalies = self.svc.detect_anomalies(f)
        zd = [a for a in anomalies if a["type"] == ZERO_DIGITAL_PAYMENTS]
        assert len(zd) == 0


class TestRiskScore:
    svc = AnomalyRulesService()

    def test_no_anomalies_zero_score(self):
        assert self.svc.calculate_risk_score([]) == 0.0

    def test_single_anomaly(self):
        anomalies = [{"type": CASH_VARIANCE_HIGH, "severity": "high", "description": "", "amount": 1000}]
        score = self.svc.calculate_risk_score(anomalies)
        assert score == 0.40  # weight for CASH_VARIANCE_HIGH

    def test_multiple_same_type(self):
        """Duplicate types should only count once."""
        anomalies = [
            {"type": CASH_VARIANCE_HIGH, "severity": "high", "description": "", "amount": 1000},
            {"type": CASH_VARIANCE_HIGH, "severity": "medium", "description": "", "amount": 500},
        ]
        score = self.svc.calculate_risk_score(anomalies)
        assert score == 0.40

    def test_capped_at_one(self):
        """Score should never exceed 1.0."""
        anomalies = [
            {"type": CASH_VARIANCE_HIGH, "severity": "high", "description": "", "amount": 1},
            {"type": VOLUME_MISMATCH, "severity": "high", "description": "", "amount": 1},
            {"type": UNUSUAL_TRANSACTION_PATTERN, "severity": "medium", "description": "", "amount": 1},
            {"type": NIGHT_SHIFT_VARIANCE, "severity": "high", "description": "", "amount": 1},
            {"type": WORKER_HISTORICAL_FLAG, "severity": "medium", "description": "", "amount": None},
            {"type": ZERO_DIGITAL_PAYMENTS, "severity": "high", "description": "", "amount": 1},
        ]
        score = self.svc.calculate_risk_score(anomalies)
        assert score == 1.0
