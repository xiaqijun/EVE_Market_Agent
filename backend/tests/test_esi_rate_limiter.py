import time
from app.tools.rate_limiter import TokenBucket, EsiRateLimiter


def test_token_bucket_consumes_tokens():
    bucket = TokenBucket(rate=10, capacity=10)
    assert bucket.consume(5) is True
    assert bucket.tokens == 5


def test_token_bucket_refuses_when_empty():
    bucket = TokenBucket(rate=10, capacity=10)
    assert bucket.consume(10) is True
    assert bucket.consume(1) is False


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(rate=100, capacity=10)
    bucket.consume(10)
    time.sleep(0.15)
    assert bucket.tokens >= 1


def test_rate_limiter_acquires():
    limiter = EsiRateLimiter(default_rate=100)
    assert limiter.acquire() is True


def test_rate_limiter_estimated_wait():
    limiter = EsiRateLimiter(default_rate=1, capacity=1)
    limiter.acquire()
    wait = limiter.estimated_wait()
    assert wait is not None


def test_token_bucket_available_property():
    bucket = TokenBucket(rate=10, capacity=10)
    assert bucket.available == 10
    bucket.consume(3)
    assert bucket.available == 7
