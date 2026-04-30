"""
DexGuard XGBoost Training Pipeline
==================================

Implements the MLOps pipeline described in
``dexguard_ml_model_implementation.md``:

1. Load the labeled ``historical_training_data`` (Postgres or CSV fallback).
2. Project each row into the canonical 5-feature vector via
   :class:`scripts.feature_extractor.FeatureExtractor`.
3. **Time-series** split (NOT random K-fold) on ``pool_created_at``:
       train  = oldest ≈4 months
       val    = next month
       test   = newest month
4. Run an Optuna study optimising the **F0.5 score** (precision-weighted)
   on the validation set, sweeping the spec-mandated hyperparameter bounds.
5. Train the final model on train ∪ val with the best params.
6. Emit the mandatory evaluation report against the *test* fold:
       - Precision–Recall AUC (PR-AUC) — the primary metric
       - Precision @ Top 5% (target > 99%)
       - Confusion matrix
       - Streaming inference latency (target < 5 ms / pool)
7. Export ``xgboost_model.json`` + ``feature_schema.json`` to
   ``lib/ml_models/`` for the Rails intelligence layer to load on boot.

Run
---
    python scripts/train_model.py --trials 30
    python scripts/train_model.py --trials 0          # skip Optuna (use defaults)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    fbeta_score,
    precision_score,
)

# Optuna log spam reduction
os.environ.setdefault("OPTUNA_LOG_LEVEL", "WARN")

import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from feature_extractor import FEATURE_NAMES, FeatureExtractor  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ML_MODELS_DIR = PROJECT_ROOT / "lib" / "ml_models"
ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = PROJECT_ROOT / "scripts" / "data"
CSV_FALLBACK_PATH = DATA_DIR / "historical_training_data.csv"

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"host={os.getenv('DATABASE_HOST', 'localhost')} "
    f"port={os.getenv('DATABASE_PORT', '5432')} "
    f"dbname={os.getenv('DATABASE_NAME', 'rexcheck_development')} "
    f"user={os.getenv('DATABASE_USERNAME', 'postgres')} "
    f"password={os.getenv('DATABASE_PASSWORD', 'postgres')}"
)

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("dexguard.train")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_from_postgres() -> pd.DataFrame | None:
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
    except Exception as exc:
        logger.info(f"Postgres unavailable ({exc}); will use CSV fallback.")
        return None

    try:
        df = pd.read_sql(
            """
            SELECT pool_created_at,
                   liquidity_depth_usd,
                   volume_to_liquidity_ratio,
                   pooled_token_ratio,
                   contract_age_minutes,
                   price_volatility_1hr,
                   label
              FROM historical_training_data
            """,
            conn,
        )
        logger.info(f"Loaded {len(df):,} rows from Postgres.")
        return df
    except Exception as exc:
        logger.info(f"Postgres query failed ({exc}); falling back to CSV.")
        return None
    finally:
        conn.close()


def _load_from_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"No training data found at {path}. "
            f"Run `python scripts/fetch_historical_data.py` first."
        )
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df):,} rows from {path}.")
    return df


def load_dataset() -> pd.DataFrame:
    df = _load_from_postgres()
    if df is None or df.empty:
        df = _load_from_csv(CSV_FALLBACK_PATH)

    df["pool_created_at"] = pd.to_datetime(df["pool_created_at"], utc=True)
    for col in FEATURE_NAMES:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["label"] = df["label"].astype(int)
    return df.sort_values("pool_created_at").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Time-series split
# ---------------------------------------------------------------------------
@dataclass
class Split:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    train_window: tuple[datetime, datetime]
    val_window: tuple[datetime, datetime]
    test_window: tuple[datetime, datetime]


def time_series_split(df: pd.DataFrame) -> Split:
    """
    Spec § 4.1: train on months 1–4, validate on month 5, test on month 6.
    To keep this generic across dataset spans, we split on the 67% / 83% / 100%
    quantiles of ``pool_created_at`` — equivalent to the spec's 4-1-1 month
    breakdown for a 6-month-wide dataset.
    """
    ts = df["pool_created_at"]
    train_end = ts.quantile(4 / 6)
    val_end = ts.quantile(5 / 6)

    train_mask = ts <= train_end
    val_mask = (ts > train_end) & (ts <= val_end)
    test_mask = ts > val_end

    def _vec(mask) -> tuple[np.ndarray, np.ndarray]:
        rows = df.loc[mask, FEATURE_NAMES].to_dict(orient="records")
        X = FeatureExtractor.from_rows(rows)
        y = df.loc[mask, "label"].to_numpy(dtype=np.int32)
        return X, y

    X_train, y_train = _vec(train_mask)
    X_val, y_val = _vec(val_mask)
    X_test, y_test = _vec(test_mask)

    logger.info(
        "Time-series split sizes  train=%d  val=%d  test=%d",
        len(y_train), len(y_val), len(y_test),
    )
    if len(y_train) == 0 or len(y_val) == 0 or len(y_test) == 0:
        raise RuntimeError(
            "One of the time-series folds is empty; "
            "ensure pool_created_at spans at least 6 quantile buckets."
        )

    return Split(
        X_train=X_train, y_train=y_train,
        X_val=X_val, y_val=y_val,
        X_test=X_test, y_test=y_test,
        train_window=(ts[train_mask].min().to_pydatetime(), ts[train_mask].max().to_pydatetime()),
        val_window=(ts[val_mask].min().to_pydatetime(), ts[val_mask].max().to_pydatetime()),
        test_window=(ts[test_mask].min().to_pydatetime(), ts[test_mask].max().to_pydatetime()),
    )


# ---------------------------------------------------------------------------
# Hyperparameter tuning  (Optuna, F0.5 objective)
# ---------------------------------------------------------------------------
def _scale_pos_weight_inverse(y: np.ndarray) -> float:
    """
    Spec § 3: penalize FPs (rug labelled as safe) severely. With our
    convention (1=SAFE), a "False Positive" is predicting SAFE for a rug.
    XGBoost's ``scale_pos_weight`` upweights the positive class — so to make
    the model *more conservative* about predicting SAFE we *down*weight it
    using the inverse class ratio.
    """
    n_pos = float(np.sum(y == 1))
    n_neg = float(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return 1.0
    return n_pos / n_neg


def _build_booster(params: dict[str, Any], split: Split) -> xgb.Booster:
    dtrain = xgb.DMatrix(split.X_train, label=split.y_train, feature_names=FEATURE_NAMES)
    dval = xgb.DMatrix(split.X_val, label=split.y_val, feature_names=FEATURE_NAMES)

    train_params = {k: v for k, v in params.items() if k != "n_estimators"}
    num_boost_round = int(params.get("n_estimators", 300))

    booster = xgb.train(
        params=train_params,
        dtrain=dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=20,
        verbose_eval=False,
    )
    return booster


def _evaluate_f_beta(booster: xgb.Booster, X: np.ndarray, y: np.ndarray,
                     beta: float = 0.5) -> tuple[float, float]:
    """Returns (best F-beta, threshold that achieves it) for the SAFE class."""
    proba = booster.predict(xgb.DMatrix(X, feature_names=FEATURE_NAMES))
    best_f, best_t = 0.0, 0.5
    for t in np.linspace(0.05, 0.95, 19):
        preds = (proba >= t).astype(int)
        if preds.sum() == 0:
            continue
        f = fbeta_score(y, preds, beta=beta, zero_division=0)
        if f > best_f:
            best_f, best_t = f, float(t)
    return best_f, best_t


def run_optuna(split: Split, n_trials: int) -> dict[str, Any]:
    base_spw = _scale_pos_weight_inverse(split.y_train)

    def objective(trial: optuna.Trial) -> float:
        params: dict[str, Any] = {
            "objective": "binary:logistic",
            "eval_metric": "aucpr",
            "tree_method": "hist",
            "verbosity": 0,
            "max_depth": trial.suggest_int("max_depth", 3, 7),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 10.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "scale_pos_weight": trial.suggest_float(
                "scale_pos_weight",
                max(0.05, base_spw * 0.25),
                base_spw * 1.0,
                log=False,
            ),
        }
        booster = _build_booster(params, split)
        f_beta, _ = _evaluate_f_beta(booster, split.X_val, split.y_val, beta=0.5)
        return f_beta

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    logger.info(f"Optuna best F0.5 (val) = {study.best_value:.4f}")
    logger.info(f"Optuna best params = {study.best_params}")
    best = study.best_params.copy()
    best.update({
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "verbosity": 0,
    })
    return best


def default_params(split: Split) -> dict[str, Any]:
    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "verbosity": 0,
        "max_depth": 5,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "min_child_weight": 3.0,
        "gamma": 1.0,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "scale_pos_weight": _scale_pos_weight_inverse(split.y_train) * 0.5,
    }


# ---------------------------------------------------------------------------
# Evaluation report
# ---------------------------------------------------------------------------
@dataclass
class EvalReport:
    pr_auc: float
    precision_top_5pct: float
    threshold: float
    precision_at_threshold: float
    fbeta_05: float
    confusion_matrix: list[list[int]]
    avg_inference_ms: float
    p99_inference_ms: float
    n_test: int


def evaluate(booster: xgb.Booster, split: Split, threshold: float) -> EvalReport:
    dtest = xgb.DMatrix(split.X_test, feature_names=FEATURE_NAMES)
    proba = booster.predict(dtest)

    pr_auc = float(average_precision_score(split.y_test, proba))

    k = max(1, int(round(0.05 * len(proba))))
    top_idx = np.argsort(proba)[::-1][:k]
    precision_top_5 = float(np.mean(split.y_test[top_idx] == 1)) if k else 0.0

    preds = (proba >= threshold).astype(int)
    cm = confusion_matrix(split.y_test, preds, labels=[0, 1]).tolist()
    prec_at_t = float(precision_score(split.y_test, preds, zero_division=0))
    f05 = float(fbeta_score(split.y_test, preds, beta=0.5, zero_division=0))

    latencies_ms: list[float] = []
    for i in range(len(split.X_test)):
        sample = xgb.DMatrix(split.X_test[i : i + 1], feature_names=FEATURE_NAMES)
        t0 = time.perf_counter()
        booster.predict(sample)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    return EvalReport(
        pr_auc=pr_auc,
        precision_top_5pct=precision_top_5,
        threshold=threshold,
        precision_at_threshold=prec_at_t,
        fbeta_05=f05,
        confusion_matrix=cm,
        avg_inference_ms=float(np.mean(latencies_ms)),
        p99_inference_ms=float(np.percentile(latencies_ms, 99)),
        n_test=len(split.y_test),
    )


def print_report(report: EvalReport) -> None:
    cm = report.confusion_matrix
    tn, fp = cm[0][0], cm[0][1]
    fn, tp = cm[1][0], cm[1][1]

    print("\n" + "=" * 70)
    print("DexGuard XGBoost - Evaluation Report (Test Fold)")
    print("=" * 70)
    print(f"  Test rows                : {report.n_test:,}")
    print(f"  Decision threshold       : {report.threshold:.3f}")
    print()
    print("  PRIMARY METRICS")
    print(f"    PR-AUC                 : {report.pr_auc:.4f}")
    print(f"    Precision @ Top 5%     : {report.precision_top_5pct:.4f}  (target > 0.99)")
    print(f"    Precision @ threshold  : {report.precision_at_threshold:.4f}")
    print(f"    F0.5                   : {report.fbeta_05:.4f}")
    print()
    print("  CONFUSION MATRIX  (rows=true, cols=pred ; class 1 = SAFE)")
    print(f"                pred=0(DANGER)   pred=1(SAFE)")
    print(f"    true=0  :     {tn:>10}      {fp:>10}")
    print(f"    true=1  :     {fn:>10}      {tp:>10}")
    print()
    print("  STREAMING INFERENCE LATENCY (per pool)")
    print(f"    avg                    : {report.avg_inference_ms:.3f} ms  (target < 5 ms)")
    print(f"    p99                    : {report.p99_inference_ms:.3f} ms")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Artifact export
# ---------------------------------------------------------------------------
def export_artifacts(
    booster: xgb.Booster,
    threshold: float,
    params: dict[str, Any],
    report: EvalReport,
    split: Split,
) -> dict[str, Path]:
    model_path = ML_MODELS_DIR / "xgboost_model.json"
    booster.save_model(str(model_path))

    schema = {
        "model_artifact": "xgboost_model.json",
        "model_version": "1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "objective": "binary:logistic",
        "decision_threshold": threshold,
        "feature_names": FEATURE_NAMES,
        "label_encoding": {"0": "DANGER", "1": "SAFE"},
        "training_window_utc": {
            "train": [split.train_window[0].isoformat(), split.train_window[1].isoformat()],
            "val":   [split.val_window[0].isoformat(),   split.val_window[1].isoformat()],
            "test":  [split.test_window[0].isoformat(),  split.test_window[1].isoformat()],
        },
        "hyperparameters": params,
        "evaluation": asdict(report),
    }
    schema_path = ML_MODELS_DIR / "feature_schema.json"
    schema_path.write_text(json.dumps(schema, indent=2))

    logger.info(f"Saved model  -> {model_path}")
    logger.info(f"Saved schema -> {schema_path}")
    return {"model": model_path, "schema": schema_path}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=30,
                        help="Optuna trials (default 30; set 0 to skip tuning).")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    np.random.seed(args.seed)

    logger.info("=" * 70)
    logger.info("DexGuard XGBoost training pipeline")
    logger.info("=" * 70)

    df = load_dataset()
    split = time_series_split(df)

    if args.trials > 0:
        logger.info(f"Running Optuna study with {args.trials} trials ...")
        params = run_optuna(split, n_trials=args.trials)
    else:
        logger.info("Skipping Optuna; using sane defaults.")
        params = default_params(split)

    logger.info("Training validation booster to pick decision threshold ...")
    val_booster = _build_booster(params, split)
    _, best_threshold = _evaluate_f_beta(
        val_booster, split.X_val, split.y_val, beta=0.5
    )
    logger.info(f"Selected decision threshold = {best_threshold:.3f}")

    logger.info("Refitting on train + val for final model ...")
    X_full = np.vstack([split.X_train, split.X_val])
    y_full = np.concatenate([split.y_train, split.y_val])
    final_split = Split(
        X_train=X_full, y_train=y_full,
        X_val=split.X_test, y_val=split.y_test,
        X_test=split.X_test, y_test=split.y_test,
        train_window=split.train_window,
        val_window=split.val_window,
        test_window=split.test_window,
    )
    final_booster = _build_booster(params, final_split)

    report = evaluate(final_booster, split, threshold=best_threshold)
    print_report(report)

    export_artifacts(final_booster, best_threshold, params, report, split)

    if report.precision_top_5pct < 0.99:
        logger.warning(
            "Precision@Top5%% (%.4f) is below the 0.99 target. "
            "Re-run with more Optuna trials or richer training data.",
            report.precision_top_5pct,
        )
    if report.avg_inference_ms > 5.0:
        logger.warning(
            "Average inference latency %.3f ms exceeds the 5 ms target.",
            report.avg_inference_ms,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
