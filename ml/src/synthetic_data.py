"""PetroLedger ML Sandbox — Synthetic Shift Data Generator.

Generates realistic Indian petrol-pump shift data *without* a database.
Each call produces a list of :class:`ShiftFeatures` with a configurable
scenario distribution:

    ┌──────────────────────┬──────┐
    │ Scenario             │   %  │
    ├──────────────────────┼──────┤
    │ Normal               │  60  │
    │ Suspicious worker    │  15  │
    │ Nozzle issues        │  10  │
    │ Night shift anomaly  │  10  │
    │ Random noise         │   5  │
    └──────────────────────┴──────┘

Outputs can be saved to ``data/synthetic_shifts.csv`` for reuse.
"""

from __future__ import annotations

import csv
import os
import random
import uuid
from pathlib import Path

from .features import ShiftFeatures

# ── Default scenario weights ───────────────────────────────────────────

DEFAULT_WEIGHTS: dict[str, float] = {
    "normal": 0.60,
    "suspicious_worker": 0.15,
    "nozzle_issues": 0.10,
    "night_anomaly": 0.10,
    "random_noise": 0.05,
}

# ── Realistic Indian-pump parameters ───────────────────────────────────

_FUEL_PRICE = 100.0  # ₹ per litre (simplified)


def _pick_scenario(weights: dict[str, float]) -> str:
    """Weighted random scenario selection."""
    scenarios = list(weights.keys())
    probs = list(weights.values())
    return random.choices(scenarios, weights=probs, k=1)[0]


# ── Per-scenario generators ────────────────────────────────────────────


def _gen_normal() -> ShiftFeatures:
    """Normal shift — small variance, typical patterns."""
    duration = round(random.uniform(6, 10), 2)
    start_hour = random.choice([6, 7, 8, 14, 15, 16])
    is_night = False
    day = random.randint(0, 6)

    volume = round(random.uniform(800, 2000), 2)
    expected_cash = round(volume * _FUEL_PRICE, 2)

    # Digital ≈ expected (small variance)
    digital = round(expected_cash * random.uniform(0.95, 1.05), 2)
    upi_ratio = random.uniform(0.3, 0.7)
    upi_amount = round(digital * upi_ratio, 2)
    pos_amount = round(digital - upi_amount, 2)

    upi_count = random.randint(15, 60)
    pos_count = random.randint(5, 30)
    total_count = upi_count + pos_count
    avg_txn = round(digital / total_count, 2) if total_count > 0 else 0.0
    max_txn = round(avg_txn * random.uniform(1.5, 2.5), 2)

    nozzles = random.randint(3, 6)
    w_avg_var = round(random.uniform(0, 200), 2)
    w_std = round(random.uniform(0, 100), 2)
    w_count = random.randint(10, 50)
    w_flagged = round(random.uniform(0, 0.15), 4)

    return ShiftFeatures(
        shift_duration_hours=duration,
        shift_start_hour=start_hour,
        is_night_shift=is_night,
        day_of_week=day,
        total_upi_amount=upi_amount,
        total_pos_amount=pos_amount,
        total_digital_amount=digital,
        upi_transaction_count=upi_count,
        pos_transaction_count=pos_count,
        avg_transaction_amount=avg_txn,
        max_transaction_amount=max_txn,
        total_volume_dispensed=volume,
        expected_cash_from_volume=expected_cash,
        nozzle_count_active=nozzles,
        worker_avg_variance=w_avg_var,
        worker_variance_std=w_std,
        worker_shift_count=w_count,
        worker_flagged_rate=w_flagged,
        label="unknown",
        scenario="normal",
    )


def _gen_suspicious_worker() -> ShiftFeatures:
    """Worker with historically high flagged rate and large variance."""
    duration = round(random.uniform(6, 10), 2)
    start_hour = random.choice([6, 7, 8, 14, 15, 16])
    is_night = False
    day = random.randint(0, 6)

    volume = round(random.uniform(800, 2000), 2)
    expected_cash = round(volume * _FUEL_PRICE, 2)

    # Significant cash-digital mismatch (worker skimming)
    digital = round(expected_cash * random.uniform(0.70, 0.85), 2)
    upi_ratio = random.uniform(0.3, 0.7)
    upi_amount = round(digital * upi_ratio, 2)
    pos_amount = round(digital - upi_amount, 2)

    upi_count = random.randint(10, 40)
    pos_count = random.randint(3, 15)
    total_count = upi_count + pos_count
    avg_txn = round(digital / total_count, 2) if total_count > 0 else 0.0
    max_txn = round(avg_txn * random.uniform(2, 4), 2)

    nozzles = random.randint(3, 6)
    w_avg_var = round(random.uniform(1500, 5000), 2)
    w_std = round(random.uniform(500, 2000), 2)
    w_count = random.randint(15, 50)
    w_flagged = round(random.uniform(0.35, 0.80), 4)

    return ShiftFeatures(
        shift_duration_hours=duration,
        shift_start_hour=start_hour,
        is_night_shift=is_night,
        day_of_week=day,
        total_upi_amount=upi_amount,
        total_pos_amount=pos_amount,
        total_digital_amount=digital,
        upi_transaction_count=upi_count,
        pos_transaction_count=pos_count,
        avg_transaction_amount=avg_txn,
        max_transaction_amount=max_txn,
        total_volume_dispensed=volume,
        expected_cash_from_volume=expected_cash,
        nozzle_count_active=nozzles,
        worker_avg_variance=w_avg_var,
        worker_variance_std=w_std,
        worker_shift_count=w_count,
        worker_flagged_rate=w_flagged,
        label="worker",
        scenario="suspicious_worker",
    )


def _gen_nozzle_issues() -> ShiftFeatures:
    """Few active nozzles, volume anomalies — possible meter tampering."""
    duration = round(random.uniform(6, 10), 2)
    start_hour = random.choice([6, 7, 8, 14, 15, 16])
    is_night = False
    day = random.randint(0, 6)

    # Volume is suspiciously low or high for the nozzle count
    volume = round(random.uniform(200, 600), 2)
    expected_cash = round(volume * _FUEL_PRICE, 2)

    # Digital close to expected but volume itself is odd
    digital = round(expected_cash * random.uniform(0.80, 0.92), 2)
    upi_ratio = random.uniform(0.3, 0.7)
    upi_amount = round(digital * upi_ratio, 2)
    pos_amount = round(digital - upi_amount, 2)

    upi_count = random.randint(5, 20)
    pos_count = random.randint(2, 10)
    total_count = upi_count + pos_count
    avg_txn = round(digital / total_count, 2) if total_count > 0 else 0.0
    max_txn = round(avg_txn * random.uniform(1.5, 3), 2)

    nozzles = random.randint(1, 2)  # key indicator
    w_avg_var = round(random.uniform(100, 800), 2)
    w_std = round(random.uniform(50, 400), 2)
    w_count = random.randint(5, 30)
    w_flagged = round(random.uniform(0.05, 0.25), 4)

    return ShiftFeatures(
        shift_duration_hours=duration,
        shift_start_hour=start_hour,
        is_night_shift=is_night,
        day_of_week=day,
        total_upi_amount=upi_amount,
        total_pos_amount=pos_amount,
        total_digital_amount=digital,
        upi_transaction_count=upi_count,
        pos_transaction_count=pos_count,
        avg_transaction_amount=avg_txn,
        max_transaction_amount=max_txn,
        total_volume_dispensed=volume,
        expected_cash_from_volume=expected_cash,
        nozzle_count_active=nozzles,
        worker_avg_variance=w_avg_var,
        worker_variance_std=w_std,
        worker_shift_count=w_count,
        worker_flagged_rate=w_flagged,
        label="nozzle",
        scenario="nozzle_issues",
    )


def _gen_night_anomaly() -> ShiftFeatures:
    """Night shift with high variance — higher theft risk."""
    duration = round(random.uniform(8, 12), 2)
    start_hour = random.choice([22, 23, 0, 1, 2])
    is_night = True
    day = random.randint(0, 6)

    volume = round(random.uniform(400, 1200), 2)
    expected_cash = round(volume * _FUEL_PRICE, 2)

    # Large cash-digital gap during night
    digital = round(expected_cash * random.uniform(0.60, 0.80), 2)
    upi_ratio = random.uniform(0.2, 0.5)
    upi_amount = round(digital * upi_ratio, 2)
    pos_amount = round(digital - upi_amount, 2)

    upi_count = random.randint(3, 15)
    pos_count = random.randint(1, 8)
    total_count = upi_count + pos_count
    avg_txn = round(digital / total_count, 2) if total_count > 0 else 0.0
    max_txn = round(avg_txn * random.uniform(2, 5), 2)

    nozzles = random.randint(2, 4)
    w_avg_var = round(random.uniform(300, 2000), 2)
    w_std = round(random.uniform(100, 1000), 2)
    w_count = random.randint(5, 30)
    w_flagged = round(random.uniform(0.10, 0.40), 4)

    return ShiftFeatures(
        shift_duration_hours=duration,
        shift_start_hour=start_hour,
        is_night_shift=is_night,
        day_of_week=day,
        total_upi_amount=upi_amount,
        total_pos_amount=pos_amount,
        total_digital_amount=digital,
        upi_transaction_count=upi_count,
        pos_transaction_count=pos_count,
        avg_transaction_amount=avg_txn,
        max_transaction_amount=max_txn,
        total_volume_dispensed=volume,
        expected_cash_from_volume=expected_cash,
        nozzle_count_active=nozzles,
        worker_avg_variance=w_avg_var,
        worker_variance_std=w_std,
        worker_shift_count=w_count,
        worker_flagged_rate=w_flagged,
        label="time_window",
        scenario="night_anomaly",
    )


def _gen_random_noise() -> ShiftFeatures:
    """Random edge cases — zero digital, extreme values, etc."""
    duration = round(random.uniform(1, 14), 2)
    start_hour = random.randint(0, 23)
    is_night = start_hour >= 22 or start_hour < 6
    day = random.randint(0, 6)

    volume = round(random.uniform(0, 3000), 2)
    expected_cash = round(volume * _FUEL_PRICE, 2)

    # Sometimes zero digital (all-cash shift)
    if random.random() < 0.3:
        digital = 0.0
    else:
        digital = round(expected_cash * random.uniform(0.5, 1.5), 2)

    upi_ratio = random.uniform(0, 1)
    upi_amount = round(digital * upi_ratio, 2)
    pos_amount = round(digital - upi_amount, 2)

    upi_count = random.randint(0, 80)
    pos_count = random.randint(0, 40)
    total_count = upi_count + pos_count
    avg_txn = round(digital / total_count, 2) if total_count > 0 else 0.0
    max_txn = round(avg_txn * random.uniform(1, 10), 2)

    nozzles = random.randint(0, 8)
    w_avg_var = round(random.uniform(0, 5000), 2)
    w_std = round(random.uniform(0, 3000), 2)
    w_count = random.randint(0, 60)
    w_flagged = round(random.uniform(0, 1.0), 4)

    return ShiftFeatures(
        shift_duration_hours=duration,
        shift_start_hour=start_hour,
        is_night_shift=is_night,
        day_of_week=day,
        total_upi_amount=upi_amount,
        total_pos_amount=pos_amount,
        total_digital_amount=digital,
        upi_transaction_count=upi_count,
        pos_transaction_count=pos_count,
        avg_transaction_amount=avg_txn,
        max_transaction_amount=max_txn,
        total_volume_dispensed=volume,
        expected_cash_from_volume=expected_cash,
        nozzle_count_active=nozzles,
        worker_avg_variance=w_avg_var,
        worker_variance_std=w_std,
        worker_shift_count=w_count,
        worker_flagged_rate=w_flagged,
        label="unknown",
        scenario="random_noise",
    )


# ── Scenario dispatcher ────────────────────────────────────────────────

_GENERATORS = {
    "normal": _gen_normal,
    "suspicious_worker": _gen_suspicious_worker,
    "nozzle_issues": _gen_nozzle_issues,
    "night_anomaly": _gen_night_anomaly,
    "random_noise": _gen_random_noise,
}


# ── Public API ──────────────────────────────────────────────────────────


def generate_shifts(
    n: int = 1000,
    weights: dict[str, float] | None = None,
    seed: int | None = None,
) -> list[ShiftFeatures]:
    """Generate *n* synthetic shift feature records.

    Parameters
    ----------
    n : int
        Number of records to generate.
    weights : dict, optional
        Scenario → probability mapping.  Defaults to ``DEFAULT_WEIGHTS``.
    seed : int, optional
        Random seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)
    w = weights or DEFAULT_WEIGHTS

    shifts: list[ShiftFeatures] = []
    for _ in range(n):
        scenario = _pick_scenario(w)
        shifts.append(_GENERATORS[scenario]())
    return shifts


def save_to_csv(
    shifts: list[ShiftFeatures],
    path: str | Path | None = None,
) -> Path:
    """Write shift features to a CSV file.  Returns the written path."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "synthetic_shifts.csv"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = list(ShiftFeatures.__dataclass_fields__.keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in shifts:
            writer.writerow(s.to_dict())
    return path


def load_from_csv(path: str | Path | None = None) -> list[ShiftFeatures]:
    """Read shift features back from a CSV file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "synthetic_shifts.csv"
    path = Path(path)

    shifts: list[ShiftFeatures] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Coerce types
            for key in row:
                val = row[key]
                if val == "":
                    row[key] = None
                    continue
                if key in ("is_night_shift",):
                    row[key] = val.lower() in ("true", "1")
                elif key in (
                    "shift_start_hour", "day_of_week",
                    "upi_transaction_count", "pos_transaction_count",
                    "nozzle_count_active", "worker_shift_count",
                ):
                    row[key] = int(row[key])
                elif key in (
                    "shift_duration_hours", "total_upi_amount", "total_pos_amount",
                    "total_digital_amount", "avg_transaction_amount",
                    "max_transaction_amount", "total_volume_dispensed",
                    "expected_cash_from_volume", "worker_avg_variance",
                    "worker_variance_std", "worker_flagged_rate",
                ):
                    row[key] = float(row[key])
            shifts.append(ShiftFeatures.from_dict(row))
    return shifts
