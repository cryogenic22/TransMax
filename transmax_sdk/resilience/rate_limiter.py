"""Token bucket rate limiter."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class TokenBucketRateLimiter:
    """Rate limiter using the token bucket algorithm.

    Tokens refill at a constant rate. Each request consumes one token.
    If no tokens are available, the caller waits until one is available.
    """

    def __init__(
        self,
        tokens_per_second: float = 10.0,
        max_tokens: Optional[float] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._rate = tokens_per_second
        self._max_tokens = max_tokens or tokens_per_second * 2
        self._tokens = self._max_tokens
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._telemetry = telemetry or NoOpTelemetry()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens, waiting if necessary."""
        async with self._lock:
            self._refill()
            while self._tokens < tokens:
                wait_time = (tokens - self._tokens) / self._rate
                self._telemetry.log_structured(
                    "debug", f"Rate limited, waiting {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)
                self._refill()
            self._tokens -= tokens

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Try to acquire tokens without waiting. Returns True if successful."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens
