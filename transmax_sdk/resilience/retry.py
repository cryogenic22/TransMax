"""Configurable retry strategy with exponential backoff."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, Optional, Set, Type

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class RetryStrategy:
    """Configurable retry with exponential backoff and jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Set[Type[Exception]]] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter
        self._retryable = retryable_exceptions or {Exception}
        self._telemetry = telemetry or NoOpTelemetry()

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function with retry logic."""
        last_error = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                if not any(isinstance(e, t) for t in self._retryable):
                    raise

                last_error = e
                if attempt == self._max_attempts:
                    break

                delay = self._calculate_delay(attempt)
                self._telemetry.log_structured(
                    "warning",
                    f"Retry {attempt}/{self._max_attempts} after {delay:.1f}s",
                    error=str(e),
                )
                await asyncio.sleep(delay)

        raise RetryExhaustedError(
            f"All {self._max_attempts} attempts exhausted"
        ) from last_error

    def _calculate_delay(self, attempt: int) -> float:
        delay = self._base_delay * (2 ** (attempt - 1))
        delay = min(delay, self._max_delay)
        if self._jitter:
            delay *= (0.5 + random.random() * 0.5)
        return delay
