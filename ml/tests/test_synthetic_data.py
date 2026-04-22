"""Tests for the synthetic data generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features import ShiftFeatures
from src.synthetic_data import DEFAULT_WEIGHTS, generate_shifts, load_from_csv, save_to_csv


class TestGenerateShifts:
    """Tests for generate_shifts()."""

    def test_generates_correct_count(self):
        shifts = generate_shifts(n=100, seed=1)
        assert len(shifts) == 100

    def test_all_are_shift_features(self):
        shifts = generate_shifts(n=50, seed=2)
        for s in shifts:
            assert isinstance(s, ShiftFeatures)

    def test_all_fields_populated(self):
        shifts = generate_shifts(n=20, seed=3)
        for s in shifts:
            assert s.shift_id is not None
            assert s.worker_id is not None
            assert s.shift_duration_hours >= 0
            assert 0 <= s.shift_start_hour <= 23
            assert 0 <= s.day_of_week <= 6
            assert s.total_digital_amount >= 0
            assert s.total_volume_dispensed >= 0
            assert s.expected_cash_from_volume >= 0

    def test_scenario_distribution(self):
        """Generate enough samples that we see all 5 scenarios."""
        shifts = generate_shifts(n=2000, seed=4)
        scenarios = {s.scenario for s in shifts}
        for expected in DEFAULT_WEIGHTS:
            assert expected in scenarios, f"Missing scenario: {expected}"

    def test_scenario_proportions_roughly_match(self):
        shifts = generate_shifts(n=5000, seed=5)
        counts: dict[str, int] = {}
        for s in shifts:
            counts[s.scenario] = counts.get(s.scenario, 0) + 1

        for scenario, weight in DEFAULT_WEIGHTS.items():
            actual_pct = counts.get(scenario, 0) / len(shifts)
            # Allow ±5% tolerance
            assert abs(actual_pct - weight) < 0.05, (
                f"{scenario}: expected ~{weight:.0%}, got {actual_pct:.0%}"
            )

    def test_reproducible_with_seed(self):
        a = generate_shifts(n=50, seed=42)
        b = generate_shifts(n=50, seed=42)
        for sa, sb in zip(a, b):
            assert sa.scenario == sb.scenario
            assert sa.total_volume_dispensed == sb.total_volume_dispensed

    def test_night_shift_flag_consistency(self):
        shifts = generate_shifts(n=500, seed=6)
        for s in shifts:
            expected_night = s.shift_start_hour >= 22 or s.shift_start_hour < 6
            if s.scenario == "night_anomaly":
                assert s.is_night_shift is True
            if s.scenario == "normal":
                assert s.is_night_shift is False


class TestCSVRoundTrip:
    """Tests for CSV save/load."""

    def test_roundtrip(self, tmp_path):
        shifts = generate_shifts(n=30, seed=7)
        csv_path = tmp_path / "test.csv"
        save_to_csv(shifts, csv_path)
        loaded = load_from_csv(csv_path)
        assert len(loaded) == len(shifts)
        for orig, loaded_s in zip(shifts, loaded):
            assert orig.scenario == loaded_s.scenario
            assert abs(orig.total_volume_dispensed - loaded_s.total_volume_dispensed) < 0.01

    def test_feature_vector_after_roundtrip(self, tmp_path):
        shifts = generate_shifts(n=10, seed=8)
        csv_path = tmp_path / "test_fv.csv"
        save_to_csv(shifts, csv_path)
        loaded = load_from_csv(csv_path)
        for orig, loaded_s in zip(shifts, loaded):
            v1 = orig.feature_vector_15()
            v2 = loaded_s.feature_vector_15()
            for a, b in zip(v1, v2):
                assert abs(a - b) < 0.01
