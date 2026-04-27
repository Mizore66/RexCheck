"""
rexcheck Python Ingestion Worker — Test Suite
==============================================
Tests 1-3 from the DexGuard Testing & Observability Plan.
Uses pytest, pytest-asyncio, and aioresponses (no live network calls).
"""

import asyncio
import json
import re
import sys
import os

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from aioresponses import aioresponses

# Add worker directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))

import ingestion_worker as worker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_POOL_PAYLOAD = {
    "id": "eth_0xabcdef1234567890abcdef1234567890abcdef12",
    "type": "pool",
    "attributes": {
        "name": "ETH / USDC",
        "address": "0xabcdef1234567890abcdef1234567890abcdef12",
        "base_token_price_usd": "3200.50",
        "volume_usd": {"h24": "15000000.00"},
        "reserve_in_usd": "50000000.00",
        "pool_created_at": "2025-01-01T00:00:00Z",
    },
    "relationships": {
        "base_token": {"data": {"id": "eth_0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "type": "token"}},
        "quote_token": {"data": {"id": "eth_0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "type": "token"}},
    },
}

# Regex pattern to match the GeckoTerminal new_pools endpoint for eth (with any query params)
ETH_NEW_POOLS_PATTERN = re.compile(r"^https://api\.geckoterminal\.com/api/v2/networks/eth/new_pools.*$")


@pytest.fixture
def mock_redis():
    """Create a mock Redis client that tracks rpush calls."""
    redis_mock = MagicMock()
    redis_mock.rpush = MagicMock(return_value=1)
    redis_mock.llen = MagicMock(return_value=0)
    return redis_mock


@pytest.fixture(autouse=True)
def reset_bloom_filter():
    """Reset the Bloom filter before each test."""
    worker.bloom = worker.ScalableBloomFilter(
        mode=worker.ScalableBloomFilter.SMALL_SET_GROWTH,
        initial_capacity=100_000,
        error_rate=0.001,
    )
    yield


@pytest.fixture(autouse=True)
def single_network():
    """Patch NETWORKS to only use 'eth' so mocks are deterministic."""
    with patch.object(worker, "NETWORKS", ["eth"]):
        yield


# ---------------------------------------------------------------------------
# Test 1: Happy Path — High-Volume Pool Ingestion
# ---------------------------------------------------------------------------

class TestHappyPathIngestion:
    """
    Test 1 from the plan: High-Volume Pool Ingestion.
    Mock a GeckoTerminal HTTP payload containing an ETH/USDC pool.
    Assert redis.llen('rexcheck:raw_pools') == 1.
    """

    @pytest.mark.asyncio
    async def test_happy_path_ingestion(self, mock_redis):
        with aioresponses() as mocked:
            # Mock GeckoTerminal API returns 1 pool (page 1)
            mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": [SAMPLE_POOL_PAYLOAD]}, status=200)
            # Mock page 2 returns empty (no more data)
            mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": []}, status=200)
            # Mock page 3 (MAX_PAGES) just in case
            mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": []}, status=200)

            import aiohttp
            async with aiohttp.ClientSession() as session:
                new_count = await worker.poll_cycle(session, mock_redis)

            # Assertions
            assert new_count == 1, f"Expected 1 new pool, got {new_count}"
            mock_redis.rpush.assert_called_once()

            # Validate the pushed payload matches expected JSON schema
            call_args = mock_redis.rpush.call_args
            queue_key = call_args[0][0]
            payload_json = call_args[0][1]
            payload = json.loads(payload_json)

            assert queue_key == "rexcheck:raw_pools"
            assert payload["network_id"] == "eth"
            assert payload["pool_address"] == "0xabcdef1234567890abcdef1234567890abcdef12"
            assert "base_token_address" in payload
            assert "quote_token_address" in payload
            assert "reserve_in_usd" in payload


# ---------------------------------------------------------------------------
# Test 2: Duplicate Rejection — Bloom Filter Scalability
# ---------------------------------------------------------------------------

class TestBloomFilterScalability:
    """
    Test 2 from the plan: Duplicate Rejection.
    Send the exact same pool payload 5 times.
    Assert: first processed (queue=1), subsequent 4 are dropped.
    """

    @pytest.mark.asyncio
    async def test_bloom_filter_scalability(self, mock_redis):
        import aiohttp

        for i in range(5):
            with aioresponses() as mocked:
                mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": [SAMPLE_POOL_PAYLOAD]}, status=200)
                mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": []}, status=200)
                mocked.get(ETH_NEW_POOLS_PATTERN, payload={"data": []}, status=200)

                async with aiohttp.ClientSession() as session:
                    await worker.poll_cycle(session, mock_redis)

        # Only the first call should have pushed to Redis
        assert mock_redis.rpush.call_count == 1, (
            f"Expected rpush called exactly once, but was called {mock_redis.rpush.call_count} times. "
            "Bloom filter should have rejected 4 duplicates."
        )


# ---------------------------------------------------------------------------
# Test 3: Graceful Degradation — Rate Limit Backoff
# ---------------------------------------------------------------------------

class TestRateLimitBackoff:
    """
    Test 3 from the plan: Graceful Degradation.
    Mock an HTTP 429 Too Many Requests response.
    Assert: worker catches exception, does not terminate, 0 pools ingested.
    """

    @pytest.mark.asyncio
    async def test_rate_limit_backoff(self, mock_redis):
        with aioresponses() as mocked:
            mocked.get(
                ETH_NEW_POOLS_PATTERN,
                status=429,
                headers={"Retry-After": "1"},  # Short backoff for testing
            )

            import aiohttp
            async with aiohttp.ClientSession() as session:
                # This should NOT raise — worker handles 429 gracefully
                new_count = await worker.poll_cycle(session, mock_redis)

            # No pools should have been ingested
            assert new_count == 0, f"Expected 0 pools on 429, got {new_count}"
            # Redis rpush should never have been called
            mock_redis.rpush.assert_not_called()
