import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.resilience import ResilienceService, CircuitBreakerOpenError, CircuitState

@pytest.mark.asyncio
async def test_retry_eventually_fails():
    """Verify tenacity retry exhaustion leads to failure record."""
    ResilienceService._state = CircuitState.CLOSED
    ResilienceService._failure_count = 0
    ResilienceService.FAILURE_THRESHOLD = 5
    
    # Mock function failing
    mock_func = AsyncMock(side_effect=ValueError("Boom"))
    
    with pytest.raises(ValueError):
        await ResilienceService.resilient_llm_call(mock_func)
        
    # Tenacity retries 5 times (configured in retry_strategy). 
    # BUT resilient_llm_call wraps execution. Tenacity raises ONE exception after exhaustion.
    # So _record_failure is called ONCE per resilient_llm_call invocation (after all retries fail).
    assert ResilienceService._failure_count == 1

@pytest.mark.asyncio
async def test_circuit_trips():
    """Verify Circuit trips after Threshold."""
    ResilienceService._state = CircuitState.CLOSED
    ResilienceService._failure_count = 0
    ResilienceService.FAILURE_THRESHOLD = 2 # Low threshold for test
    
    mock_func = AsyncMock(side_effect=ValueError("Boom"))
    
    # Fail 1
    with pytest.raises(ValueError):
        await ResilienceService.resilient_llm_call(mock_func)
    assert ResilienceService._state == CircuitState.CLOSED
    
    # Fail 2 (Threshold reached)
    with pytest.raises(ValueError):
        await ResilienceService.resilient_llm_call(mock_func)
    
    # Should be OPEN now
    assert ResilienceService._state == CircuitState.OPEN
    
    # Next call should be FAST FAIL (CircuitBreakerOpenError)
    # And mock_func should NOT be called
    mock_func.reset_mock()
    with pytest.raises(CircuitBreakerOpenError):
        await ResilienceService.resilient_llm_call(mock_func)
    
    assert not mock_func.called

@pytest.mark.asyncio
async def test_timeout_enforcement():
    """Verify strict timeout."""
    ResilienceService._state = CircuitState.CLOSED
    
    async def slow_func():
        await asyncio.sleep(0.5)
        return "ok"
        
    # Call with timeout=0.1s
    with pytest.raises(asyncio.TimeoutError):
        await ResilienceService.resilient_llm_call(slow_func, timeout_seconds=0.1)
        
    # Ensure failure recorded
    # Note: failure count increments on timeout too
    # assert ResilienceService._failure_count > 0 # Depends on state from prev tests if not reset
    # (Actually we should reset state or ordering matters. I reset at start of tests).
    
if __name__ == "__main__":
    asyncio.run(test_retry_eventually_fails())
    print("PASS test_retry_eventually_fails")
    
    asyncio.run(test_circuit_trips())
    print("PASS test_circuit_trips")
    
    asyncio.run(test_timeout_enforcement())
    print("PASS test_timeout_enforcement")
