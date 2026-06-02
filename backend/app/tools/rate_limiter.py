"""ESI rate limit and cache management.

Implements ESI's floating-window token bucket model with:
- Proactive throttling at 10% remaining (avoid 429)
- Cache TTL enforcement (respect ESI's Expires header)
- 429 penalty tracking with exponential backoff
- Per-group bucket state
- Request statistics
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from app.config import settings


@dataclass
class TokenBucket:
    """Rate limit state for a single route group."""

    group: str
    limit: int = 0  # Total tokens per window (e.g. 12000)
    remaining: int = 0  # Tokens remaining
    window: int = 0  # Window size in seconds (e.g. 900)
    used: int = 0  # Tokens used by last request
    updated_at: float = field(default_factory=time.monotonic)
    penalty_until: float = 0.0  # monotonic time when penalty expires
    penalty_count: int = 0  # consecutive 429 hits

    @property
    def usage_ratio(self) -> float:
        """How much of the bucket has been consumed (0.0 = empty, 1.0 = full)."""
        if self.limit <= 0:
            return 0.0
        return self.remaining / self.limit

    def replenish_wait(self, threshold: float) -> float:
        """Calculate seconds to wait until remaining exceeds threshold."""
        if self.limit <= 0 or self.window <= 0:
            return 0.0
        target = int(self.limit * threshold)
        if self.remaining >= target:
            return 0.0
        tokens_per_sec = self.limit / self.window
        elapsed = time.monotonic() - self.updated_at
        needed = target - self.remaining
        return max(0.0, needed / tokens_per_sec - elapsed)


@dataclass
class CacheEntry:
    """Cache state for a single ESI endpoint."""

    etag: str | None = None
    expires_at: float = 0.0  # Unix timestamp — do not request before this
    last_modified: str | None = None

    @property
    def is_fresh(self) -> bool:
        """True if the cache has not expired yet."""
        return time.time() < self.expires_at


@dataclass
class RequestStats:
    """Aggregate request statistics."""

    total_requests: int = 0
    total_wait_seconds: float = 0.0
    total_429_hits: int = 0
    total_304_hits: int = 0
    total_errors: int = 0
    requests_by_group: dict[str, int] = field(default_factory=dict)

    def record_request(self, group: str):
        self.total_requests += 1
        self.requests_by_group[group] = self.requests_by_group.get(group, 0) + 1

    def record_wait(self, seconds: float):
        self.total_wait_seconds += seconds

    def record_429(self):
        self.total_429_hits += 1

    def record_304(self):
        self.total_304_hits += 1

    def record_error(self):
        self.total_errors += 1


class EsiRateManager:
    """Global rate limit and cache manager for ESI requests.

    Usage:
        manager = EsiRateManager()
        await manager.acquire("market-order")   # wait if needed
        # ... make request ...
        manager.update_from_response(headers)   # update state
    """

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._cache: dict[str, CacheEntry] = {}
        self._error_limit: int = 100
        self._error_reset_at: float = 0.0
        self._stats = RequestStats()

        # Config
        self.throttle_threshold = settings.esi_throttle_threshold
        self.penalty_multiplier = settings.esi_penalty_multiplier
        self.max_penalty_wait = settings.esi_max_penalty_wait

    async def acquire(self, group: str = "default") -> None:
        """Acquire permission to make a request. Waits if necessary."""
        bucket = self._buckets.get(group)

        # 1. Penalty wait (from previous 429)
        if bucket and bucket.penalty_until > time.monotonic():
            wait = bucket.penalty_until - time.monotonic()
            print(
                f"[RateLimiter] {group}: penalty wait {wait:.1f}s (429 count: {bucket.penalty_count})"
            )
            await asyncio.sleep(wait)
            self._stats.record_wait(wait)

        # 2. Error limit check (legacy)
        if self._error_limit <= 2:
            wait = max(0.0, self._error_reset_at - time.time())
            if wait > 0:
                print(f"[RateLimiter] error limit low ({self._error_limit}), waiting {wait:.1f}s")
                await asyncio.sleep(wait)
                self._stats.record_wait(wait)

        # 3. Proactive throttle — wait until remaining exceeds threshold
        if bucket:
            wait = bucket.replenish_wait(self.throttle_threshold)
            if wait > 0:
                print(
                    f"[RateLimiter] {group}: throttle wait {wait:.1f}s (remaining {bucket.remaining}/{bucket.limit})"
                )
                await asyncio.sleep(wait)
                self._stats.record_wait(wait)

    def update_from_response(self, headers: dict) -> None:
        """Update rate limit state from ESI response headers."""
        group = headers.get("x-ratelimit-group")
        if group:
            limit_str = headers.get("x-ratelimit-limit", "")
            remaining = headers.get("x-ratelimit-remaining")
            used = headers.get("x-ratelimit-used")

            if remaining is not None:
                max_tokens, window = self._parse_limit(limit_str) if limit_str else (0, 0)
                bucket = self._buckets.setdefault(group, TokenBucket(group=group))
                bucket.remaining = int(remaining)
                bucket.limit = max_tokens
                bucket.window = window
                bucket.used = int(used) if used else 0
                bucket.updated_at = time.monotonic()
                # Clear penalty on successful response
                if bucket.penalty_count > 0:
                    bucket.penalty_count = 0
                    bucket.penalty_until = 0.0

                self._stats.record_request(group)

        # Legacy error limit
        error_remain = headers.get("x-esi-error-limit-remain")
        error_reset = headers.get("x-esi-error-limit-reset")
        if error_remain is not None:
            self._error_limit = int(error_remain)
        if error_reset is not None:
            self._error_reset_at = time.time() + int(error_reset)

        # Persist to Redis for cross-process access
        self.save_to_redis()

    def update_cache(self, path: str, params_key: str, headers: dict) -> None:
        """Update cache state from ESI response headers."""
        cache_key = f"{path}?{params_key}"
        entry = self._cache.setdefault(cache_key, CacheEntry())

        # ETag
        etag = headers.get("etag")
        if etag:
            entry.etag = etag

        # Expires — ESI requires no requests before this
        expires = headers.get("expires")
        if expires:
            try:
                from email.utils import parsedate_to_datetime

                entry.expires_at = parsedate_to_datetime(expires).timestamp()
            except Exception:
                pass

        # Last-Modified
        last_mod = headers.get("last-modified")
        if last_mod:
            entry.last_modified = last_mod

    def record_429(self, retry_after: int, group: str = "default") -> None:
        """Record a 429 penalty. Increases wait on consecutive hits."""
        bucket = self._buckets.setdefault(group, TokenBucket(group=group))
        bucket.penalty_count += 1

        # Exponential backoff: base * multiplier^(count-1), capped
        base_wait = retry_after
        penalty_wait = min(
            base_wait * (self.penalty_multiplier ** (bucket.penalty_count - 1)),
            self.max_penalty_wait,
        )
        bucket.penalty_until = time.monotonic() + penalty_wait

        self._stats.record_429()
        print(
            f"[RateLimiter] 429 on {group}! penalty {penalty_wait:.0f}s "
            f"(count: {bucket.penalty_count}, base: {retry_after}s)"
        )

    def is_cache_fresh(self, path: str, params_key: str) -> bool:
        """Check if the cached response is still fresh (ESI's Expires)."""
        cache_key = f"{path}?{params_key}"
        entry = self._cache.get(cache_key)
        return entry is not None and entry.is_fresh

    def get_etag(self, path: str, params_key: str) -> str | None:
        """Get cached ETag for conditional requests."""
        cache_key = f"{path}?{params_key}"
        entry = self._cache.get(cache_key)
        return entry.etag if entry else None

    def record_304(self) -> None:
        """Record a 304 Not Modified response."""
        self._stats.record_304()

    def record_error(self) -> None:
        """Record a non-2xx/3xx error."""
        self._stats.record_error()

    @property
    def stats(self) -> dict:
        """Return current statistics."""
        return {
            "total_requests": self._stats.total_requests,
            "total_wait_seconds": round(self._stats.total_wait_seconds, 1),
            "total_429_hits": self._stats.total_429_hits,
            "total_304_hits": self._stats.total_304_hits,
            "total_errors": self._stats.total_errors,
            "requests_by_group": dict(self._stats.requests_by_group),
            "buckets": {
                name: {
                    "remaining": b.remaining,
                    "limit": b.limit,
                    "usage_pct": round((1 - b.usage_ratio) * 100, 1),
                    "penalty_count": b.penalty_count,
                }
                for name, b in self._buckets.items()
            },
            "cache_entries": len(self._cache),
        }

    @property
    def status(self) -> dict:
        """Alias for stats, backward compatible."""
        return self.stats

    def save_to_redis(self) -> None:
        """Persist current stats to Redis for cross-process access."""
        try:
            import redis
            r = redis.from_url(settings.redis_url)
            data = {
                "total_requests": self._stats.total_requests,
                "total_wait_seconds": round(self._stats.total_wait_seconds, 1),
                "total_429_hits": self._stats.total_429_hits,
                "total_304_hits": self._stats.total_304_hits,
                "total_errors": self._stats.total_errors,
                "requests_by_group": dict(self._stats.requests_by_group),
                "cache_entries": len(self._cache),
                "buckets": {
                    name: {
                        "remaining": b.remaining,
                        "limit": b.limit,
                        "usage_pct": round((1 - b.usage_ratio) * 100, 1),
                        "penalty_count": b.penalty_count,
                    }
                    for name, b in self._buckets.items()
                },
                "updated_at": time.time(),
            }
            r.set("esi:rate_stats", json.dumps(data), ex=300)
        except Exception:
            pass

    @staticmethod
    def load_from_redis() -> dict | None:
        """Load stats from Redis (for API access from different process)."""
        try:
            import redis
            r = redis.from_url(settings.redis_url)
            data = r.get("esi:rate_stats")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_limit(limit_str: str) -> tuple[int, int]:
        """Parse '12000/15m' into (max_tokens, window_seconds)."""
        if not limit_str:
            return 0, 0
        try:
            parts = limit_str.split("/")
            tokens = int(parts[0])
            time_part = parts[1]
            if time_part.endswith("m"):
                seconds = int(time_part[:-1]) * 60
            elif time_part.endswith("h"):
                seconds = int(time_part[:-1]) * 3600
            else:
                seconds = int(time_part)
            return tokens, seconds
        except (ValueError, IndexError):
            return 0, 0
