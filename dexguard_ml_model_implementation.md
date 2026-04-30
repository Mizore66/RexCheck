# SYSTEM DIRECTIVE: DEXGUARD ML MODEL IMPLEMENTATION PLAN
**Target Agent:** Claude Opus 4.7 (or equivalent High-Capability Coding Agent)
**Role:** Senior MLOps Engineer & Data Architect.
**Execution Parameters:** NO ASSUMPTIONS ALLOWED. You must follow this specification exactly as written. This document dictates the end-to-end machine learning pipeline, from historical data scraping to the training and export of the XGBoost model. Do not use Deep Learning/Neural Networks for this MVP; adhere to the highly efficient, low-latency XGBoost architecture specified.

---

## 1. DATA ACQUISITION & PIPELINE ARCHITECTURE (DATA ENGINEERING)
Before training, you must build a robust data pipeline to fetch and label historical pool data.

* **Target Source:** GeckoTerminal API.
* **Storage:** PostgreSQL (Docker Volume) - You will create a new table `historical_training_data`.
* **Script:** Create a Python script `scripts/fetch_historical_data.py`.
* **Logic:**
    1. Query historical data for 10,000 pools created between 30 and 180 days ago.
    2. **Label Generation (The Ground Truth):** * Label `1` (SAFE): Pool maintained >$10,000 liquidity 30 days after creation AND 24h volume > $0.
        * Label `0` (RUG/DANGER): Pool liquidity dropped by >90% within 72 hours OR trading volume flatlined to exactly 0 (honeypot proxy).

---

## 2. FEATURE ENGINEERING SPECIFICATION
Do not invent features. The model must rely strictly on data available within the first hour of a pool's life to simulate real-time inference. Implement a `FeatureExtractor` class in Python that calculates these exact vectors:

* `liquidity_depth_usd`: Raw reserve in USD at $T+1	ext{hr}$.
* `volume_to_liquidity_ratio`: (1hr Volume) / (1hr Liquidity). Extremely high ratios signal wash trading.
* `pooled_token_ratio`: Ratio of Base Token vs Quote Token in the pool compared to market price (detects imbalanced initial liquidity).
* `contract_age_minutes`: Time delta between token mint and pool initialization.
* `price_volatility_1hr`: Standard deviation of price within the first 60 minutes.

---

## 3. MODEL ARCHITECTURE (XGBOOST CLASSIFIER)
You will implement an XGBoost model. It is chosen for its ultra-low inference latency and high performance on tabular financial data, easily running on resource-constrained hardware.

* **Library:** `xgboost` (Python).
* **Objective Function:** `binary:logistic`.
* **Asymmetric Loss Handling:** Fraud/Rug detection is highly imbalanced. You must configure the `scale_pos_weight` parameter to penalize False Positives (labeling a rug as safe) severely. A False Positive is catastrophic; a False Negative (missing a safe pool) is acceptable.

---

## 4. TRAINING PIPELINE (`scripts/train_model.py`)
Implement the training script with strict MLOps best practices.

1. **Data Splitting:** Time-series split. Do NOT use random K-fold. Train on older pools (e.g., months 1-4), validate on newer pools (month 5), test on newest pools (month 6) to prevent data leakage.
2. **Hyperparameter Tuning:** Implement a lightweight `Optuna` study or `GridSearchCV` optimizing for the **F0.5 Score** (which prioritizes precision over recall).
    * Target bounds: `max_depth` (3 to 7), `learning_rate` (0.01 to 0.1), `n_estimators` (100 to 500).
3. **Training Execution:** Train the model using the engineered features against the binary labels.

---

## 5. TESTING, VALIDATION & OBSERVABILITY
The training script must output a strict evaluation report before saving the model.

* **Mandatory Metrics to Calculate and Log:**
    * **Precision-Recall AUC (PR-AUC):** This is the primary metric. Do not use ROC-AUC.
    * **Precision at Top 5%:** Of the pools the model was *most* confident were safe, how many were actually safe? (Target: >99%).
    * **Confusion Matrix:** Output the raw matrix to the terminal.
* **Testing Scenario:** Run a simulated backtest on the "Month 6" holdout set. The script must simulate streaming inference: passing row-by-row to the model and recording inference latency. Target latency: < 5ms per pool.

---

## 6. ARTIFACT EXPORT & INTEGRATION
Once validation passes, the model must be exported for use in the Rails/Ruby backend environment.

* **Format:** Export the trained XGBoost model strictly to a `.json` format (`xgboost_model.json`). Do not use Pickle (`.pkl`) as it poses security risks and cross-language compatibility issues.
* **Feature Schema:** Generate a `feature_schema.json` file that explicitly lists the order of the features required by the model, ensuring the Rails backend constructs the inference array in the exact correct order.
* **Storage:** Save these artifacts in the `lib/ml_models/` directory of the Rails project, where the Ruby intelligence layer will load it into memory upon boot.
