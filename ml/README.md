# PetroLedger ML Sandbox

> ⚠️ **Throwaway sandbox** — this code is for prototyping and validation only. The production backend will have its own implementations that import the *logic*, not this code directly.

Standalone ML module for prototyping and validating PetroLedger's four intelligence layers against synthetic Indian petrol-pump data.

## Quick Start

```bash
cd petroledger/ml
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run full pipeline demo
python run_pipeline.py
```

## Modules

| Module | Description |
|---|---|
| `src/features.py` | Standalone `ShiftFeatures` dataclass — same fields as backend, no DB deps |
| `src/synthetic_data.py` | Generates realistic shift data (5 scenarios: normal, suspicious worker, nozzle issues, night anomaly, random noise) |
| `src/anomaly_rules.py` | Rule-based anomaly detection — exact port of backend's 6 checks + risk scoring |
| `src/isolation_forest.py` | Isolation Forest training + prediction (15-feature vector, contamination=0.05) |
| `src/attribution.py` | XGBoost attribution (12-feature vector, 4 classes: worker/nozzle/time_window/unknown) |
| `src/narration.py` | GenAI narration via Groq API (LLaMA 3.1 8B) |

## Pipeline

`run_pipeline.py` demos the full stack:

1. Generate 1000 synthetic shifts
2. Run rule-based anomaly detection
3. Train & evaluate Isolation Forest
4. Train & evaluate XGBoost attribution
5. Run all 4 layers on 10 sample shifts, print results table

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Optional | Enables the narration layer. Without it, narration is skipped gracefully. |

Create a `.env` file in `ml/`:
```
GROQ_API_KEY=gsk_...
```

## Directory Layout

```
ml/
├── data/              ← Generated CSV datasets
├── models/            ← Trained model artifacts (.joblib)
├── src/               ← Source modules
├── tests/             ← pytest test suite
├── notebooks/         ← Optional Jupyter exploration
├── run_pipeline.py    ← End-to-end demo
└── requirements.txt   ← Dependencies
```
