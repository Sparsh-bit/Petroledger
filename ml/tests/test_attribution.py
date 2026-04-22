"""Tests for XGBoost attribution service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.attribution import CLASSES, AttributionResult, AttributionService
from src.features import ShiftFeatures
from src.synthetic_data import generate_shifts


class TestTraining:
    def test_train_on_synthetic_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)
        svc = AttributionService()
        model_path = svc.train_on_synthetic(n_per_class=50, version=1)
        assert model_path.exists()
        assert "attribution_xgb_v1" in model_path.name

    def test_model_file_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)
        svc = AttributionService()
        model_path = svc.train_on_synthetic(n_per_class=30, version=2)
        assert model_path.suffix == ".joblib"
        assert model_path.stat().st_size > 0


class TestPrediction:
    @pytest.fixture()
    def trained_service(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)
        svc = AttributionService()
        svc.train_on_synthetic(n_per_class=50)
        return svc

    def test_predict_returns_result(self, trained_service):
        shift = generate_shifts(n=1, seed=20)[0]
        result = trained_service.predict(shift)
        assert isinstance(result, AttributionResult)
        assert result.predicted_class in CLASSES
        assert 0 <= result.confidence <= 1.0

    def test_predict_probabilities_sum_to_one(self, trained_service):
        shift = generate_shifts(n=1, seed=21)[0]
        result = trained_service.predict(shift)
        total = sum(result.class_probabilities.values())
        assert abs(total - 1.0) < 0.01

    def test_feature_vector_is_12_elements(self):
        shift = generate_shifts(n=1, seed=22)[0]
        vec = shift.feature_vector_12()
        assert len(vec) == 12

    def test_predict_without_model_raises(self):
        svc = AttributionService()
        shift = generate_shifts(n=1, seed=23)[0]
        with pytest.raises(RuntimeError, match="not trained"):
            svc.predict(shift)


class TestEvaluation:
    def test_evaluate_returns_stats(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)
        svc = AttributionService()
        svc.train_on_synthetic(n_per_class=50)

        eval_data = generate_shifts(n=100, seed=24)
        stats = svc.evaluate(eval_data)

        assert "accuracy" in stats
        assert "confusion_matrix" in stats
        assert "classification_report" in stats
        assert 0 <= stats["accuracy"] <= 1.0


class TestLoadModel:
    def test_load_and_predict(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)

        svc1 = AttributionService()
        svc1.train_on_synthetic(n_per_class=30, version=3)

        svc2 = AttributionService()
        svc2.load(version=3)
        shift = generate_shifts(n=1, seed=25)[0]
        result = svc2.predict(shift)
        assert result.predicted_class in CLASSES

    def test_load_nonexistent_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.attribution._MODELS_DIR", tmp_path)
        svc = AttributionService()
        with pytest.raises(FileNotFoundError):
            svc.load(version=999)


class TestClassesDefined:
    def test_four_classes(self):
        assert len(CLASSES) == 4
        assert set(CLASSES) == {"worker", "nozzle", "time_window", "unknown"}
