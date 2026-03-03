"""Telemetry protocol: the contract all telemetry implementations must satisfy."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional, Protocol, runtime_checkable


@runtime_checkable
class TelemetryProtocol(Protocol):
    """Interface for telemetry providers (OTel, Prometheus, NoOp)."""

    @contextmanager
    def span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Generator[None, None, None]:
        """Create a tracing span around a block of code."""
        ...

    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        ...

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation."""
        ...

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value."""
        ...

    def log_structured(self, level: str, message: str, **kwargs: Any) -> None:
        """Emit a structured log entry."""
        ...
