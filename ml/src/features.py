"""PetroLedger ML Sandbox — Standalone ShiftFeatures Dataclass.

DB-free copy of the backend's ShiftFeatures.  Same fields, no SQLAlchemy.
Includes from_dict() / to_dict() helpers for CSV/JSON round-tripping.

⚠️  This is a *throwaway sandbox* — the backend integration will import its
own copy of this dataclass; do not depend on this module in production.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class ShiftFeatures:
    """Flat feature vector describing a single shift for ML models."""

    # ── Identifiers ─────────────────────────────────────────────────────
    shift_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ── Temporal ────────────────────────────────────────────────────────
    shift_duration_hours: float = 0.0
    shift_start_hour: int = 8
    is_night_shift: bool = False
    day_of_week: int = 0  # 0=Monday … 6=Sunday

    # ── Transaction ─────────────────────────────────────────────────────
    total_upi_amount: float = 0.0
    total_pos_amount: float = 0.0
    total_digital_amount: float = 0.0
    upi_transaction_count: int = 0
    pos_transaction_count: int = 0
    avg_transaction_amount: float = 0.0
    max_transaction_amount: float = 0.0

    # ── Pump / Volume ───────────────────────────────────────────────────
    total_volume_dispensed: float = 0.0
    expected_cash_from_volume: float = 0.0
    nozzle_count_active: int = 4

    # ── Worker history ──────────────────────────────────────────────────
    worker_avg_variance: float = 0.0
    worker_variance_std: float = 0.0
    worker_shift_count: int = 0
    worker_flagged_rate: float = 0.0

    # ── Label (for supervised training only) ────────────────────────────
    label: str | None = None  # e.g. "worker", "nozzle", "time_window", "unknown"
    scenario: str | None = None  # e.g. "normal", "suspicious_worker", …

    # ── Helpers ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (all Decimals → float)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ShiftFeatures:
        """Construct from a plain dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def feature_vector_15(self) -> list[float]:
        """Return the 15-element numeric vector used by Isolation Forest."""
        return [
            self.shift_duration_hours,
            float(self.shift_start_hour),
            float(self.is_night_shift),
            float(self.day_of_week),
            self.total_upi_amount,
            self.total_pos_amount,
            float(self.upi_transaction_count),
            float(self.pos_transaction_count),
            self.avg_transaction_amount,
            self.max_transaction_amount,
            self.total_volume_dispensed,
            self.expected_cash_from_volume,
            self.worker_avg_variance,
            self.worker_variance_std,
            float(self.worker_shift_count),
        ]

    def feature_vector_12(self) -> list[float]:
        """Return the 12-element numeric vector used by XGBoost attribution."""
        return [
            self.shift_duration_hours,
            float(self.shift_start_hour),
            float(self.is_night_shift),
            self.total_digital_amount,
            float(self.upi_transaction_count + self.pos_transaction_count),
            self.avg_transaction_amount,
            self.max_transaction_amount,
            self.total_volume_dispensed,
            self.expected_cash_from_volume,
            self.worker_avg_variance,
            self.worker_variance_std,
            self.worker_flagged_rate,
        ]
