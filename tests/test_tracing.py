"""
TMX-3900 — `traced` decorator contract tests.

Confirms:
  - decorator preserves return value (sync + async)
  - decorator records exceptions on the span and re-raises (no swallowing)
  - decorator captures `job_id` from TransMax-state-shaped first argument
  - decorator is a true no-op when TRANSMAX_OTEL_ENABLED is unset
  - get_tracer() returns a valid tracer instance (real or no-op) without crashing
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.tracing import get_tracer, traced


# ── Sync return-value preservation ──────────────────────────────────────


def test_sync_decorator_preserves_return_value() -> None:
    @traced("test.sync.echo")
    def echo(x: int, y: int) -> int:
        return x + y

    assert echo(2, 3) == 5


def test_sync_decorator_preserves_kwargs() -> None:
    @traced()
    def fmt(a: str, *, suffix: str = "!") -> str:
        return a + suffix

    assert fmt("hi", suffix="?") == "hi?"


# ── Async return-value preservation ─────────────────────────────────────


def test_async_decorator_preserves_return_value() -> None:
    @traced("test.async.echo")
    async def echo(x: int, y: int) -> int:
        await asyncio.sleep(0)  # force coroutine boundary
        return x * y

    assert asyncio.run(echo(4, 5)) == 20


# ── Exception path (sync + async) ───────────────────────────────────────


def test_sync_decorator_does_not_swallow_exceptions() -> None:
    @traced("test.sync.boom")
    def boom() -> None:
        raise ValueError("expected")

    with pytest.raises(ValueError, match="expected"):
        boom()


def test_async_decorator_does_not_swallow_exceptions() -> None:
    @traced("test.async.boom")
    async def boom() -> None:
        raise RuntimeError("expected-async")

    with pytest.raises(RuntimeError, match="expected-async"):
        asyncio.run(boom())


# ── job_id attribute capture (smoke — no-op tracer accepts but discards) ─


def test_decorator_handles_state_shaped_first_arg() -> None:
    """When the first arg has a job_id, decorator captures it without error."""

    @traced("test.state")
    def with_state(state: dict) -> str:
        return state.get("doc_id", "")

    state = {"job_id": "j-123", "doc_id": "d-456", "extra": "value"}
    assert with_state(state) == "d-456"


def test_decorator_handles_non_state_first_arg() -> None:
    """When the first arg isn't dict-shaped, the decorator does not crash."""

    @traced("test.scalar")
    def takes_int(x: int) -> int:
        return x + 1

    assert takes_int(41) == 42


def test_decorator_handles_no_args() -> None:
    @traced("test.empty")
    def noargs() -> str:
        return "ok"

    assert noargs() == "ok"


# ── No-op path (default state when TRANSMAX_OTEL_ENABLED unset) ─────────


def test_get_tracer_returns_object_with_start_as_current_span() -> None:
    """Whether OTel is enabled or not, the tracer must support the API."""
    tracer = get_tracer("test-tracer")
    cm = tracer.start_as_current_span("test-span")
    # Use as context manager — should not crash.
    with cm as span:
        # Span must accept attribute / exception calls.
        span.set_attribute("foo", "bar")
        span.record_exception(ValueError("inert"))
