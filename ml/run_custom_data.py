#!/usr/bin/env python3
"""PetroLedger ML Sandbox — Run All 4 Layers on Your Own CSV Data.

Usage:
    python3 run_custom_data.py                          # uses data/my_shifts.csv
    python3 run_custom_data.py path/to/your_file.csv    # custom path

The CSV must have these columns (order doesn't matter):
    shift_id, worker_id, pump_id, total_sales_volume, expected_volume,
    cash_collected, expected_cash, digital_payments_total, shift_duration_hours,
    is_night_shift, transaction_count, avg_transaction_amount,
    historical_avg_transaction, worker_shift_count, worker_flagged_rate,
    nozzle_count, price_per_litre, previous_shift_cash, running_7d_avg_cash

Missing columns will default to 0 / empty string / False.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.features import ShiftFeatures
from src.anomaly_rules import AnomalyRulesService
from src.isolation_forest import IsolationForestService
from src.attribution import AttributionService
from src.narration import NarrationService


# ── CSV Loader ──────────────────────────────────────────────────────────

# Fields and their default values / converters
_FLOAT_FIELDS = [
    "total_sales_volume", "expected_volume", "cash_collected", "expected_cash",
    "digital_payments_total", "shift_duration_hours", "avg_transaction_amount",
    "historical_avg_transaction", "worker_flagged_rate", "price_per_litre",
    "previous_shift_cash", "running_7d_avg_cash",
]
_INT_FIELDS = ["transaction_count", "worker_shift_count", "nozzle_count"]
_STR_FIELDS = ["shift_id", "worker_id", "scenario"]
_BOOL_FIELDS = ["is_night_shift"]


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes", "y")


def load_csv(path: Path) -> list[ShiftFeatures]:
    """Load a CSV file into a list of ShiftFeatures."""
    shifts: list[ShiftFeatures] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        available_cols = set(reader.fieldnames or [])
        print(f"  CSV columns found: {', '.join(sorted(available_cols))}")

        for row_num, row in enumerate(reader, 2):  # 2 because header is row 1
            try:
                d: dict = {}
                for field in _STR_FIELDS:
                    d[field] = row.get(field, "").strip()
                for field in _FLOAT_FIELDS:
                    val = row.get(field, "0").strip()
                    d[field] = float(val) if val else 0.0
                for field in _INT_FIELDS:
                    val = row.get(field, "0").strip()
                    d[field] = int(float(val)) if val else 0
                for field in _BOOL_FIELDS:
                    d[field] = _parse_bool(row.get(field, "false"))
                shifts.append(ShiftFeatures(**d))
            except Exception as exc:
                print(f"  ⚠️  Skipping row {row_num}: {exc}")
                continue

    return shifts


# ── Pipeline ────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main() -> None:
    # Resolve CSV path
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = Path(__file__).resolve().parent / "data" / "my_shifts.csv"

    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        print(f"   Place your CSV at: {csv_path}")
        print(f"   Or run: python3 run_custom_data.py <path_to_csv>")
        sys.exit(1)

    # ── Load ────────────────────────────────────────────────────────────
    _header(f"Loading Custom Data from {csv_path.name}")
    shifts = load_csv(csv_path)
    print(f"  Loaded {len(shifts)} shifts")

    if not shifts:
        print("  ❌ No valid rows found. Check your CSV format.")
        sys.exit(1)

    # ── Layer 1: Rules ──────────────────────────────────────────────────
    _header("Layer 1 — Rule-Based Anomaly Detection")
    rules_svc = AnomalyRulesService()

    results = []
    for s in shifts:
        anomalies = rules_svc.detect_anomalies(s)
        risk = rules_svc.calculate_risk_score(anomalies)
        results.append({"shift": s, "anomalies": anomalies, "risk": risk})

    flagged = sum(1 for r in results if r["anomalies"])
    print(f"  Shifts flagged: {flagged}/{len(shifts)}")

    # ── Layer 2: Isolation Forest ───────────────────────────────────────
    _header("Layer 2 — Isolation Forest")
    if_svc = IsolationForestService()

    model_path = Path(__file__).resolve().parent / "models" / "isolation_forest_v1.joblib"
    if model_path.exists():
        if_svc.load(str(model_path))
        print(f"  Loaded pre-trained model from {model_path.name}")
    else:
        print(f"  No pre-trained model found. Training on your data...")
        if len(shifts) >= 30:
            if_svc.train(shifts, version=1)
            print(f"  Trained on {len(shifts)} shifts")
        else:
            print(f"  ⚠️  Too few rows ({len(shifts)}) to train — need at least 30. Skipping IF.")
            if_svc = None

    for r in results:
        if if_svc:
            if_result = if_svc.predict(r["shift"])
            r["if_anomaly"] = if_result.is_anomaly
            r["if_score"] = if_result.anomaly_score
        else:
            r["if_anomaly"] = None
            r["if_score"] = None

    if if_svc:
        anomaly_count = sum(1 for r in results if r["if_anomaly"])
        print(f"  Anomalies detected: {anomaly_count}/{len(shifts)}")

    # ── Layer 3: XGBoost Attribution ────────────────────────────────────
    _header("Layer 3 — XGBoost Attribution")
    attr_svc = AttributionService()

    attr_model_path = Path(__file__).resolve().parent / "models" / "attribution_xgb_v1.joblib"
    if attr_model_path.exists():
        attr_svc.load(str(attr_model_path))
        print(f"  Loaded pre-trained model from {attr_model_path.name}")
    else:
        print(f"  No pre-trained model found. Training on synthetic data...")
        attr_svc.train_on_synthetic(n_per_class=500, version=1)
        print(f"  Trained and saved.")

    for r in results:
        attr_result = attr_svc.predict(r["shift"])
        r["attribution"] = attr_result.predicted_class
        r["attr_confidence"] = attr_result.confidence

    # ── Layer 4: GenAI Narration ────────────────────────────────────────
    _header("Layer 4 — GenAI Narration (Groq)")
    narration_svc = NarrationService()

    if not narration_svc.is_available:
        print("  ⚠️  GROQ_API_KEY not set — narration skipped.")
    else:
        print("  ✓ Groq API available")

    # ── Results Table ───────────────────────────────────────────────────
    _header("Results")

    print(f"  {'#':>3s}  {'Shift ID':16s}  {'Risk':>6s}  {'IF':>8s}  {'Attribution':>14s}  {'Conf':>6s}  {'Anomalies':>9s}")
    print(f"  {'─'*3}  {'─'*16}  {'─'*6}  {'─'*8}  {'─'*14}  {'─'*6}  {'─'*9}")

    narration_count = 0
    for i, r in enumerate(results, 1):
        risk_label = "HIGH" if r["risk"] > 0.5 else "MED" if r["risk"] > 0.2 else "LOW"
        if_label = "ANOMALY" if r["if_anomaly"] else "normal" if r["if_anomaly"] is not None else "N/A"
        shift_id = (r["shift"].shift_id or f"row-{i}")[:16]
        n_anomalies = len(r["anomalies"])

        print(
            f"  {i:3d}  {shift_id:16s}  "
            f"{risk_label:>6s}  {if_label:>8s}  "
            f"{r['attribution']:>14s}  {r['attr_confidence']:>5.0%}  "
            f"{n_anomalies:>9d}"
        )

        # Narrate top 3 HIGH-risk shifts
        if narration_count < 3 and risk_label == "HIGH" and narration_svc.is_available:
            narration_count += 1
            context = {
                "shift_id": r["shift"].shift_id,
                "worker_id": r["shift"].worker_id,
                "risk_score": r["risk"],
                "anomalies": r["anomalies"],
                "isolation_forest": {"is_anomaly": r["if_anomaly"], "score": r["if_score"]},
                "attribution": {"class": r["attribution"], "confidence": r["attr_confidence"]},
            }
            narration = narration_svc.narrate(context)
            if narration:
                print(f"        📝 {narration[:200]}")
                print()

    # ── Summary ─────────────────────────────────────────────────────────
    _header("Summary")
    high = sum(1 for r in results if r["risk"] > 0.5)
    med = sum(1 for r in results if 0.2 < r["risk"] <= 0.5)
    low = sum(1 for r in results if r["risk"] <= 0.2)
    print(f"  Total shifts : {len(shifts)}")
    print(f"  HIGH risk    : {high}")
    print(f"  MEDIUM risk  : {med}")
    print(f"  LOW risk     : {low}")
    if if_svc:
        print(f"  IF anomalies : {sum(1 for r in results if r['if_anomaly'])}")
    print()


if __name__ == "__main__":
    main()
