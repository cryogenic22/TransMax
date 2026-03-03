"""Resilience protocol: contract for resilience implementations."""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class ResilienceProtocol(Protocol):
    """Interface for resilience wrappers."""

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function with resilience (circuit breaker, retry, rate limit)."""
        ...
