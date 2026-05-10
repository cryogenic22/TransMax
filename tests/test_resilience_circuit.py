import asyncio
import pytest
from unittest.mock import AsyncMock

from app.services.resilience import (
    CircuitBreakerOpenError,
    CircuitState,
    InMemoryStateStore,
    ResilienceService,
)


def _fresh_service(threshold: int = 5) -> ResilienceService:
    """Build a service with a fresh in-memory store + given threshold."""
    svc = ResilienceService(state_store=InMemoryStateStore())
    svc.FAILURE_THRESHOLD = threshold
    return svc


@pytest.mark.asyncio
async def test_retry_eventually_fails():
    """Verify tenacity retry exhaustion leads to failure record."""
    svc = _fresh_service(threshold=5)

    mock_func = AsyncMock(side_effect=ValueError("Boom"))

    with pytest.raises(ValueError):
        await svc.resilient_llm_call(mock_func)

    # Tenacity retries 5 times (configured in retry_strategy).
    # BUT resilient_llm_call wraps execution. Tenacity raises ONE exception after exhaustion.
    # So _record_failure is called ONCE per resilient_llm_call invocation (after all retries fail).
    assert svc.state_store.get_failure_count() == 1


@pytest.mark.asyncio
async def test_circuit_trips():
    """Verify Circuit trips after Threshold."""
    svc = _fresh_service(threshold=2)  # Low threshold for test

    mock_func = AsyncMock(side_effect=ValueError("Boom"))

    # Fail 1
    with pytest.raises(ValueError):
        await svc.resilient_llm_call(mock_func)
    assert svc.state_store.get_state() == CircuitState.CLOSED

    # Fail 2 (Threshold reached)
    with pytest.raises(ValueError):
        await svc.resilient_llm_call(mock_func)

    # Should be OPEN now
    assert svc.state_store.get_state() == CircuitState.OPEN

    # Next call should be FAST FAIL (CircuitBreakerOpenError)
    # And mock_func should NOT be called
    mock_func.reset_mock()
    with pytest.raises(CircuitBreakerOpenError):
        await svc.resilient_llm_call(mock_func)

    assert not mock_func.called


@pytest.mark.asyncio
async def test_timeout_enforcement():
    """Verify strict timeout."""
    svc = _fresh_service()

    async def slow_func():
        await asyncio.sleep(0.5)
        return "ok"

    # Call with timeout=0.1s
    with pytest.raises(asyncio.TimeoutError):
        await svc.resilient_llm_call(slow_func, timeout_seconds=0.1)
