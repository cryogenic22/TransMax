from typing import Callable, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
import openai
import asyncio
import time
from enum import Enum

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
        TimeoutError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreakerOpenError(Exception):
    """Raised when the circuit is open (fail fast)."""
    pass

class ResilienceService:
    """
    Service to wrap external API calls with resilience patterns.
    TMX-051: Hardened with Circuit Breaker and Strict Timeouts.
    """
    
    # Circuit Breaker Configuration
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60 # seconds
    
    # Global Circuit State (In-Memory)
    # Ideally this would be in Redis for distributed systems, but per-instance is fine for V1.
    _state = CircuitState.CLOSED
    _failure_count = 0
    _last_failure_time = 0

    @classmethod
    def _check_circuit(cls):
        """Checks if the circuit is open and raises if so."""
        if cls._state == CircuitState.OPEN:
            elapsed = time.time() - cls._last_failure_time
            if elapsed > cls.RECOVERY_TIMEOUT:
                logger.info("Circuit Breaker probing (HALF_OPEN)...")
                cls._state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit is OPEN. Fail fast active. Retry in {cls.RECOVERY_TIMEOUT - elapsed:.1f}s")
        
        # If HALF_OPEN, we allow 1 request to pass (the current one)
        # Assuming single-threaded check logic or accepting race conditions for simplicity check.

    @classmethod
    def _record_success(cls):
        """Reset circuit on success."""
        if cls._state != CircuitState.CLOSED:
            logger.info("Circuit Breaker recovered (CLOSED).")
            cls._state = CircuitState.CLOSED
            cls._failure_count = 0

    @classmethod
    def _record_failure(cls):
        """Record failure and potentially trip circuit."""
        cls._failure_count += 1
        cls._last_failure_time = time.time()
        
        if cls._state == CircuitState.HALF_OPEN:
            # If we were probing and failed, go back to OPEN immediately
            cls._state = CircuitState.OPEN
            logger.error("Circuit Breaker probe failed. Returning to OPEN.")
            
        elif cls._failure_count >= cls.FAILURE_THRESHOLD:
            if cls._state == CircuitState.CLOSED:
                cls._state = CircuitState.OPEN
                logger.error(f"Circuit Breaker TRIPPED after {cls._failure_count} failures. Fail fast enabled.")

    @staticmethod
    @retry_strategy
    async def _execute_with_retry(func: Callable, *args, **kwargs) -> Any:
        """Internal execution with Tenacity retry logic."""
        return await func(*args, **kwargs)

    @classmethod
    async def resilient_llm_call(cls, func: Callable, *args, timeout_seconds: int = 60, **kwargs) -> Any:
        """
        Executes a callable (LLM invoke) with Retries, Circuit Breaker, and Timeout.
        """
        # 1. Check Circuit
        cls._check_circuit()
        
        try:
            # 2. Execute with Global Timeout
            # We wrap the *retrying* execution in a timeout.
            # So if retries take too long, we abort.
            result = await asyncio.wait_for(
                cls._execute_with_retry(func, *args, **kwargs),
                timeout=timeout_seconds
            )
            
            # 3. Success -> Reset
            cls._record_success()
            return result
            
        except CircuitBreakerOpenError:
            raise # Re-raise CB errors immediately
        except Exception as e:
            # 4. Failure -> Record
            # Note: Tenacity raises the underlying exception after retries are exhausted.
            # Or asyncio.TimeoutError if timed out.
            cls._record_failure()
            logger.error(f"Resilient Call Failed: {e}")
            raise e

    @classmethod
    def move_to_dlq(cls, job_id: str, error_code: str, error_trace: str, payload: Any):
        """
        Safely shuts down a job and archives it to the DLQ.
        """
        # Local imports to avoid circular dependency hell
        from app.services.db_service import get_db_service
        from app.models.models import DeadLetterQueue
        
        logger.error(f"Moving Job {job_id} to DEAD-LETTER QUEUE. Code: {error_code}")
        
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
                retry_count=cls._failure_count
            )
            session.add(dlq_entry)
            session.commit()
            logger.info(f"Persisted DLQ Entry {dlq_entry.dlq_id}")
            
            # TODO: Kill functionality for the job? 
            # The caller handles the flow termination ideally.
            
        except Exception as e:
            logger.critical(f"FATAL: FAILED TO WRIT TO DLQ! {e}")
            session.rollback()
        finally:
            session.close()
