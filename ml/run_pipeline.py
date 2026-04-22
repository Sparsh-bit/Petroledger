#!/usr/bin/env python3
"""PetroLedger ML Sandbox — End-to-End Pipeline Demo.

Runs the full ML pipeline on synthetic data:

    1. Generate 1000 synthetic shifts
    2. Run rule-based anomaly detection on all
    3. Train Isolation Forest → evaluate on held-out test set
    4. Train XGBoost attribution → evaluate
    5. Run full pipeline on 10 sample shifts
    6. Print results table with all layer outputs

Usage:
    cd petroledger/ml
    python run_pipeline.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.anomaly_rules import AnomalyRulesService
from src.attribution import AttributionService
from src.isolation_forest import IsolationForestService
from src.narration import NarrationService
from src.synthetic_data import generate_shifts, save_to_csv


def _print_header(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main() -> None:
    # ── Step 1: Generate synthetic data ─────────────────────────────────
    _print_header("Step 1 — Generating 1000 Synthetic Shifts")
    all_shifts = generate_shifts(n=1000, seed=42)
    csv_path = save_to_csv(all_shifts)
    print(f"  Generated {len(all_shifts)} shifts")
    print(f"  Saved to {csv_path}")

    # Scenario distribution
    scenarios: dict[str, int] = {}
    for s in all_shifts:
        scenarios[s.scenario or "unknown"] = scenarios.get(s.scenario or "unknown", 0) + 1
    for scenario, count in sorted(scenarios.items()):
        print(f"    {scenario:25s}: {count:4d} ({count/len(all_shifts):.0%})")

    # ── Step 2: Rule-based anomaly detection ────────────────────────────
    _print_header("Step 2 — Rule-Based Anomaly Detection")
    rules_svc = AnomalyRulesService()

    flagged = 0
    total_anomalies = 0
    for s in all_shifts:
        anomalies = rules_svc.detect_anomalies(s)
        risk = rules_svc.calculate_risk_score(anomalies)
        if anomalies:
            flagged += 1
            total_anomalies += len(anomalies)

    print(f"  Shifts flagged     : {flagged}/{len(all_shifts)} ({flagged/len(all_shifts):.0%})")
    print(f"  Total anomalies    : {total_anomalies}")
    print(f"  Avg anomalies/flag : {total_anomalies/flagged:.1f}" if flagged else "  Avg anomalies/flag : N/A")

    # ── Step 3: Isolation Forest ────────────────────────────────────────
    _print_header("Step 3 — Isolation Forest Training & Evaluation")

    # 80/20 split
    random.seed(42)
    indices = list(range(len(all_shifts)))
    random.shuffle(indices)
    split = int(0.8 * len(all_shifts))
    train_set = [all_shifts[i] for i in indices[:split]]
    test_set = [all_shifts[i] for i in indices[split:]]

    if_svc = IsolationForestService()
    model_path = if_svc.train(train_set, version=1)
    print(f"  Model saved to {model_path}")
    print(f"  Train size: {len(train_set)}, Test size: {len(test_set)}")

    # Create ground truth: anomaly = NOT normal scenario
    true_labels = [s.scenario != "normal" for s in test_set]
    stats = if_svc.evaluate(test_set, true_labels)
    print(f"  Anomalies detected : {stats['anomalies_detected']}/{stats['total']}")
    print(f"  Anomaly rate       : {stats['anomaly_rate']:.1%}")
    if "confusion_matrix" in stats:
        cm = stats["confusion_matrix"]
        print(f"  Confusion Matrix   :")
        print(f"    TN={cm[0][0]:4d}  FP={cm[0][1]:4d}")
        print(f"    FN={cm[1][0]:4d}  TP={cm[1][1]:4d}")

    # ── Step 4: XGBoost Attribution ─────────────────────────────────────
    _print_header("Step 4 — XGBoost Attribution Training & Evaluation")

    attr_svc = AttributionService()
    attr_path = attr_svc.train_on_synthetic(n_per_class=500, version=1)
    print(f"  Model saved to {attr_path}")

    # Evaluate on a smaller labelled test set
    eval_data = generate_shifts(n=200, seed=99)
    eval_stats = attr_svc.evaluate(eval_data)
    print(f"  Accuracy           : {eval_stats['accuracy']:.1%}")
    cr = eval_stats["classification_report"]
    for cls_name in ["worker", "nozzle", "time_window", "unknown"]:
        if cls_name in cr:
            r = cr[cls_name]
            print(f"    {cls_name:15s}: precision={r['precision']:.2f}  recall={r['recall']:.2f}  f1={r['f1-score']:.2f}")

    # ── Step 5: Full pipeline on 10 samples (2 per scenario) ────────────
    _print_header("Step 5 — Full Pipeline on 10 Sample Shifts (diverse)")

    narration_svc = NarrationService()

    # Generate 2 per scenario for a diverse demo
    samples: list = []
    scenario_weights = [
        {"normal": 1.0, "suspicious_worker": 0.0, "nozzle_issues": 0.0, "night_anomaly": 0.0, "random_noise": 0.0},
        {"suspicious_worker": 1.0, "normal": 0.0, "nozzle_issues": 0.0, "night_anomaly": 0.0, "random_noise": 0.0},
        {"nozzle_issues": 1.0, "normal": 0.0, "suspicious_worker": 0.0, "night_anomaly": 0.0, "random_noise": 0.0},
        {"night_anomaly": 1.0, "normal": 0.0, "suspicious_worker": 0.0, "nozzle_issues": 0.0, "random_noise": 0.0},
        {"random_noise": 1.0, "normal": 0.0, "suspicious_worker": 0.0, "nozzle_issues": 0.0, "night_anomaly": 0.0},
    ]
    for idx, w in enumerate(scenario_weights):
        samples.extend(generate_shifts(n=2, weights=w, seed=100 + idx))

    print(f"  {'#':>2s}  {'Scenario':20s}  {'Risk':>6s}  {'IF':>8s}  {'Attribution':>14s}  {'Conf':>6s}")
    print(f"  {'─'*2}  {'─'*20}  {'─'*6}  {'─'*8}  {'─'*14}  {'─'*6}")

    narration_count = 0
    for i, s in enumerate(samples, 1):
        # Layer 1: Rules
        anomalies = rules_svc.detect_anomalies(s)
        risk = rules_svc.calculate_risk_score(anomalies)
        risk_label = "HIGH" if risk > 0.5 else "MED" if risk > 0.2 else "LOW"

        # Layer 2: Isolation Forest
        if_result = if_svc.predict(s)
        if_label = "ANOMALY" if if_result.is_anomaly else "normal"

        # Layer 3: Attribution
        attr_result = attr_svc.predict(s)

        print(
            f"  {i:2d}  {s.scenario or 'unknown':20s}  "
            f"{risk_label:>6s}  {if_label:>8s}  "
            f"{attr_result.predicted_class:>14s}  {attr_result.confidence:>5.0%}"
        )

        # Layer 4: Narration (first 3 HIGH-risk shifts, if API available)
        if narration_count < 3 and risk_label == "HIGH" and narration_svc.is_available:
            narration_count += 1
            context = {
                "shift_id": s.shift_id,
                "scenario": s.scenario,
                "risk_score": risk,
                "anomalies": anomalies,
                "isolation_forest": {
                    "is_anomaly": if_result.is_anomaly,
                    "score": if_result.anomaly_score,
                },
                "attribution": {
                    "class": attr_result.predicted_class,
                    "confidence": attr_result.confidence,
                },
            }
            narration = narration_svc.narrate(context)
            if narration:
                # Word-wrap narration for readability
                print(f"      📝 {narration[:200]}")

    if not narration_svc.is_available:
        print(f"\n  ⚠️  GROQ_API_KEY not set — narration layer skipped.")

    _print_header("Pipeline Complete ✓")


if __name__ == "__main__":
    main()
