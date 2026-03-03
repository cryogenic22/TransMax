"""Cost tracking with tiktoken token counting."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transmax_sdk.types import CostRecord


class CostTracker:
    """Tracks LLM token usage and cost across requests.

    Thread-safe. Can estimate cost before making a call (pre-flight)
    or record actual usage after a call.
    """

    # Default cost per 1K tokens (can be overridden via config)
    DEFAULT_COSTS_INPUT = {
        "gpt-4o": 0.0025,
        "gpt-4o-mini": 0.00015,
        "gpt-4-turbo-preview": 0.01,
    }
    DEFAULT_COSTS_OUTPUT = {
        "gpt-4o": 0.01,
        "gpt-4o-mini": 0.0006,
        "gpt-4-turbo-preview": 0.03,
    }

    def __init__(
        self,
        cost_per_1k_input: Optional[Dict[str, float]] = None,
        cost_per_1k_output: Optional[Dict[str, float]] = None,
    ) -> None:
        self._cost_input = cost_per_1k_input or self.DEFAULT_COSTS_INPUT
        self._cost_output = cost_per_1k_output or self.DEFAULT_COSTS_OUTPUT
        self._records: List[CostRecord] = []
        self._lock = threading.Lock()
        self._encoder = None  # lazy-loaded tiktoken encoder

    def _get_encoder(self, model: str):
        """Lazy-load tiktoken encoder for the given model."""
        if self._encoder is None:
            try:
                import tiktoken
                try:
                    self._encoder = tiktoken.encoding_for_model(model)
                except KeyError:
                    self._encoder = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                return None
        return self._encoder

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """Count tokens in text using tiktoken."""
        encoder = self._get_encoder(model)
        if encoder is None:
            # Fallback: rough estimate of 4 chars per token
            return len(text) // 4
        return len(encoder.encode(text))

    def estimate_cost(self, text: str, model: str = "gpt-4o", direction: str = "input") -> float:
        """Estimate cost for a text before making an API call."""
        tokens = self.count_tokens(text, model)
        if direction == "input":
            rate = self._cost_input.get(model, 0.01)
        else:
            rate = self._cost_output.get(model, 0.03)
        return (tokens / 1000) * rate

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_id: Optional[str] = None,
    ) -> CostRecord:
        """Record actual token usage from an API call."""
        input_cost = (input_tokens / 1000) * self._cost_input.get(model, 0.01)
        output_cost = (output_tokens / 1000) * self._cost_output.get(model, 0.03)
        total = input_cost + output_cost

        rec = CostRecord(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total,
            request_id=request_id,
        )
        with self._lock:
            self._records.append(rec)
        return rec

    @property
    def total_cost(self) -> float:
        with self._lock:
            return sum(r.cost_usd for r in self._records)

    @property
    def total_input_tokens(self) -> int:
        with self._lock:
            return sum(r.input_tokens for r in self._records)

    @property
    def total_output_tokens(self) -> int:
        with self._lock:
            return sum(r.output_tokens for r in self._records)

    @property
    def records(self) -> List[CostRecord]:
        with self._lock:
            return list(self._records)

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
