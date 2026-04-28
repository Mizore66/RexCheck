"""
Datadog Observability Module for RexCheck Python Worker
=======================================================
Provides Datadog APM tracing and custom StatsD metrics
for the ingestion worker pipeline.

Usage:
    Set DD_AGENT_HOST and DD_ENV environment variables, then
    run with: ddtrace-run python ingestion_worker.py

Custom Metrics:
    - dexguard.worker.duplicate_dropped  (counter)
    - dexguard.worker.ingested_pools     (counter)
    - dexguard.worker.poll_cycle_duration (histogram)
    - dexguard.worker.queue_depth        (gauge)
"""

import os
import logging

logger = logging.getLogger("rexcheck.worker.observability")

# ---------------------------------------------------------------------------
# Datadog StatsD Client (lazy init)
# ---------------------------------------------------------------------------

_statsd_client = None


def _get_statsd():
    """Lazily initialize the DogStatsD client."""
    global _statsd_client
    if _statsd_client is not None:
        return _statsd_client

    try:
        from datadog import DogStatsd
        _statsd_client = DogStatsd(
            host=os.getenv("DD_AGENT_HOST", "localhost"),
            port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
            namespace="dexguard",
            constant_tags=[
                f"env:{os.getenv('DD_ENV', 'development')}",
                f"service:{os.getenv('DD_SERVICE', 'rexcheck-worker')}",
            ],
        )
        logger.info("Datadog StatsD client initialized")
    except ImportError:
        logger.warning(
            "datadog package not installed — metrics will be no-ops. "
            "Install with: pip install datadog ddtrace"
        )
        _statsd_client = _NoOpStatsd()

    return _statsd_client


class _NoOpStatsd:
    """No-op fallback when datadog is not installed."""

    def increment(self, *args, **kwargs):
        pass

    def gauge(self, *args, **kwargs):
        pass

    def histogram(self, *args, **kwargs):
        pass

    def distribution(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Metric Emission Helpers
# ---------------------------------------------------------------------------


def emit_duplicate_dropped(network: str, pool_address: str):
    """Emit counter when Bloom filter rejects a duplicate payload."""
    _get_statsd().increment(
        "worker.duplicate_dropped",
        tags=[f"network:{network}", f"pool_address:{pool_address}"],
    )


def emit_ingested_pool(network: str, pool_address: str):
    """Emit counter when a new pool is successfully pushed to Redis."""
    _get_statsd().increment(
        "worker.ingested_pools",
        tags=[f"network:{network}"],
    )


def emit_poll_cycle_duration(duration_seconds: float, cycle: int):
    """Emit histogram for poll cycle duration."""
    _get_statsd().histogram(
        "worker.poll_cycle_duration",
        duration_seconds,
        tags=[f"cycle:{cycle}"],
    )


def emit_queue_depth(depth: int):
    """Emit gauge for current Redis queue depth."""
    _get_statsd().gauge("worker.queue_depth", depth)
