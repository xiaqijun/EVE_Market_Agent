"""Tests for ESI rate limiter module."""

import time
import pytest
from app.tools.rate_limiter import TokenBucket, CacheEntry, RequestStats, EsiRateManager


class TestTokenBucket:
    def test_usage_ratio(self):
        bucket = TokenBucket(group="test", limit=100, remaining=50)
        assert bucket.usage_ratio == 0.5

    def test_usage_ratio_empty(self):
        bucket = TokenBucket(group="test", limit=100, remaining=0)
        assert bucket.usage_ratio == 0.0

    def test_usage_ratio_full(self):
        bucket = TokenBucket(group="test", limit=100, remaining=100)
        assert bucket.usage_ratio == 1.0

    def test_usage_ratio_no_limit(self):
        bucket = TokenBucket(group="test", limit=0, remaining=0)
        assert bucket.usage_ratio == 0.0

    def test_replenish_wait_no_wait(self):
        bucket = TokenBucket(group="test", limit=100, remaining=50, window=900)
        assert bucket.replenish_wait(0.1) == 0.0  # 50% > 10%

    def test_replenish_wait_needed(self):
        bucket = TokenBucket(
            group="test",
            limit=12000,
            remaining=100,
            window=900,
            updated_at=time.monotonic(),
        )
        wait = bucket.replenish_wait(0.10)  # Need 1200, have 100
        assert wait > 0
        assert wait < 900  # Should be less than full window


class TestCacheEntry:
    def test_is_fresh_when_not_expired(self):
        entry = CacheEntry(expires_at=time.time() + 300)
        assert entry.is_fresh is True

    def test_is_stale_when_expired(self):
        entry = CacheEntry(expires_at=time.time() - 1)
        assert entry.is_fresh is False

    def test_is_stale_when_no_expiry(self):
        entry = CacheEntry()
        assert entry.is_fresh is False


class TestRequestStats:
    def test_record_request(self):
        stats = RequestStats()
        stats.record_request("market-order")
        assert stats.total_requests == 1
        assert stats.requests_by_group["market-order"] == 1

    def test_record_wait(self):
        stats = RequestStats()
        stats.record_wait(5.0)
        assert stats.total_wait_seconds == 5.0

    def test_record_429(self):
        stats = RequestStats()
        stats.record_429()
        assert stats.total_429_hits == 1


class TestEsiRateManager:
    def test_update_from_response(self):
        manager = EsiRateManager()
        manager.update_from_response(
            {
                "x-ratelimit-group": "market-order",
                "x-ratelimit-limit": "12000/15m",
                "x-ratelimit-remaining": "10000",
                "x-ratelimit-used": "2",
            }
        )
        assert "market-order" in manager._buckets
        bucket = manager._buckets["market-order"]
        assert bucket.remaining == 10000
        assert bucket.limit == 12000
        assert bucket.window == 900

    def test_update_from_response_clears_penalty(self):
        manager = EsiRateManager()
        manager._buckets["market-order"] = TokenBucket(
            group="market-order", penalty_count=3, penalty_until=time.monotonic() + 100
        )
        manager.update_from_response(
            {
                "x-ratelimit-group": "market-order",
                "x-ratelimit-limit": "12000/15m",
                "x-ratelimit-remaining": "10000",
            }
        )
        bucket = manager._buckets["market-order"]
        assert bucket.penalty_count == 0
        assert bucket.penalty_until == 0.0

    def test_record_429_sets_penalty(self):
        manager = EsiRateManager()
        manager.record_429(10, "market-order")
        bucket = manager._buckets["market-order"]
        assert bucket.penalty_count == 1
        assert bucket.penalty_until > time.monotonic()

    def test_record_429_exponential_backoff(self):
        manager = EsiRateManager()
        manager.record_429(10, "market-order")
        assert manager._buckets["market-order"].penalty_count == 1

        # Simulate penalty expiring
        manager._buckets["market-order"].penalty_until = time.monotonic() - 1

        manager.record_429(10, "market-order")
        assert manager._buckets["market-order"].penalty_count == 2

    def test_record_429_capped_at_max(self):
        manager = EsiRateManager()
        for _ in range(10):
            manager._buckets["market-order"] = TokenBucket(group="market-order")
            manager.record_429(10, "market-order")
        bucket = manager._buckets["market-order"]
        # Penalty should be capped at max_penalty_wait
        remaining = bucket.penalty_until - time.monotonic()
        assert remaining <= manager.max_penalty_wait + 1

    def test_cache_lifecycle(self):
        manager = EsiRateManager()
        path = "/markets/10000002/orders/"
        params_key = "page=1&type=all"

        # No cache initially
        assert manager.is_cache_fresh(path, params_key) is False
        assert manager.get_etag(path, params_key) is None

        # Update cache
        manager.update_cache(
            path,
            params_key,
            {
                "etag": '"abc123"',
                "expires": "Mon, 02 Jun 2026 12:00:00 GMT",
            },
        )
        assert manager.get_etag(path, params_key) == '"abc123"'

    def test_stats(self):
        manager = EsiRateManager()
        manager.update_from_response(
            {
                "x-ratelimit-group": "market-order",
                "x-ratelimit-limit": "12000/15m",
                "x-ratelimit-remaining": "10000",
            }
        )
        stats = manager.stats
        assert stats["total_requests"] == 1
        assert "market-order" in stats["buckets"]
        assert stats["buckets"]["market-order"]["remaining"] == 10000

    @pytest.mark.asyncio
    async def test_acquire_no_wait_when_healthy(self):
        manager = EsiRateManager()
        manager._buckets["test"] = TokenBucket(group="test", limit=100, remaining=90, window=900)
        # Should not wait
        await manager.acquire("test")

    @pytest.mark.asyncio
    async def test_acquire_waits_for_penalty(self):
        manager = EsiRateManager()
        manager._buckets["test"] = TokenBucket(
            group="test",
            limit=100,
            remaining=90,
            window=900,
            penalty_until=time.monotonic() + 0.1,
            penalty_count=1,
        )
        start = time.monotonic()
        await manager.acquire("test")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # Should have waited ~0.1s

    def test_parse_limit(self):
        assert EsiRateManager._parse_limit("12000/15m") == (12000, 900)
        assert EsiRateManager._parse_limit("100/1h") == (100, 3600)
        assert EsiRateManager._parse_limit("") == (0, 0)
        assert EsiRateManager._parse_limit("invalid") == (0, 0)
