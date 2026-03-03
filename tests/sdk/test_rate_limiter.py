"""Tests for token bucket rate limiter."""

import pytest
import time
from transmax_sdk.resilience.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    def test_initial_tokens_available(self):
        rl = TokenBucketRateLimiter(tokens_per_second=10.0)
        assert rl.available_tokens > 0

    def test_try_acquire_success(self):
        rl = TokenBucketRateLimiter(tokens_per_second=10.0)
        assert rl.try_acquire(1.0) is True

    def test_try_acquire_depletes(self):
        rl = TokenBucketRateLimiter(tokens_per_second=10.0, max_tokens=2.0)
        assert rl.try_acquire(1.0) is True
        assert rl.try_acquire(1.0) is True
        assert rl.try_acquire(1.0) is False

    def test_tokens_refill(self):
        rl = TokenBucketRateLimiter(tokens_per_second=100.0, max_tokens=2.0)
        rl.try_acquire(2.0)
        time.sleep(0.05)  # Should refill ~5 tokens
        assert rl.available_tokens > 0

    @pytest.mark.asyncio
    async def test_acquire_waits(self):
        rl = TokenBucketRateLimiter(tokens_per_second=100.0, max_tokens=1.0)
        rl.try_acquire(1.0)  # Deplete
        start = time.monotonic()
        await rl.acquire(1.0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # Should wait briefly then succeed

    @pytest.mark.asyncio
    async def test_acquire_basic(self):
        rl = TokenBucketRateLimiter(tokens_per_second=100.0)
        await rl.acquire(1.0)  # Should not raise
