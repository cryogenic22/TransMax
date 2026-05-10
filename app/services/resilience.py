"""
ResilienceService — wraps external (LLM) calls with retry, circuit breaker,
and timeout.

TMX-051 introduced the circuit breaker as class-level state.
TMX-3052 (audit C-07) refactored to instance-based with a pluggable
``CircuitBreakerStateStore`` backend so the in-process breaker is
thread-safe today AND the descope §5.3 Redis-backed multi-worker variant
is a one-line swap (TMX-3052b).

Design:
- ``CircuitBreakerStateStore`` Protocol: minimal interface (5 methods).
- ``InMemoryStateStore``: ``threading.Lock``-protected in-process default.
  All mutations are sync methods called from inside async coroutines; the
  lock is acquired/released synchronously (never held across ``await``).
- ``RedisStateStore``: stub raising ``NotImplementedError`` — wired by
  TMX-3052b. A3 (no silent fallbacks): if Redis is configured but down,
  the constructor must raise; never silently fall back to
  ``InMemoryStateStore`` (would diverge per worker).
- ``ResilienceService``: instance-based, holds a ``state_store`` field.
- ``get_resilience_service()``: module-level lazy singleton, mirrors
  TMX-3053 ``get_quality_gate_service()``.

Class-level ``_state`` / ``_failure_count`` / ``_last_failure_time``
have been DELETED, not deprecated. C-07 is closed by removing the
shared mutable class state, not by adding a lock around it.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional, Protocol

import openai
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Setup logger
logger = logging.getLogger(__name__)

# Define retry strategy
# Wait 1s, 2s, 4s... up to 10s. Stop after 5 attempts.
retry_strategy = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.APITimeoutError,
        ConnectionError,
        TimeoutError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit is open (fail fast)."""

    pass


# ---------------------------------------------------------------------------
# State-store interface + implementations
# ---------------------------------------------------------------------------


class CircuitBreakerStateStore(Protocol):
    """
    Pluggable backend for circuit-breaker state.

    All methods MUST be safe to call from multiple threads / coroutines
    concurrently. Mutations must be atomic (read-modify-write under a
    single lock or single Redis op).
    """

    def get_state(self) -> CircuitState: ...

    def set_state(self, new_state: CircuitState) -> None: ...

    def get_failure_count(self) -> int: ...

    def increment_failures(self) -> int:
        """Atomically increment and return the new count."""
        ...

    def get_last_failure_time(self) -> float: ...

    def record_failure_time(self, t: float) -> None: ...

    def reset(self) -> None:
        """Reset to CLOSED + zero failures (success path)."""
        ...


class InMemoryStateStore:
    """
    Thread-safe in-process state store.

    Protected by a single ``threading.Lock``. Sync methods only — every
    state mutation is a sync compound op called from inside an async
    coroutine; the lock is never held across an ``await``, so an
    ``asyncio.Lock`` is not required (the GIL + threading.Lock already
    give the right serialisation for sync read-modify-write).

    See worksheet stage 6 / red team item #15 for the analysis.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0

    def get_state(self) -> CircuitState:
        with self._lock:
            return self._state

    def set_state(self, new_state: CircuitState) -> None:
        with self._lock:
            self._state = new_state

    def get_failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def increment_failures(self) -> int:
        with self._lock:
            self._failure_count += 1
            return self._failure_count

    def get_last_failure_time(self) -> float:
        with self._lock:
            return self._last_failure_time

    def record_failure_time(self, t: float) -> None:
        with self._lock:
            self._last_failure_time = t

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0


class RedisStateStore:
    """
    Redis-backed state store — STUB.

    Deferred to TMX-3052b: implement using SETNX / INCR / EXPIRE for atomic
    cross-worker counters. On instantiation, MUST verify Redis is
    reachable and fail loud (raise) if not — A3 forbids silent fallback
    to ``InMemoryStateStore`` because that would let two workers diverge
    invisibly under regulator-facing trust signals.
    """

    def __init__(self, redis_url: str) -> None:
        raise NotImplementedError(
            "RedisStateStore is not wired yet. See TMX-3052b. "
            "For pilot single-worker deployments, use InMemoryStateStore "
            "(the default)."
        )

    def get_state(self) -> CircuitState:  # pragma: no cover - stub
        raise NotImplementedError

    def set_state(self, new_state: CircuitState) -> None:  # pragma: no cover - stub
        raise NotImplementedError

    def get_failure_count(self) -> int:  # pragma: no cover - stub
        raise NotImplementedError

    def increment_failures(self) -> int:  # pragma: no cover - stub
        raise NotImplementedError

    def get_last_failure_time(self) -> float:  # pragma: no cover - stub
        raise NotImplementedError

    def record_failure_time(self, t: float) -> None:  # pragma: no cover - stub
        raise NotImplementedError

    def reset(self) -> None:  # pragma: no cover - stub
        raise NotImplementedError


# ---------------------------------------------------------------------------
# ResilienceService — instance-based
# ---------------------------------------------------------------------------


class ResilienceService:
    """
    Instance-based service to wrap external API calls with resilience
    patterns.

    TMX-051 introduced the circuit breaker.
    TMX-3052 (audit C-07): refactored from class-level globals to
    instance-based with pluggable ``CircuitBreakerStateStore``. The
    class-level ``_state`` / ``_failure_count`` / ``_last_failure_time``
    fields are deleted; all state lives in ``self.state_store``.
    """

    # Circuit breaker configuration (kept as instance-overridable defaults)
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60  # seconds

    def __init__(self, state_store: Optional[CircuitBreakerStateStore] = None) -> None:
        # Per-instance state-transition lock. Guards the compound
        # "check + transition" ops (e.g. CLOSED→OPEN) that span
        # multiple state-store reads/writes. The state_store's own
        # locks make individual ops atomic, but the breaker's
        # transition logic needs a coarser-grained lock to make
        # the transition itself atomic — exactly the C-07 race.
        self._transition_lock = threading.Lock()
        self.state_store: CircuitBreakerStateStore = state_store or InMemoryStateStore()

    def _check_circuit(self) -> None:
        """Checks if the circuit is open and raises if so."""
        # Fast read; the transition (OPEN→HALF_OPEN after recovery
        # timeout) is done under the transition lock to make the
        # CAS-shape transition atomic.
        if self.state_store.get_state() == CircuitState.OPEN:
            elapsed = time.time() - self.state_store.get_last_failure_time()
            if elapsed > self.RECOVERY_TIMEOUT:
                with self._transition_lock:
                    # Re-check under lock — another thread may have
                    # already transitioned us.
                    if self.state_store.get_state() == CircuitState.OPEN:
                        elapsed_inner = (
                            time.time() - self.state_store.get_last_failure_time()
                        )
                        if elapsed_inner > self.RECOVERY_TIMEOUT:
                            logger.info("Circuit Breaker probing (HALF_OPEN)...")
                            self.state_store.set_state(CircuitState.HALF_OPEN)
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit is OPEN. Fail fast active. "
                    f"Retry in {self.RECOVERY_TIMEOUT - elapsed:.1f}s"
                )
        # If HALF_OPEN, we allow the request through. Multiple concurrent
        # probes ARE possible by design — the first to fail/succeed wins
        # and transitions the state under _record_failure / _record_success
        # locks.

    def _record_success(self) -> None:
        """Reset circuit on success."""
        with self._transition_lock:
            if self.state_store.get_state() != CircuitState.CLOSED:
                logger.info("Circuit Breaker recovered (CLOSED).")
                self.state_store.reset()

    def _record_failure(self) -> None:
        """Record failure and potentially trip circuit (atomic)."""
        # Increment first (atomic via state_store lock).
        new_count = self.state_store.increment_failures()
        self.state_store.record_failure_time(time.time())

        # Transition decision must be atomic to avoid logging N times.
        with self._transition_lock:
            current = self.state_store.get_state()
            if current == CircuitState.HALF_OPEN:
                # Probe failed — back to OPEN, exactly once.
                self.state_store.set_state(CircuitState.OPEN)
                logger.error("Circuit Breaker probe failed. Returning to OPEN.")
            elif current == CircuitState.CLOSED and new_count >= self.FAILURE_THRESHOLD:
                self.state_store.set_state(CircuitState.OPEN)
                logger.error(
                    f"Circuit Breaker TRIPPED after {new_count} failures. "
                    "Fail fast enabled."
                )

    @staticmethod
    @retry_strategy
    async def _execute_with_retry(func: Callable, *args, **kwargs):
        """Internal execution with Tenacity retry logic."""
        return await func(*args, **kwargs)

    async def resilient_llm_call(
        self,
        func: Callable,
        *args,
        timeout_seconds: int = 60,
        **kwargs,
    ):
        """
        Executes a callable (LLM invoke) with Retries, Circuit Breaker, and Timeout.
        """
        # 1. Check Circuit
        self._check_circuit()

        try:
            # 2. Execute with Global Timeout
            result = await asyncio.wait_for(
                self._execute_with_retry(func, *args, **kwargs),
                timeout=timeout_seconds,
            )
            # 3. Success -> Reset
            self._record_success()
            return result
        except CircuitBreakerOpenError:
            raise  # Re-raise CB errors immediately
        except Exception as e:
            # 4. Failure -> Record
            self._record_failure()
            logger.error(f"Resilient Call Failed: {e}")
            raise

    def move_to_dlq(
        self,
        job_id: str,
        error_code: str,
        error_trace: str,
        payload,
    ) -> None:
        """
        Safely shuts down a job and archives it to the DLQ.
        """
        # Local imports to avoid circular dependency hell
        from app.models.models import DeadLetterQueue
        from app.services.db_service import get_db_service

        logger.error(
            f"Moving Job {job_id} to DEAD-LETTER QUEUE. Code: {error_code}"
        )

        db = get_db_service()
        session = db.get_session()
        try:
            # TMX-3012c: organization_id auto-injected from tenant context.
            # The pipeline runner enters org_context before invoking the
            # graph; if move_to_dlq is ever called outside that context, the
            # mixin raises TenantContextMissing — A3-correct.
            dlq_entry = DeadLetterQueue(
                job_id=job_id,
                error_code=error_code,
                error_trace=error_trace,
                payload_snapshot=payload,
                retry_count=self.state_store.get_failure_count(),
            )
            session.add(dlq_entry)
            session.commit()
            logger.info(f"Persisted DLQ Entry {dlq_entry.dlq_id}")
        except Exception as e:
            logger.critical(f"FATAL: FAILED TO WRIT TO DLQ! {e}")
            session.rollback()
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Module-level lazy singleton (mirrors TMX-3053 get_quality_gate_service)
# ---------------------------------------------------------------------------

_resilience_service_instance: Optional[ResilienceService] = None
_factory_lock = threading.Lock()


def get_resilience_service() -> ResilienceService:
    """
    Singleton accessor for ResilienceService.

    Mirrors TMX-3053 ``get_quality_gate_service()`` shape. Double-checked
    locking on the module-cache slot. Same DRY note: if a third copy of
    this pattern lands, extract to ``app.core.singletons.lazy_singleton``
    (TMX-LAZY-SINGLETON-HELPER).
    """
    global _resilience_service_instance
    if _resilience_service_instance is not None:
        return _resilience_service_instance
    with _factory_lock:
        if _resilience_service_instance is None:
            _resilience_service_instance = ResilienceService()
        return _resilience_service_instance
