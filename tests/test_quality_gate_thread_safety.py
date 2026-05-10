"""
TMX-3053 — Thread-safety regression suite for QualityGateService singleton.

Audit C-08 (2026-05-09 audit §5): the singleton uses `_initialized` to gate
construction work, but the read-then-act on that flag is not atomic. Under
concurrent first-touch, one thread can see `_initialized=False`, begin loading
language packs, then a second thread enters the same branch and either (a)
duplicates the work, or (b) reads partially-initialised state.

These tests reproduce the race window before the fix and verify the
post-fix invariants (exactly-once init, fully-populated state for every
caller, lock-protected `_lang_packs` cache).

Determinism strategy
--------------------
We use a `threading.Barrier(N)` to release N threads simultaneously, plus
a slow `__init__` body (monkeypatched to insert a `time.sleep`) to widen
the race window from microseconds to ~50 ms. This makes the race
deterministically reproducible against unfixed code (50/50 reds in stress
mode), which is the G2 reproduce-the-failure gate.
"""
from __future__ import annotations

import threading
import time
from typing import List
from unittest.mock import patch

import pytest

from app.services import quality_gate as qg_module
from app.services.quality_gate import QualityGateService


@pytest.fixture(autouse=True)
def _reset_singleton_state():
    """
    Reset class-level singleton state between tests so each test starts
    clean. We touch the private attributes directly because the production
    code holds them on the class, not on an instance.
    """
    QualityGateService._instance = None
    QualityGateService._initialized = False
    qg_module._gate_service_instance = None
    yield
    QualityGateService._instance = None
    QualityGateService._initialized = False
    qg_module._gate_service_instance = None


def _spawn_concurrent_constructors(
    n_threads: int,
    init_delay_seconds: float = 0.05,
) -> tuple[List[QualityGateService], int]:
    """
    Spawn `n_threads` threads that all call `QualityGateService()` at the
    same moment (released by a Barrier). Returns the list of instances each
    thread observed, plus the count of times the post-guard
    `_populate_initial_state` hook ran.

    We patch ``_populate_initial_state`` (the hookable extraction of the
    init body) rather than ``__init__`` itself, so the production
    double-checked-locking guard around the call site is exercised. The
    patched body inserts a sleep to widen the race window from
    microseconds to ~50 ms, making the race deterministically reproducible
    against unfixed code.
    """
    init_body_invocations = 0
    counter_lock = threading.Lock()

    def slow_populate(self):
        nonlocal init_body_invocations
        with counter_lock:
            init_body_invocations += 1
        # Widen the race window between the guard read and the state write.
        time.sleep(init_delay_seconds)
        self._lang_pack_lock = threading.Lock()
        self._lang_packs = {}

    instances: List[QualityGateService] = []
    instances_lock = threading.Lock()
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        instance = QualityGateService()
        with instances_lock:
            instances.append(instance)

    with patch.object(QualityGateService, "_populate_initial_state", slow_populate):
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
        for t in threads:
            assert not t.is_alive(), "thread did not finish in time"

    return instances, init_body_invocations


def test_concurrent_first_touch_initializes_exactly_once():
    """
    C-08 regression — under concurrent first-touch, the service initialises
    exactly once and all threads see the same fully-initialised instance.
    """
    n_threads = 32
    instances, init_body_invocations = _spawn_concurrent_constructors(n_threads)

    assert len(instances) == n_threads, "every thread should have produced an instance"

    # All threads must observe the SAME instance object (singleton invariant).
    canonical = instances[0]
    for inst in instances:
        assert inst is canonical, "singleton broke: threads got distinct instances"

    # The post-guard init body must execute EXACTLY ONCE across all threads.
    # Pre-fix: this is the failing assertion (multiple threads enter the body
    # because the read-then-act on `_initialized` is not atomic).
    assert init_body_invocations == 1, (
        f"expected exactly 1 init-body invocation, got {init_body_invocations}; "
        "C-08 race is live (initialisation work duplicated across threads)"
    )

    # Every caller must see fully-populated state. `_lang_packs` is a dict;
    # if a thread saw a partially-initialised instance, this attr would be
    # missing or not a dict.
    assert hasattr(canonical, "_lang_packs"), "instance missing _lang_packs attr"
    assert isinstance(canonical._lang_packs, dict)


def test_concurrent_get_quality_gate_service_initializes_exactly_once():
    """
    The module-level `get_quality_gate_service()` accessor has the same
    race shape as direct `QualityGateService()` construction. Under
    concurrent first-touch, the accessor must also produce exactly one
    instance (and the underlying class init body must run once).
    """
    n_threads = 32
    barrier = threading.Barrier(n_threads)
    instances: List[QualityGateService] = []
    instances_lock = threading.Lock()

    init_body_invocations = 0
    counter_lock = threading.Lock()

    def slow_populate(self):
        nonlocal init_body_invocations
        with counter_lock:
            init_body_invocations += 1
        time.sleep(0.05)
        self._lang_pack_lock = threading.Lock()
        self._lang_packs = {}

    def worker():
        barrier.wait()
        instance = qg_module.get_quality_gate_service()
        with instances_lock:
            instances.append(instance)

    with patch.object(QualityGateService, "_populate_initial_state", slow_populate):
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

    assert len(instances) == n_threads
    canonical = instances[0]
    for inst in instances:
        assert inst is canonical, (
            "get_quality_gate_service() returned distinct instances under contention"
        )
    assert init_body_invocations == 1, (
        f"expected exactly 1 init-body invocation via accessor, got {init_body_invocations}"
    )


def test_concurrent_lang_pack_load_is_atomic():
    """
    `QualityGateService._load_lang_pack` lazily caches packs into
    `self._lang_packs`. Under concurrent first-touch of an unloaded
    language, the load function must execute exactly once and every
    caller must observe the same cached pack object.

    This is the same C-08 shape as the singleton init guard but applied
    to the per-language cache.
    """
    instance = QualityGateService()
    instance._lang_packs = {}  # ensure clean cache

    real_factory_module = "app.services.language_packs.factory"
    load_invocations = 0
    counter_lock = threading.Lock()
    sentinel_pack = object()  # unique pack object we hand back

    def slow_get_pack(lang_code: str):
        nonlocal load_invocations
        with counter_lock:
            load_invocations += 1
        time.sleep(0.05)
        return sentinel_pack

    n_threads = 16
    barrier = threading.Barrier(n_threads)
    observed: List[object] = []
    observed_lock = threading.Lock()

    def worker():
        barrier.wait()
        pack = instance._load_lang_pack("xx")
        with observed_lock:
            observed.append(pack)

    with patch(f"{real_factory_module}.LanguagePackFactory.get_pack", side_effect=slow_get_pack):
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

    assert len(observed) == n_threads
    for p in observed:
        assert p is sentinel_pack, "thread observed wrong pack instance"

    # Pre-fix: this is the failing assertion. The lazy cache write
    # (`self._lang_packs[lang_code] = pack`) is not lock-guarded, so
    # multiple threads enter the load branch and re-run get_pack.
    assert load_invocations == 1, (
        f"expected exactly 1 lang-pack load, got {load_invocations}; "
        "C-08 race is live in _load_lang_pack cache"
    )
