"""
TMX-3052 — regression tests for circuit-breaker thread-safety (audit C-07).

These tests reproduce the race conditions called out in the May 2026 audit:
- compound read-modify-write on `_failure_count` loses increments
- concurrent threshold-crossings emit multiple "OPEN" log lines
- concurrent HALF_OPEN probe failures transition the state multiple times

Pattern mirrors TMX-3053:
- `Barrier(N)` to release all threads simultaneously
- injected micro-sleep inside the read-modify-write to widen the race window
- assertion on a counter wrapped around the side effect (logger or count)

Each test runs once with stress; the loop runs the file 50x as the green-stable
gate (see worksheet stage 5).
"""
from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from app.services.resilience import (
    CircuitBreakerOpenError,  # noqa: F401  (kept for callers needing it)
    CircuitState,
    InMemoryStateStore,
    ResilienceService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_service(threshold: int = 5) -> ResilienceService:
    """Build a ResilienceService with a fresh InMemoryStateStore (test isolation)."""
    svc = ResilienceService(state_store=InMemoryStateStore())
    svc.FAILURE_THRESHOLD = threshold
    return svc


# ---------------------------------------------------------------------------
# Test 1: concurrent failures count atomically
# ---------------------------------------------------------------------------


def test_concurrent_failures_count_atomically():
    """
    AC-1: N threads each call _record_failure(); final _failure_count == N.

    Pre-fix: read-modify-write on `cls._failure_count += 1` loses increments
    under thread interleaving. Each thread reads (say) 3, both write 4, the
    second increment is lost.

    Post-fix: InMemoryStateStore.increment_failures() is lock-protected.
    """
    N = 32
    svc = _fresh_service(threshold=N + 100)  # high threshold so no trip
    barrier = threading.Barrier(N)

    # Inject a micro-sleep INSIDE the increment to widen the race window.
    real_increment = svc.state_store.increment_failures

    def slow_increment() -> int:
        # Simulate a slow read-modify-write — what the unfixed code looked
        # like, where the increment was three Python statements with the
        # GIL releasable between them.
        time.sleep(0.001)
        return real_increment()

    with patch.object(svc.state_store, "increment_failures", slow_increment):

        def worker():
            barrier.wait()
            svc._record_failure()

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert svc.state_store.get_failure_count() == N, (
        f"expected {N} failures, got {svc.state_store.get_failure_count()} — "
        "C-07 race lost increments"
    )


# ---------------------------------------------------------------------------
# Test 2: concurrent state transitions log OPEN exactly once
# ---------------------------------------------------------------------------


def test_concurrent_threshold_crossings_log_open_exactly_once(caplog):
    """
    AC-2: N threads each push the breaker over threshold; only ONE
    "Circuit Breaker TRIPPED" log line fires.

    Pre-fix: many threads simultaneously observe `_failure_count >= THRESHOLD`
    while `_state == CLOSED`, and ALL of them transition CLOSED→OPEN, each
    logging "TRIPPED". Both noisy and incorrect (the trip is a one-shot
    transition, not a repeatable event).

    Post-fix: the transition is atomic under the state-store lock.
    """
    N = 32
    THRESHOLD = 5
    svc = _fresh_service(threshold=THRESHOLD)
    barrier = threading.Barrier(N)

    open_log_count = 0
    open_log_lock = threading.Lock()

    real_logger_error = logging.getLogger("app.services.resilience").error

    def counting_error(msg, *args, **kwargs):
        nonlocal open_log_count
        if isinstance(msg, str) and "TRIPPED" in msg:
            with open_log_lock:
                open_log_count += 1
        real_logger_error(msg, *args, **kwargs)

    def worker():
        barrier.wait()
        # Each thread injects one failure; with N=32 and threshold=5 every
        # thread crosses the threshold by the time it records.
        svc._record_failure()

    with patch.object(
        logging.getLogger("app.services.resilience"), "error", counting_error
    ):
        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    # Final state must be OPEN
    assert svc.state_store.get_state() == CircuitState.OPEN

    # And exactly one TRIPPED log line, not N
    assert open_log_count == 1, (
        f"expected 1 'TRIPPED' log line, got {open_log_count} — "
        "C-07 race fires N transitions"
    )


# ---------------------------------------------------------------------------
# Test 3: HALF_OPEN probe failure transitions to OPEN exactly once
# ---------------------------------------------------------------------------


def test_concurrent_half_open_probe_failures_transition_once(caplog):
    """
    AC-3: When state is HALF_OPEN and N concurrent probes all fail, the
    transition to OPEN happens exactly once (not N times).

    The pre-fix code's comment is explicit:
        "Assuming single-threaded check logic or accepting race conditions
         for simplicity check."

    Under N concurrent probes this is wrong — each thread observes
    HALF_OPEN, each calls _record_failure which checks `if state ==
    HALF_OPEN: state = OPEN; log.error(...)` — N log lines.
    """
    N = 16
    svc = _fresh_service(threshold=5)
    # Force the breaker into HALF_OPEN
    svc.state_store.set_state(CircuitState.HALF_OPEN)
    barrier = threading.Barrier(N)

    probe_failed_log_count = 0
    probe_log_lock = threading.Lock()

    real_logger_error = logging.getLogger("app.services.resilience").error

    def counting_error(msg, *args, **kwargs):
        nonlocal probe_failed_log_count
        if isinstance(msg, str) and "probe failed" in msg.lower():
            with probe_log_lock:
                probe_failed_log_count += 1
        real_logger_error(msg, *args, **kwargs)

    def worker():
        barrier.wait()
        svc._record_failure()

    with patch.object(
        logging.getLogger("app.services.resilience"), "error", counting_error
    ):
        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert svc.state_store.get_state() == CircuitState.OPEN
    assert probe_failed_log_count == 1, (
        f"expected 1 'probe failed' log line, got {probe_failed_log_count}"
        " — C-07 HALF_OPEN race fires N transitions"
    )


# ---------------------------------------------------------------------------
# Sanity: factory returns the same instance under concurrent access
# ---------------------------------------------------------------------------


def test_factory_returns_same_instance_under_concurrent_access():
    """
    AC-5 sanity: get_resilience_service() is a thread-safe lazy singleton
    (mirrors TMX-3053 get_quality_gate_service pattern).
    """
    from app.services import resilience as resilience_module

    # Reset module-level cache for the test
    with resilience_module._factory_lock:
        resilience_module._resilience_service_instance = None

    N = 32
    barrier = threading.Barrier(N)
    instances: list[ResilienceService] = []
    instances_lock = threading.Lock()

    def worker():
        barrier.wait()
        svc = resilience_module.get_resilience_service()
        with instances_lock:
            instances.append(svc)

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(instances) == N
    first = instances[0]
    for svc in instances[1:]:
        assert svc is first, "factory returned different instances under race"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
