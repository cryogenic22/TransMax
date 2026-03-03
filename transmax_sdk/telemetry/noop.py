"""No-op telemetry implementation for testing and standalone use."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple


class NoOpTelemetry:
    """Telemetry that does nothing - safe default for standalone/testing use.

    Optionally records calls for test assertions when record=True.
    """

    def __init__(self, record: bool = False) -> None:
        self._record = record
        self.spans: List[Tuple[str, Optional[Dict[str, Any]]]] = []
        self.counters: List[Tuple[str, float, Optional[Dict[str, str]]]] = []
        self.histograms: List[Tuple[str, float, Optional[Dict[str, str]]]] = []
        self.gauges: List[Tuple[str, float, Optional[Dict[str, str]]]] = []
        self.logs: List[Dict[str, Any]] = []

    @contextmanager
    def span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Generator[None, None, None]:
        if self._record:
            self.spans.append((name, attributes))
        yield

    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        if self._record:
            self.counters.append((name, value, labels))

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if self._record:
            self.histograms.append((name, value, labels))

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if self._record:
            self.gauges.append((name, value, labels))

    def log_structured(self, level: str, message: str, **kwargs: Any) -> None:
        if self._record:
            self.logs.append({"level": level, "message": message, **kwargs})

    def reset(self) -> None:
        """Clear all recorded calls."""
        self.spans.clear()
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
        self.logs.clear()
