import pytest
from tenacity import RetryError
from unittest.mock import AsyncMock

from app.services.resilience import (
    InMemoryStateStore,
    ResilienceService,
)


def _fresh_service() -> ResilienceService:
    """Build a service with a fresh in-memory store (test isolation)."""
    return ResilienceService(state_store=InMemoryStateStore())


async def test_resilience_success():
    """Test that it passes through on success."""
    svc = _fresh_service()
    mock_func = AsyncMock(return_value="Success")
    result = await svc.resilient_llm_call(mock_func)
    assert result == "Success"
    assert mock_func.call_count == 1


async def test_resilience_retry_logic():
    """Test that it retries on TimeoutError."""
    svc = _fresh_service()
    # Fail 2 times then succeed
    mock_func = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "Success"])

    result = await svc.resilient_llm_call(mock_func)
    assert result == "Success"
    assert mock_func.call_count == 3


async def test_resilience_failure():
    """Test that it eventually fails after max attempts."""
    svc = _fresh_service()
    mock_func = AsyncMock(side_effect=TimeoutError())

    with pytest.raises(RetryError):
        await svc.resilient_llm_call(mock_func)
