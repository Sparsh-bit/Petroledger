"""PetroLedger ML Sandbox — XGBoost Attribution Service.

Trains an XGBClassifier on synthetic labelled data to *attribute* the
likely cause of a cash variance to one of four categories:

    ┌─────────────┬──────────────────────────────────────┐
    │ Class       │ Meaning                              │
    ├─────────────┼──────────────────────────────────────┤
    │ worker      │ Worker-related (skimming / errors)   │
    │ nozzle      │ Nozzle / meter hardware issue        │
    │ time_window │ Risky time window (night shifts)     │
    │ unknown     │ No clear attribution                 │
    └─────────────┴──────────────────────────────────────┘

Uses a 12-element feature vector and XGBoost multiclass classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from xgboost import XGBClassifier

from .features import ShiftFeatures
from .synthetic_data import generate_shifts

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

CLASSES = ["worker", "nozzle", "time_window", "unknown"]
_CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}


# ── Result dataclass ────────────────────────────────────────────────────


@dataclass
class AttributionResult:
    """Prediction result for a single shift."""

    predicted_class: str
    confidence: float
    class_probabilities: dict[str, float]


# ── Service ─────────────────────────────────────────────────────────────


class AttributionService:
    """XGBoost-based variance attribution service."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self._model: XGBClassifier | None = None

    # ── Training on synthetic data ──────────────────────────────────────

    def train_on_synthetic(
        self,
        n_per_class: int = 500,
        version: int = 1,
    ) -> Path:
        """Generate labelled synthetic data and train XGBClassifier.

        Creates *n_per_class* samples for each of the 4 attribution
        classes using controlled scenario weights, then trains and
        saves the model.
        """
        logger.info(
            "Generating %d samples per class (%d total)",
            n_per_class, n_per_class * 4,
        )

        all_features: list[ShiftFeatures] = []
        all_labels: list[int] = []

        # worker class — from suspicious_worker scenario
        worker_data = generate_shifts(
            n=n_per_class,
            weights={"suspicious_worker": 1.0, "normal": 0.0, "nozzle_issues": 0.0, "night_anomaly": 0.0, "random_noise": 0.0},
            seed=self.random_state,
        )
        all_features.extend(worker_data)
        all_labels.extend([_CLASS_TO_IDX["worker"]] * len(worker_data))

        # nozzle class — from nozzle_issues scenario
        nozzle_data = generate_shifts(
            n=n_per_class,
            weights={"nozzle_issues": 1.0, "normal": 0.0, "suspicious_worker": 0.0, "night_anomaly": 0.0, "random_noise": 0.0},
            seed=self.random_state + 1,
        )
        all_features.extend(nozzle_data)
        all_labels.extend([_CLASS_TO_IDX["nozzle"]] * len(nozzle_data))

        # time_window class — from night_anomaly scenario
        night_data = generate_shifts(
            n=n_per_class,
            weights={"night_anomaly": 1.0, "normal": 0.0, "suspicious_worker": 0.0, "nozzle_issues": 0.0, "random_noise": 0.0},
            seed=self.random_state + 2,
        )
        all_features.extend(night_data)
        all_labels.extend([_CLASS_TO_IDX["time_window"]] * len(night_data))

        # unknown class — from normal + random noise
        unknown_data = generate_shifts(
            n=n_per_class,
            weights={"normal": 0.7, "random_noise": 0.3, "suspicious_worker": 0.0, "nozzle_issues": 0.0, "night_anomaly": 0.0},
            seed=self.random_state + 3,
        )
        all_features.extend(unknown_data)
        all_labels.extend([_CLASS_TO_IDX["unknown"]] * len(unknown_data))

        return self._train(all_features, all_labels, version)

    def _train(
        self,
        features_list: list[ShiftFeatures],
        labels: list[int],
        version: int = 1,
    ) -> Path:
        """Core training logic."""
        X = np.array([f.feature_vector_12() for f in features_list])
        y = np.array(labels)

        logger.info("Training XGBClassifier on %d samples, %d features", *X.shape)

        self._model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective="multi:softprob",
            num_class=len(CLASSES),
            random_state=self.random_state,
            eval_metric="mlogloss",
        )
        self._model.fit(X, y)

        model_path = _MODELS_DIR / f"attribution_xgb_v{version}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, model_path)
        logger.info("Model saved to %s", model_path)
        return model_path

    # ── Loading ─────────────────────────────────────────────────────────

    def load(self, version: int = 1) -> None:
        """Load a previously trained model from disk."""
        model_path = _MODELS_DIR / f"attribution_xgb_v{version}.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"No model at {model_path}")
        self._model = joblib.load(model_path)
        logger.info("Loaded model from %s", model_path)

    # ── Prediction ──────────────────────────────────────────────────────

    def predict(
        self,
        features: ShiftFeatures,
        variance: float | None = None,
    ) -> AttributionResult:
        """Predict the most likely cause of cash variance.

        *variance* is accepted for API compatibility but not used in the
        feature vector (it is a target, not a feature).
        """
        if self._model is None:
            raise RuntimeError("Model not trained or loaded. Call train_on_synthetic() first.")

        X = np.array([features.feature_vector_12()])
        probas = self._model.predict_proba(X)[0]
        pred_idx = int(np.argmax(probas))

        return AttributionResult(
            predicted_class=CLASSES[pred_idx],
            confidence=float(probas[pred_idx]),
            class_probabilities={
                CLASSES[i]: round(float(probas[i]), 4) for i in range(len(CLASSES))
            },
        )

    # ── Evaluation ──────────────────────────────────────────────────────

    def evaluate(self, features_list: list[ShiftFeatures]) -> dict:
        """Evaluate model on a labelled test set.

        Uses the ``label`` field of each :class:`ShiftFeatures` as ground truth.
        """
        if self._model is None:
            raise RuntimeError("Model not trained or loaded.")

        X = np.array([f.feature_vector_12() for f in features_list])
        true_labels = []
        for f in features_list:
            label = f.label if f.label in _CLASS_TO_IDX else "unknown"
            true_labels.append(_CLASS_TO_IDX[label])

        y_true = np.array(true_labels)
        y_pred = self._model.predict(X)

        cm = confusion_matrix(y_true, y_pred).tolist()
        cr = classification_report(
            y_true, y_pred,
            target_names=CLASSES,
            output_dict=True,
        )

        return {
            "confusion_matrix": cm,
            "classification_report": cr,
            "accuracy": cr["accuracy"],
        }
