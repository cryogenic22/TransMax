import time
from typing import Dict, Any
import logging

from app.core.model_pricing import cost_for

logger = logging.getLogger(__name__)

class ObservabilityService:
    """
    Service to track operational metrics: Latency, Cost (Tokens), and Quality Violations.
    """
    
    # Simple in-memory metrics for now (Prometheus would be better for prod)
    _metrics = {
        "total_requests": 0,
        "total_cost_usd": 0.0,
        "total_latency_ms": 0.0,
        "violations_count": 0
    }
    
    @staticmethod
    def start_timer() -> float:
        return time.time()
        
    @staticmethod
    def end_timer(start_time: float) -> float:
        return (time.time() - start_time) * 1000 # ms
        
    @classmethod
    def track_request(cls, duration_ms: float, cost_usd: float = 0.0, violations: int = 0):
        cls._metrics["total_requests"] += 1
        cls._metrics["total_latency_ms"] += duration_ms
        cls._metrics["total_cost_usd"] += cost_usd
        cls._metrics["violations_count"] += violations
        
        logger.info(f"REQ_METRIC | Duration: {duration_ms:.2f}ms | Cost: ${cost_usd:.4f} | Violations: {violations}")

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost via the canonical pricing registry (TMX-PRICING-1).

        Pricing lives in `app/core/model_pricing.py` — the single source of
        truth. Unknown models raise `UnknownModelError` rather than silently
        defaulting to gpt-4o's rate (the old behaviour), so a recorded cost is
        always for the model that actually ran (addendum A3).
        """
        return cost_for(model, input_tokens, output_tokens)

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        return cls._metrics.copy()
