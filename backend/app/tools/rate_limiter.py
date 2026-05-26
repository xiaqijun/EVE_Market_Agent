import time
import threading
import redis
from app.config import settings


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self, n: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self.tokens


class EsiRateLimiter:
    def __init__(self, default_rate: float = 100):
        self.default_rate = default_rate
        self.redis = redis.from_url(settings.redis_url)
        self._bucket = TokenBucket(rate=default_rate, capacity=int(default_rate * 2))

    def acquire(self, n: int = 1) -> bool:
        return self._bucket.consume(n)

    def estimated_wait(self, n: int = 1) -> float | None:
        if self._bucket.available >= n:
            return 0
        return (n - self._bucket.available) / self._bucket.rate

    def enqueue(self, endpoint: str, params_hash: str) -> str:
        key = f"esi:queue:{endpoint}"
        task_id = self.redis.rpush(key, params_hash)
        return f"{endpoint}:{task_id}"

    def dequeue(self, endpoint: str) -> str | None:
        key = f"esi:queue:{endpoint}"
        return self.redis.lpop(key)
