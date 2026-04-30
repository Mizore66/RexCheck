"""
DexGuard Feature Extractor
==========================
Single source of truth for the 5 features consumed by the XGBoost model.

The order of ``FEATURE_NAMES`` is part of the model contract. The Rails
backend reads ``feature_schema.json`` and constructs its inference vector in
exactly this order — never reorder this list without retraining and
re-exporting the schema artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

import numpy as np

# Canonical feature order. DO NOT reorder without updating feature_schema.json.
FEATURE_NAMES: list[str] = [
    "liquidity_depth_usd",
    "volume_to_liquidity_ratio",
    "pooled_token_ratio",
    "contract_age_minutes",
    "price_volatility_1hr",
]


class FeatureExtractor:
    """
    Build the 5-element feature vector required by the XGBoost classifier
    from any of three input shapes:

    1. A row dict already containing the engineered features
       (e.g. a row from ``historical_training_data``).
    2. A pandas-style dict-of-lists / DataFrame row.
    3. A raw GeckoTerminal pool payload + first-hour OHLCV array, in which
       case the engineered features are computed on the fly.

    The class is intentionally stateless and side-effect free so it can be
    re-used safely from background workers, test harnesses, and the Ruby
    intelligence layer (via JSON dumps) without coordination.
    """

    @staticmethod
    def feature_names() -> list[str]:
        return list(FEATURE_NAMES)

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> np.ndarray:
        """Project a labeled / engineered row into the canonical vector order."""
        return np.asarray(
            [_coerce_float(row.get(name, 0.0)) for name in FEATURE_NAMES],
            dtype=np.float32,
        )

    @classmethod
    def from_rows(cls, rows: Sequence[Mapping[str, object]]) -> np.ndarray:
        if not rows:
            return np.empty((0, len(FEATURE_NAMES)), dtype=np.float32)
        return np.vstack([cls.from_row(r) for r in rows])

    @classmethod
    def from_geckoterminal(
        cls,
        attributes: Mapping[str, object],
        ohlcv_first_hour: Sequence[Sequence[float]] | None = None,
        token_mint_at: datetime | None = None,
    ) -> np.ndarray:
        """
        Compute features directly from a GeckoTerminal pool ``attributes``
        payload plus the optional first-hour OHLCV array
        ``[timestamp, open, high, low, close, volume]`` (oldest first).
        """
        reserve_usd = _coerce_float(attributes.get("reserve_in_usd"))
        vol_1h = _coerce_float(_get_nested(attributes, ("volume_usd", "h1")))

        base_price = _coerce_float(attributes.get("base_token_price_usd"))
        quote_price = _coerce_float(attributes.get("quote_token_price_usd"))
        pooled_token_ratio = (base_price / quote_price) if quote_price > 0 else 1.0

        created_at = _parse_iso(attributes.get("pool_created_at"))
        anchor = token_mint_at or created_at
        if anchor and created_at:
            contract_age_minutes = max(
                0.0, (created_at - anchor).total_seconds() / 60.0
            )
        else:
            contract_age_minutes = 0.0

        if ohlcv_first_hour:
            closes = [
                _coerce_float(row[4])
                for row in ohlcv_first_hour
                if len(row) >= 5 and row[4] is not None
            ]
            if closes and np.mean(closes) > 0:
                volatility = float(np.std(closes) / np.mean(closes))
            else:
                volatility = 0.0
        else:
            volatility = 0.0

        return np.asarray(
            [
                reserve_usd,
                (vol_1h / reserve_usd) if reserve_usd > 0 else 0.0,
                pooled_token_ratio,
                contract_age_minutes,
                volatility,
            ],
            dtype=np.float32,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_nested(payload: Mapping[str, object], path: tuple[str, ...]) -> object:
    cur: object = payload
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)  # type: ignore[union-attr]
    return cur


def _parse_iso(value: object) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
