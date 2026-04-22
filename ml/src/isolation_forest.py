"""PetroLedger ML Sandbox — Isolation Forest Anomaly Detection.

Trains an Isolation Forest on the 15-element feature vector from
:class:`ShiftFeatures` and predicts whether a shift is an outlier.

    contamination=0.05  │  n_estimators=100
    model path: models/isolation_forest_v{version}.joblib
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix

from .features import ShiftFeatures

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


# ── Result dataclass ────────────────────────────────────────────────────


@dataclass
class IsolationForestResult:
    """Prediction result for a single shift."""

    is_anomaly: bool
    anomaly_score: float  # sklearn decision_function (lower = more anomalous)
    raw_prediction: int   # -1 = anomaly, 1 = normal


# ── Service ─────────────────────────────────────────────────────────────


class IsolationForestService:
    """Isolation Forest training and inference for shift anomaly detection."""

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model: IsolationForest | None = None

    # ── Training ────────────────────────────────────────────────────────

    def train(
        self,
        features_list: list[ShiftFeatures],
        version: int = 1,
    ) -> Path:
        """Train on a list of ShiftFeatures, save model to disk.

        Returns the path of the saved model file.
        """
        if len(features_list) < 10:
            raise ValueError(
                f"Need at least 10 samples to train, got {len(features_list)}"
            )

        X = np.array([f.feature_vector_15() for f in features_list])
        logger.info("Training Isolation Forest on %d samples, %d features", *X.shape)

        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        self._model.fit(X)

        model_path = _MODELS_DIR / f"isolation_forest_v{version}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, model_path)
        logger.info("Model saved to %s", model_path)
        return model_path

    # ── Loading ─────────────────────────────────────────────────────────

    def load(self, version: int = 1) -> None:
        """Load a previously trained model from disk."""
        model_path = _MODELS_DIR / f"isolation_forest_v{version}.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"No model at {model_path}")
        self._model = joblib.load(model_path)
        logger.info("Loaded model from %s", model_path)

    # ── Prediction ──────────────────────────────────────────────────────

    def predict(self, features: ShiftFeatures) -> IsolationForestResult:
        """Predict whether a single shift is anomalous."""
        if self._model is None:
            raise RuntimeError("Model not trained or loaded. Call train() or load() first.")

        X = np.array([features.feature_vector_15()])
        pred = int(self._model.predict(X)[0])
        score = float(self._model.decision_function(X)[0])

        return IsolationForestResult(
            is_anomaly=(pred == -1),
            anomaly_score=score,
            raw_prediction=pred,
        )

    # ── Evaluation ──────────────────────────────────────────────────────

    def evaluate(
        self,
        features_list: list[ShiftFeatures],
        true_labels: list[bool] | None = None,
    ) -> dict:
        """Run predictions on a test set, return stats.

        If *true_labels* is provided (True=anomaly), also compute
        confusion matrix and classification report.
        """
        if self._model is None:
            raise RuntimeError("Model not trained or loaded.")

        results = [self.predict(f) for f in features_list]
        predicted = [r.is_anomaly for r in results]
        scores = [r.anomaly_score for r in results]

        stats = {
            "total": len(results),
            "anomalies_detected": sum(predicted),
            "anomaly_rate": sum(predicted) / len(results) if results else 0.0,
            "avg_score": float(np.mean(scores)),
            "min_score": float(np.min(scores)),
            "max_score": float(np.max(scores)),
        }

        if true_labels is not None:
            cm = confusion_matrix(true_labels, predicted).tolist()
            cr = classification_report(
                true_labels, predicted,
                target_names=["Normal", "Anomaly"],
                output_dict=True,
            )
            stats["confusion_matrix"] = cm
            stats["classification_report"] = cr

        return stats
