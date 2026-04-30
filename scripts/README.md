# DexGuard ML Pipeline

End-to-end training pipeline for the XGBoost rug/honeypot classifier
specified in [`dexguard_ml_model_implementation.md`](../dexguard_ml_model_implementation.md).

## Layout

| File | Role |
| --- | --- |
| `requirements.txt`           | Python deps for the training pipeline (Python 3.12+). |
| `feature_extractor.py`       | Canonical 5-feature vector extractor. The Rails backend reads `lib/ml_models/feature_schema.json` to mirror this order. |
| `fetch_historical_data.py`   | Builds `historical_training_data` (Postgres) with synthetic-or-real labelled pool data. CSV fallback at `scripts/data/historical_training_data.csv` when Postgres is offline. |
| `train_model.py`             | Time-series split → Optuna F0.5 study → evaluation report → exports `xgboost_model.json` + `feature_schema.json` to `lib/ml_models/`. |

## Quick start

```powershell
# 1. one-time setup
py -3.12 -m venv .venv-ml
.\.venv-ml\Scripts\python -m pip install -r scripts/requirements.txt

# 2. build labelled training data (synthetic — fast, offline-safe)
.\.venv-ml\Scripts\python scripts/fetch_historical_data.py --mode synthetic --rows 10000

# 3. train + tune + export model artifacts
.\.venv-ml\Scripts\python scripts/train_model.py --trials 30
```

## Real GeckoTerminal mode

```powershell
.\.venv-ml\Scripts\python scripts/fetch_historical_data.py --mode real --target 10000
```

The real mode iterates `/networks/<net>/pools`, filters to pools created
30–180 days ago, fetches first-hour OHLCV per pool, and applies the spec's
labelling rules. It is rate-limited (~30 req/min) — full 10k backfill takes
hours and you may want to run it inside the `worker/` container.

## Storage

`fetch_historical_data.py` first attempts to write to Postgres
(`historical_training_data`). If the connection fails it logs a warning and
falls back to CSV. `train_model.py` reads from whichever is available.

## Output artifacts

`train_model.py` writes to `lib/ml_models/`:

- `xgboost_model.json` — JSON-serialised booster (cross-language safe; **not** pickle)
- `feature_schema.json` — feature order + decision threshold + training window + evaluation report

The Rails intelligence layer must load both at boot and feed inference vectors
in the exact `feature_names` order published in the schema.
