"""Tests for Isolation Forest anomaly detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.features import ShiftFeatures
from src.isolation_forest import IsolationForestResult, IsolationForestService
from src.synthetic_data import generate_shifts


class TestTraining:
    def test_training_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        shifts = generate_shifts(n=100, seed=10)
        model_path = svc.train(shifts, version=1)
        assert model_path.exists()
        assert "isolation_forest_v1" in model_path.name

    def test_model_file_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        shifts = generate_shifts(n=50, seed=11)
        model_path = svc.train(shifts, version=2)
        assert model_path.suffix == ".joblib"
        assert model_path.stat().st_size > 0

    def test_insufficient_data_raises(self):
        svc = IsolationForestService()
        shifts = generate_shifts(n=5, seed=12)
        with pytest.raises(ValueError, match="at least 10"):
            svc.train(shifts)


class TestPrediction:
    def test_predict_returns_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        shifts = generate_shifts(n=100, seed=13)
        svc.train(shifts)

        result = svc.predict(shifts[0])
        assert isinstance(result, IsolationForestResult)
        assert isinstance(result.is_anomaly, bool)
        assert isinstance(result.anomaly_score, float)
        assert result.raw_prediction in (-1, 1)

    def test_predict_without_model_raises(self):
        svc = IsolationForestService()
        shift = generate_shifts(n=1, seed=14)[0]
        with pytest.raises(RuntimeError, match="not trained"):
            svc.predict(shift)


class TestEvaluation:
    def test_evaluate_returns_stats(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        shifts = generate_shifts(n=200, seed=15)
        svc.train(shifts[:150])

        test_set = shifts[150:]
        true_labels = [s.scenario != "normal" for s in test_set]
        stats = svc.evaluate(test_set, true_labels)

        assert "total" in stats
        assert "anomalies_detected" in stats
        assert "anomaly_rate" in stats
        assert 0 <= stats["anomaly_rate"] <= 1.0
        assert "confusion_matrix" in stats

    def test_evaluate_without_labels(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        shifts = generate_shifts(n=100, seed=16)
        svc.train(shifts[:80])

        stats = svc.evaluate(shifts[80:])
        assert "total" in stats
        assert "confusion_matrix" not in stats


class TestLoadModel:
    def test_load_and_predict(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)

        # Train and save
        svc1 = IsolationForestService()
        shifts = generate_shifts(n=100, seed=17)
        svc1.train(shifts, version=5)

        # Load in new service instance
        svc2 = IsolationForestService()
        svc2.load(version=5)
        result = svc2.predict(shifts[0])
        assert isinstance(result, IsolationForestResult)

    def test_load_nonexistent_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.isolation_forest._MODELS_DIR", tmp_path)
        svc = IsolationForestService()
        with pytest.raises(FileNotFoundError):
            svc.load(version=999)
