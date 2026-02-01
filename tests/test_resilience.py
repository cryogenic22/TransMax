import pytest
import asyncio
from tenacity import RetryError
from app.services.resilience import ResilienceService
from unittest.mock import AsyncMock

async def test_resilience_success():
    """Test that it passes through on success."""
    mock_func = AsyncMock(return_value="Success")
    result = await ResilienceService.resilient_llm_call(mock_func)
    assert result == "Success"
    assert mock_func.call_count == 1

async def test_resilience_retry_logic():
    """Test that it retries on TimeoutError."""
    # Fail 2 times then succeed
    mock_func = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "Success"])
    
    result = await ResilienceService.resilient_llm_call(mock_func)
    assert result == "Success"
    assert mock_func.call_count == 3

async def test_resilience_failure():
    """Test that it eventually fails after max attempts."""
    mock_func = AsyncMock(side_effect=TimeoutError())
    
    with pytest.raises(RetryError):
        # We need to lower retry usage for test speed or rely on mock speed
        # But since we use wait_exponential, it might take a few seconds
        # For this unit test, we'll verify it raises RetryError 
        await ResilienceService.resilient_llm_call(mock_func)
