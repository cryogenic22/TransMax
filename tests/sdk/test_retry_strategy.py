"""Tests for retry strategy."""

import pytest
from transmax_sdk.resilience.retry import RetryStrategy, RetryExhaustedError


class TestRetryStrategy:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        strategy = RetryStrategy(max_attempts=3)
        result = await strategy.execute(lambda: 42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        attempt_count = 0

        def flaky():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary error")
            return "success"

        strategy = RetryStrategy(max_attempts=3, base_delay=0.01)
        result = await strategy.execute(flaky)
        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_raises(self):
        def always_fail():
            raise ValueError("Permanent error")

        strategy = RetryStrategy(max_attempts=2, base_delay=0.01)
        with pytest.raises(RetryExhaustedError):
            await strategy.execute(always_fail)

    @pytest.mark.asyncio
    async def test_non_retryable_not_retried(self):
        attempt_count = 0

        def raises_type_error():
            nonlocal attempt_count
            attempt_count += 1
            raise TypeError("Not retryable")

        strategy = RetryStrategy(
            max_attempts=3,
            retryable_exceptions={ValueError},
            base_delay=0.01,
        )
        with pytest.raises(TypeError):
            await strategy.execute(raises_type_error)
        assert attempt_count == 1  # Not retried

    @pytest.mark.asyncio
    async def test_async_function(self):
        async def async_fn():
            return "async result"

        strategy = RetryStrategy()
        result = await strategy.execute(async_fn)
        assert result == "async result"

    @pytest.mark.asyncio
    async def test_exponential_delay(self):
        strategy = RetryStrategy(max_attempts=3, base_delay=1.0, jitter=False)
        # delay for attempt 1 = 1.0, attempt 2 = 2.0
        d1 = strategy._calculate_delay(1)
        d2 = strategy._calculate_delay(2)
        assert d2 > d1

    @pytest.mark.asyncio
    async def test_max_delay_capped(self):
        strategy = RetryStrategy(max_attempts=10, base_delay=1.0, max_delay=5.0, jitter=False)
        d = strategy._calculate_delay(10)
        assert d <= 5.0
