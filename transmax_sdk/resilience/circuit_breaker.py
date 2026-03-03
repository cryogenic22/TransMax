"""Instance-based circuit breaker (not class-level)."""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    pass


class CircuitBreaker:
    """Instance-based circuit breaker with configurable thresholds.

    States:
    - CLOSED: Normal operation, tracking failures.
    - OPEN: Rejecting all calls (fail-fast) after threshold breached.
    - HALF_OPEN: Allowing a single probe call to test recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._name = name
        self._telemetry = telemetry or NoOpTelemetry()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._success_count_half_open = 0

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for recovery timeout."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._telemetry.gauge(
                    "transmax_circuit_breaker_state", 2.0,
                    labels={"provider": self._name},
                )
        return self._state

    def check(self) -> None:
        """Check if circuit allows a call. Raises CircuitBreakerOpenError if not."""
        current = self.state
        if current == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self._name}' is OPEN. "
                f"Recovery in {self._time_until_recovery():.0f}s."
            )

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._telemetry.gauge(
                "transmax_circuit_breaker_state", 0.0,
                labels={"provider": self._name},
            )
            self._telemetry.log_structured("info", f"Circuit '{self._name}' recovered (CLOSED)")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self._threshold and self._state != CircuitState.OPEN:
            self._state = CircuitState.OPEN
            self._telemetry.gauge(
                "transmax_circuit_breaker_state", 1.0,
                labels={"provider": self._name},
            )
            self._telemetry.log_structured(
                "warning",
                f"Circuit '{self._name}' OPEN after {self._failure_count} failures",
            )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _time_until_recovery(self) -> float:
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        return max(0.0, self._recovery_timeout - elapsed)

    @property
    def failure_count(self) -> int:
        return self._failure_count
