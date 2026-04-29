"""
rexcheck Ingestion Worker
=========================
Continuously polls the GeckoTerminal API for new pools across configured networks,
applies a Bloom filter to reject duplicates, and pushes raw JSON payloads of new
pools into the Redis queue `rexcheck:raw_pools` for the Rails backend to consume.

Usage:
    python ingestion_worker.py

Environment Variables:
    REDIS_URL           - Redis connection URL (default: redis://localhost:6379/0)
    POLL_INTERVAL       - Seconds between polling cycles (default: 30)
    NETWORKS            - Comma-separated list of networks to monitor
                          (default: eth,solana,base,arbitrum,polygon_pos,bsc,avalanche,optimism)
    GECKO_API_BASE_URL  - GeckoTerminal API base URL
                          (default: https://api.geckoterminal.com/api/v2)
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp
import redis
from dotenv import load_dotenv
import hashlib
from pybloom_live import ScalableBloomFilter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
NETWORKS = os.getenv(
    "NETWORKS",
    "eth,solana,base,arbitrum,polygon_pos,bsc,avalanche,optimism"
).split(",")
GECKO_API_BASE_URL = os.getenv(
    "GECKO_API_BASE_URL",
    "https://api.geckoterminal.com/api/v2"
)
REDIS_QUEUE_KEY = "rexcheck:raw_pools"
MAX_PAGES_PER_NETWORK = 3  # Fetch up to 3 pages per network per cycle

# ---------------------------------------------------------------------------
# Structured JSON Logging (Datadog-compatible)
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for Datadog Log Management."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "rexcheck-worker",
        }
        # Add extra fields if present (pool_address, network_id, etc.)
        for key in ("pool_address", "network_id", "cycle", "duration"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


# Use JSON format when DD_LOGS_INJECTION is set, otherwise human-readable
if os.getenv("DD_LOGS_INJECTION", "").lower() in ("true", "1"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
logger = logging.getLogger("rexcheck.worker")

# ---------------------------------------------------------------------------
# Observability (Datadog Metrics)
# ---------------------------------------------------------------------------

try:
    from observability import (
        emit_duplicate_dropped,
        emit_ingested_pool,
        emit_poll_cycle_duration,
        emit_queue_depth,
    )
except ImportError:
    # Fallback no-ops if observability module isn't available
    def emit_duplicate_dropped(*a, **kw): pass
    def emit_ingested_pool(*a, **kw): pass
    def emit_poll_cycle_duration(*a, **kw): pass
    def emit_queue_depth(*a, **kw): pass

# ---------------------------------------------------------------------------
# Bloom Filter
# ---------------------------------------------------------------------------

bloom = ScalableBloomFilter(
    mode=ScalableBloomFilter.SMALL_SET_GROWTH,
    initial_capacity=100_000,
    error_rate=0.001,
)

# ---------------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------------

shutdown_event = asyncio.Event()


def _signal_handler(sig, frame):
    logger.info(f"Received signal {sig}. Initiating graceful shutdown…")
    shutdown_event.set()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ---------------------------------------------------------------------------
# Redis Connection
# ---------------------------------------------------------------------------


def get_redis_client() -> redis.Redis:
    """Create and return a Redis client."""
    return redis.from_url(REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# GeckoTerminal API Client
# ---------------------------------------------------------------------------


async def fetch_new_pools(
    session: aiohttp.ClientSession,
    network: str,
    page: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch new pools from GeckoTerminal API for a given network.

    Endpoint: GET /api/v2/networks/{network}/new_pools
    """
    url = f"{GECKO_API_BASE_URL}/networks/{network}/new_pools"
    params = {
        "page": page,
        "include": "base_token,quote_token",
    }
    headers = {
        "Accept": "application/json;version=20230302",
        "User-Agent": "rexcheck-worker/1.0",
    }

    try:
        async with session.get(url, params=params, headers=headers, timeout=15) as resp:
            if resp.status == 429:
                # Rate limited — back off
                retry_after = int(resp.headers.get("Retry-After", "60"))
                logger.warning(
                    f"Rate limited on {network} (page {page}). "
                    f"Backing off for {retry_after}s."
                )
                await asyncio.sleep(retry_after)
                return []

            if resp.status != 200:
                logger.error(
                    f"GeckoTerminal API error for {network} page {page}: "
                    f"HTTP {resp.status}"
                )
                return []

            data = await resp.json()
            pools = data.get("data", [])
            logger.info(
                f"Fetched {len(pools)} pools from {network} (page {page})"
            )
            return pools

    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching pools from {network} (page {page})")
        return []
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching pools from {network}: {e}")
        return []


def extract_pool_payload(pool_data: dict, network: str) -> dict:
    """
    Transform raw GeckoTerminal pool data into a normalized payload
    for the Rails ingestion job.
    """
    attrs = pool_data.get("attributes", {})
    relationships = pool_data.get("relationships", {})

    # Extract token addresses from relationships
    base_token_id = (
        relationships.get("base_token", {}).get("data", {}).get("id", "")
    )
    quote_token_id = (
        relationships.get("quote_token", {}).get("data", {}).get("id", "")
    )

    # Token IDs are formatted as "network_tokenAddress"
    base_token_address = base_token_id.split("_", 1)[-1] if "_" in base_token_id else base_token_id
    quote_token_address = quote_token_id.split("_", 1)[-1] if "_" in quote_token_id else quote_token_id

    return {
        "network_id": network,
        "pool_name": attrs.get("name", "Unknown Pool"),
        "pool_address": attrs.get("address", ""),
        "base_token_address": base_token_address,
        "quote_token_address": quote_token_address,
        "volume_usd": attrs.get("volume_usd", {}),
        "reserve_in_usd": str(attrs.get("reserve_in_usd", "0")),
        "pool_created_at": attrs.get("pool_created_at", ""),
        "attributes": attrs,
        "relationships": relationships,
    }


# ---------------------------------------------------------------------------
# Main Poll Cycle
# ---------------------------------------------------------------------------


async def poll_cycle(
    session: aiohttp.ClientSession,
    redis_client: redis.Redis,
) -> int:
    """
    Run a single polling cycle across all configured networks.
    Returns the number of new pools pushed to Redis.
    """
    new_count = 0

    for network in NETWORKS:
        network = network.strip()
        if not network:
            continue

        for page in range(1, MAX_PAGES_PER_NETWORK + 1):
            if shutdown_event.is_set():
                return new_count

            pools = await fetch_new_pools(session, network, page)
            if not pools:
                break  # No more data or error — move to next network

            page_new = 0
            for pool_data in pools:
                pool_address = pool_data.get("attributes", {}).get("address", "")
                if not pool_address:
                    continue

                # Redis-cached hash deduplication (allows updates when data changes)
                attrs = pool_data.get("attributes", {})
                volume = str(attrs.get("volume_usd", {}).get("h24", "0"))
                reserve = str(attrs.get("reserve_in_usd", "0"))
                data_hash = hashlib.md5(f"{volume}:{reserve}".encode()).hexdigest()

                redis_hash_key = f"rexcheck:pool_hash:{network}:{pool_address}"
                cached_hash = redis_client.get(redis_hash_key)

                if cached_hash == data_hash:
                    # Data hasn't changed since last ingestion
                    emit_duplicate_dropped(network=network, pool_address=pool_address)
                    continue

                # Store hash with 10-minute TTL and push to queue
                redis_client.setex(redis_hash_key, 600, data_hash)

                # Build payload and push to Redis queue
                payload = extract_pool_payload(pool_data, network)
                redis_client.rpush(REDIS_QUEUE_KEY, json.dumps(payload))
                emit_ingested_pool(network=network, pool_address=pool_address)
                page_new += 1
                new_count += 1

            logger.info(
                f"[{network}] Page {page}: {page_new} new pools queued "
                f"(filtered {len(pools) - page_new} duplicates)"
            )

            # Small delay between pages to respect rate limits
            await asyncio.sleep(1.5)

        # Small delay between networks
        await asyncio.sleep(0.5)

    return new_count


# ---------------------------------------------------------------------------
# Worker Main Loop
# ---------------------------------------------------------------------------


async def main():
    """Main worker loop."""
    logger.info("=" * 60)
    logger.info("rexcheck Ingestion Worker starting up")
    logger.info(f"  Redis URL:      {REDIS_URL}")
    logger.info(f"  Poll interval:  {POLL_INTERVAL}s")
    logger.info(f"  Networks:       {', '.join(NETWORKS)}")
    logger.info(f"  API Base:       {GECKO_API_BASE_URL}")
    logger.info("=" * 60)

    redis_client = get_redis_client()

    # Verify Redis connectivity
    try:
        redis_client.ping()
        logger.info("✓ Redis connection established")
    except redis.ConnectionError as e:
        logger.critical(f"✗ Cannot connect to Redis: {e}")
        sys.exit(1)

    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)

    async with aiohttp.ClientSession(connector=connector) as session:
        cycle = 0
        while not shutdown_event.is_set():
            cycle += 1
            start = time.monotonic()

            logger.info(f"─── Poll Cycle #{cycle} ───")

            try:
                new_pools = await poll_cycle(session, redis_client)
                elapsed = time.monotonic() - start
                queue_size = redis_client.llen(REDIS_QUEUE_KEY)

                # Emit Datadog metrics
                emit_poll_cycle_duration(elapsed, cycle)
                emit_queue_depth(queue_size)

                logger.info(
                    f"Cycle #{cycle} complete: {new_pools} new pools | "
                    f"Queue depth: {queue_size} | "
                    f"Duration: {elapsed:.2f}s",
                    extra={"cycle": cycle, "duration": elapsed}
                )
            except Exception as e:
                logger.error(f"Error in poll cycle #{cycle}: {e}", exc_info=True)

            # Wait for next cycle or shutdown
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=POLL_INTERVAL,
                )
                break  # Shutdown signaled
            except asyncio.TimeoutError:
                pass  # Normal — timeout means it's time for next cycle

    logger.info("Worker shut down gracefully. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
