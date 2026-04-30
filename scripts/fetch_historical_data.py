"""
DexGuard Historical Training Data Acquisition Pipeline
======================================================
Fetches historical pool data from GeckoTerminal and labels each row with the
ground-truth signal required to train the XGBoost rug-detection classifier.

Schema (PostgreSQL `historical_training_data`):
    - id                         BIGSERIAL PRIMARY KEY
    - network_id                 VARCHAR
    - pool_address               VARCHAR UNIQUE
    - pool_created_at            TIMESTAMPTZ
    - observation_at             TIMESTAMPTZ      -- creation + 1 hour
    - liquidity_depth_usd        NUMERIC
    - volume_to_liquidity_ratio  NUMERIC
    - pooled_token_ratio         NUMERIC
    - contract_age_minutes       NUMERIC
    - price_volatility_1hr       NUMERIC
    - label                      SMALLINT         -- 1=SAFE, 0=DANGER
    - label_reason               VARCHAR          -- safe | rug_liq_drop | honeypot
    - label_evaluated_at         TIMESTAMPTZ
    - created_at                 TIMESTAMPTZ DEFAULT NOW()

Modes
-----
- ``--mode synthetic`` (default): generate a realistic, labeled synthetic dataset
  for offline / CI development. Useful when the GeckoTerminal API quota is
  insufficient to backfill 10k pools.
- ``--mode real``: actually call the GeckoTerminal API (slow; rate-limited).

Storage
-------
The script writes to PostgreSQL by default. If a database connection cannot be
established it transparently falls back to a CSV at
``scripts/data/historical_training_data.csv`` so downstream training is never
blocked.

Usage
-----
    python scripts/fetch_historical_data.py --mode synthetic --rows 10000
    python scripts/fetch_historical_data.py --mode real --target 10000
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import psycopg2
    from psycopg2.extras import execute_values
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "scripts" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CSV_FALLBACK_PATH = DATA_DIR / "historical_training_data.csv"

GECKO_API_BASE_URL = os.getenv(
    "GECKO_API_BASE_URL", "https://api.geckoterminal.com/api/v2"
)
NETWORKS = os.getenv(
    "NETWORKS",
    "eth,solana,base,arbitrum,polygon_pos,bsc,avalanche,optimism",
).split(",")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"host={os.getenv('DATABASE_HOST', 'localhost')} "
    f"port={os.getenv('DATABASE_PORT', '5432')} "
    f"dbname={os.getenv('DATABASE_NAME', 'rexcheck_development')} "
    f"user={os.getenv('DATABASE_USERNAME', 'postgres')} "
    f"password={os.getenv('DATABASE_PASSWORD', 'postgres')}"
)

# Rule-based labelling thresholds (per spec § 1.2)
SAFE_LIQUIDITY_FLOOR_USD = 10_000
RUG_LIQUIDITY_DROP_PCT = 0.90
RUG_OBSERVATION_HOURS = 72
SAFE_OBSERVATION_DAYS = 30

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
logger = logging.getLogger("dexguard.fetch")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
DDL_HISTORICAL = """
CREATE TABLE IF NOT EXISTS historical_training_data (
    id                         BIGSERIAL PRIMARY KEY,
    network_id                 VARCHAR(32)  NOT NULL,
    pool_address               VARCHAR(96)  NOT NULL,
    pool_created_at            TIMESTAMPTZ  NOT NULL,
    observation_at             TIMESTAMPTZ  NOT NULL,
    liquidity_depth_usd        NUMERIC(24,4),
    volume_to_liquidity_ratio  NUMERIC(24,8),
    pooled_token_ratio         NUMERIC(24,8),
    contract_age_minutes       NUMERIC(18,4),
    price_volatility_1hr       NUMERIC(24,8),
    label                      SMALLINT     NOT NULL CHECK (label IN (0,1)),
    label_reason               VARCHAR(64)  NOT NULL,
    label_evaluated_at         TIMESTAMPTZ  NOT NULL,
    created_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT historical_training_data_unique
        UNIQUE (network_id, pool_address)
);
CREATE INDEX IF NOT EXISTS idx_historical_pool_created_at
    ON historical_training_data (pool_created_at);
CREATE INDEX IF NOT EXISTS idx_historical_label
    ON historical_training_data (label);
"""

INSERT_SQL = """
INSERT INTO historical_training_data
    (network_id, pool_address, pool_created_at, observation_at,
     liquidity_depth_usd, volume_to_liquidity_ratio, pooled_token_ratio,
     contract_age_minutes, price_volatility_1hr,
     label, label_reason, label_evaluated_at)
VALUES %s
ON CONFLICT (network_id, pool_address) DO UPDATE SET
    liquidity_depth_usd       = EXCLUDED.liquidity_depth_usd,
    volume_to_liquidity_ratio = EXCLUDED.volume_to_liquidity_ratio,
    pooled_token_ratio        = EXCLUDED.pooled_token_ratio,
    contract_age_minutes      = EXCLUDED.contract_age_minutes,
    price_volatility_1hr      = EXCLUDED.price_volatility_1hr,
    label                     = EXCLUDED.label,
    label_reason              = EXCLUDED.label_reason,
    label_evaluated_at        = EXCLUDED.label_evaluated_at;
"""

CSV_COLUMNS = [
    "network_id",
    "pool_address",
    "pool_created_at",
    "observation_at",
    "liquidity_depth_usd",
    "volume_to_liquidity_ratio",
    "pooled_token_ratio",
    "contract_age_minutes",
    "price_volatility_1hr",
    "label",
    "label_reason",
    "label_evaluated_at",
]


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------
@dataclass
class TrainingRow:
    network_id: str
    pool_address: str
    pool_created_at: datetime
    observation_at: datetime
    liquidity_depth_usd: float
    volume_to_liquidity_ratio: float
    pooled_token_ratio: float
    contract_age_minutes: float
    price_volatility_1hr: float
    label: int
    label_reason: str
    label_evaluated_at: datetime

    def as_tuple(self) -> tuple:
        return (
            self.network_id,
            self.pool_address,
            self.pool_created_at,
            self.observation_at,
            self.liquidity_depth_usd,
            self.volume_to_liquidity_ratio,
            self.pooled_token_ratio,
            self.contract_age_minutes,
            self.price_volatility_1hr,
            self.label,
            self.label_reason,
            self.label_evaluated_at,
        )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def _connect_postgres():
    """Try to connect to Postgres. Returns the connection or None on failure."""
    if not HAS_PSYCOPG:
        logger.warning("psycopg2 not installed - falling back to CSV.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        return conn
    except Exception as exc:
        logger.warning(f"Postgres unreachable ({exc}) - falling back to CSV.")
        return None


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL_HISTORICAL)
    conn.commit()


def write_to_postgres(rows: list[TrainingRow]) -> int:
    conn = _connect_postgres()
    if conn is None:
        return 0
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            execute_values(
                cur,
                INSERT_SQL,
                [r.as_tuple() for r in rows],
                page_size=500,
            )
        conn.commit()
        logger.info(f"Persisted {len(rows)} rows into PostgreSQL.")
        return len(rows)
    finally:
        conn.close()


def write_to_csv(rows: list[TrainingRow], path: Path = CSV_FALLBACK_PATH) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            d["pool_created_at"] = d["pool_created_at"].isoformat()
            d["observation_at"] = d["observation_at"].isoformat()
            d["label_evaluated_at"] = d["label_evaluated_at"].isoformat()
            writer.writerow(d)
    logger.info(f"Persisted {len(rows)} rows into {path}.")
    return len(rows)


def persist(rows: list[TrainingRow]) -> str:
    """Persist to Postgres, falling back to CSV. Returns the storage backend used."""
    pg_count = write_to_postgres(rows)
    write_to_csv(rows)
    return "postgres+csv" if pg_count else "csv"


# ---------------------------------------------------------------------------
# Synthetic generator
# ---------------------------------------------------------------------------
def _truncated_lognormal(mean: float, sigma: float, lo: float, hi: float, rng) -> float:
    """Sample from a log-normal distribution clipped to [lo, hi]."""
    for _ in range(20):
        v = float(rng.lognormal(mean=mean, sigma=sigma))
        if lo <= v <= hi:
            return v
    return float(np.clip(v, lo, hi))


def generate_synthetic_dataset(
    n_rows: int,
    rug_ratio: float = 0.55,
    seed: int = 42,
) -> list[TrainingRow]:
    """
    Build a realistic, learnable synthetic dataset.

    Distribution choices come from observed DEX rug-pull patterns:
    - SAFE pools: deeper liquidity, balanced token ratios, healthy vol/liq.
    - RUG pools: shallow liquidity, extreme vol/liq spikes (wash trading)
      OR exactly-zero volume (honeypot proxy), imbalanced reserves.

    Pool ``created_at`` timestamps are spread uniformly across the
    spec-mandated window (30 to 180 days ago) so that downstream
    time-series splitting has months of data to work with.
    """
    rng = np.random.default_rng(seed)

    n_rug = int(n_rows * rug_ratio)
    n_safe = n_rows - n_rug
    now = datetime.now(timezone.utc)

    rows: list[TrainingRow] = []
    networks = [n.strip() for n in NETWORKS if n.strip()]

    def random_creation() -> datetime:
        days_ago = rng.uniform(30, 180)
        return now - timedelta(days=float(days_ago))

    for i in range(n_safe):
        created = random_creation()
        observed = created + timedelta(hours=1)
        liquidity = _truncated_lognormal(11.0, 0.7, SAFE_LIQUIDITY_FLOOR_USD, 5_000_000, rng)
        vol_liq_ratio = float(rng.uniform(0.05, 2.5))
        token_ratio = float(np.clip(rng.normal(1.0, 0.05), 0.7, 1.4))
        contract_age = float(rng.uniform(60, 60 * 24 * 14))
        volatility = float(rng.uniform(0.005, 0.04))
        rows.append(
            TrainingRow(
                network_id=str(rng.choice(networks)),
                pool_address=f"0xsafe{i:08x}{int(rng.integers(0, 2**32)):08x}",
                pool_created_at=created,
                observation_at=observed,
                liquidity_depth_usd=round(liquidity, 4),
                volume_to_liquidity_ratio=round(vol_liq_ratio, 8),
                pooled_token_ratio=round(token_ratio, 8),
                contract_age_minutes=round(contract_age, 4),
                price_volatility_1hr=round(volatility, 8),
                label=1,
                label_reason="safe_above_threshold_30d",
                label_evaluated_at=observed + timedelta(days=SAFE_OBSERVATION_DAYS),
            )
        )

    for i in range(n_rug):
        created = random_creation()
        observed = created + timedelta(hours=1)

        rug_kind = rng.choice(["liq_drop", "honeypot", "wash_trade"], p=[0.55, 0.25, 0.20])
        if rug_kind == "liq_drop":
            liquidity = _truncated_lognormal(8.0, 1.0, 200, 50_000, rng)
            vol_liq_ratio = float(rng.uniform(0.001, 5.0))
            token_ratio = float(np.clip(rng.normal(1.0, 0.25), 0.2, 3.0))
            volatility = float(rng.uniform(0.05, 0.6))
            label_reason = "rug_liq_drop_72h"
        elif rug_kind == "honeypot":
            liquidity = _truncated_lognormal(9.0, 0.6, 1_000, 200_000, rng)
            vol_liq_ratio = 0.0
            token_ratio = float(np.clip(rng.normal(1.0, 0.4), 0.05, 5.0))
            volatility = 0.0
            label_reason = "honeypot_zero_volume"
        else:
            liquidity = _truncated_lognormal(9.5, 0.8, 500, 500_000, rng)
            vol_liq_ratio = float(rng.uniform(15, 250))
            token_ratio = float(np.clip(rng.normal(1.0, 0.15), 0.4, 1.8))
            volatility = float(rng.uniform(0.02, 0.4))
            label_reason = "wash_trading_proxy"

        contract_age = float(rng.uniform(0, 240))
        rows.append(
            TrainingRow(
                network_id=str(rng.choice(networks)),
                pool_address=f"0xrug{i:08x}{int(rng.integers(0, 2**32)):08x}",
                pool_created_at=created,
                observation_at=observed,
                liquidity_depth_usd=round(liquidity, 4),
                volume_to_liquidity_ratio=round(vol_liq_ratio, 8),
                pooled_token_ratio=round(token_ratio, 8),
                contract_age_minutes=round(contract_age, 4),
                price_volatility_1hr=round(volatility, 8),
                label=0,
                label_reason=label_reason,
                label_evaluated_at=observed + timedelta(hours=RUG_OBSERVATION_HOURS),
            )
        )

    rng.shuffle(rows)
    logger.info(
        f"Generated synthetic dataset: {n_safe} SAFE / {n_rug} DANGER "
        f"(rug ratio = {rug_ratio:.2f})"
    )
    return rows


# ---------------------------------------------------------------------------
# Real GeckoTerminal acquisition (best-effort, rate-limited)
# ---------------------------------------------------------------------------
async def _gecko_get(session, url: str, params: dict | None = None) -> dict | None:
    headers = {
        "Accept": "application/json;version=20230302",
        "User-Agent": "dexguard-fetch/1.0",
    }
    for attempt in range(3):
        try:
            async with session.get(url, params=params, headers=headers, timeout=20) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "30"))
                    logger.warning(f"Rate limited; sleeping {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} for {url}")
                    return None
                return await resp.json()
        except Exception as exc:
            logger.warning(f"GET {url} failed (attempt {attempt + 1}): {exc}")
            await asyncio.sleep(2 * (attempt + 1))
    return None


async def _fetch_first_hour_ohlcv(session, network: str, pool_address: str,
                                   start_ts: datetime) -> list[list[float]]:
    """Fetch minute-resolution OHLCV for the first 60 minutes of a pool's life."""
    url = f"{GECKO_API_BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/minute"
    params = {
        "aggregate": 1,
        "before_timestamp": int((start_ts + timedelta(minutes=61)).timestamp()),
        "limit": 60,
    }
    data = await _gecko_get(session, url, params=params)
    if not data:
        return []
    return data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])


def _label_from_attrs(attrs: dict, created_at: datetime) -> tuple[int, str]:
    """
    Apply the spec's labelling rules to a pool's *current* attributes.

    Live API exposes "current" reserves and 24h volume only. We approximate:
    - SAFE if reserve_in_usd >= floor and 24h volume > 0 AND age >= SAFE window.
    - DANGER (rug) if reserve_in_usd << historical reserve at creation
      (we treat tiny current liquidity for an aged pool as a rug proxy).
    - DANGER (honeypot) if 24h volume == 0 for an aged pool.
    """
    age_days = (datetime.now(timezone.utc) - created_at).days
    reserve_now = float(attrs.get("reserve_in_usd") or 0)
    vol_24 = float((attrs.get("volume_usd") or {}).get("h24") or 0)

    if vol_24 == 0 and age_days >= 3:
        return 0, "honeypot_zero_volume"
    if reserve_now < SAFE_LIQUIDITY_FLOOR_USD * (1 - RUG_LIQUIDITY_DROP_PCT) and age_days >= 3:
        return 0, "rug_liq_drop_72h"
    if reserve_now >= SAFE_LIQUIDITY_FLOOR_USD and vol_24 > 0 and age_days >= SAFE_OBSERVATION_DAYS:
        return 1, "safe_above_threshold_30d"
    return -1, "unresolved"


def _features_from_attrs_and_ohlcv(attrs: dict, ohlcv: list[list[float]]) -> dict[str, float]:
    """Derive the 5 spec-mandated features from raw API payloads."""
    reserve_usd = float(attrs.get("reserve_in_usd") or 0)
    vol_1h = float((attrs.get("volume_usd") or {}).get("h1") or 0)
    base_reserve = float(attrs.get("base_token_price_usd") or 0)
    quote_reserve = float(attrs.get("quote_token_price_usd") or 0)
    pool_ratio = (base_reserve / quote_reserve) if quote_reserve > 0 else 1.0

    if ohlcv:
        closes = [float(row[4]) for row in ohlcv if len(row) >= 5 and row[4]]
        volatility = float(np.std(closes) / np.mean(closes)) if closes and np.mean(closes) > 0 else 0.0
    else:
        volatility = 0.0

    return {
        "liquidity_depth_usd": reserve_usd,
        "volume_to_liquidity_ratio": (vol_1h / reserve_usd) if reserve_usd > 0 else 0.0,
        "pooled_token_ratio": pool_ratio,
        "price_volatility_1hr": volatility,
    }


async def fetch_real_dataset(target: int) -> list[TrainingRow]:
    if not HAS_AIOHTTP:
        raise RuntimeError("aiohttp is required for --mode real")

    rows: list[TrainingRow] = []
    now = datetime.now(timezone.utc)
    cutoff_old = now - timedelta(days=180)
    cutoff_new = now - timedelta(days=30)

    async with aiohttp.ClientSession() as session:
        for network in NETWORKS:
            network = network.strip()
            if not network or len(rows) >= target:
                break
            for page in range(1, 11):
                if len(rows) >= target:
                    break
                data = await _gecko_get(
                    session,
                    f"{GECKO_API_BASE_URL}/networks/{network}/pools",
                    params={"page": page},
                )
                if not data:
                    break
                pools = data.get("data", [])
                if not pools:
                    break

                for pool_data in pools:
                    if len(rows) >= target:
                        break
                    attrs = pool_data.get("attributes", {})
                    created_iso = attrs.get("pool_created_at")
                    if not created_iso:
                        continue
                    try:
                        created_at = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if not (cutoff_old <= created_at <= cutoff_new):
                        continue

                    label, reason = _label_from_attrs(attrs, created_at)
                    if label == -1:
                        continue

                    pool_address = attrs.get("address", "")
                    ohlcv = await _fetch_first_hour_ohlcv(session, network, pool_address, created_at)
                    feats = _features_from_attrs_and_ohlcv(attrs, ohlcv)
                    observed = created_at + timedelta(hours=1)

                    rows.append(
                        TrainingRow(
                            network_id=network,
                            pool_address=pool_address,
                            pool_created_at=created_at,
                            observation_at=observed,
                            liquidity_depth_usd=feats["liquidity_depth_usd"],
                            volume_to_liquidity_ratio=feats["volume_to_liquidity_ratio"],
                            pooled_token_ratio=feats["pooled_token_ratio"],
                            contract_age_minutes=(observed - created_at).total_seconds() / 60.0,
                            price_volatility_1hr=feats["price_volatility_1hr"],
                            label=label,
                            label_reason=reason,
                            label_evaluated_at=now,
                        )
                    )
                    await asyncio.sleep(1.2)
                logger.info(f"[{network}] page {page}: collected so far {len(rows)}")
                await asyncio.sleep(1.5)
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["synthetic", "real"],
        default="synthetic",
        help="Synthetic (default) for offline use; real to call GeckoTerminal API.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10_000,
        help="Number of rows to produce in synthetic mode (default 10000).",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=10_000,
        help="Maximum pools to collect in real mode (default 10000).",
    )
    parser.add_argument(
        "--rug-ratio",
        type=float,
        default=0.55,
        help="Fraction of synthetic rows labelled DANGER (default 0.55).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default 42).",
    )
    args = parser.parse_args(argv)

    logger.info("=" * 70)
    logger.info("DexGuard historical training data acquisition")
    logger.info(f"  Mode:       {args.mode}")
    logger.info(f"  Target:     {args.rows if args.mode == 'synthetic' else args.target}")
    logger.info(f"  Networks:   {', '.join(NETWORKS)}")
    logger.info("=" * 70)

    if args.mode == "synthetic":
        rows = generate_synthetic_dataset(
            n_rows=args.rows, rug_ratio=args.rug_ratio, seed=args.seed
        )
    else:
        rows = asyncio.run(fetch_real_dataset(target=args.target))
        if not rows:
            logger.error("No rows collected via GeckoTerminal - aborting.")
            return 2

    backend = persist(rows)
    n_safe = sum(1 for r in rows if r.label == 1)
    n_danger = sum(1 for r in rows if r.label == 0)
    logger.info(f"Done. Backend: {backend}. Total: {len(rows)}  SAFE: {n_safe}  DANGER: {n_danger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
