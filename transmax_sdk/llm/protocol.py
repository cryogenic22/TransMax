"""LLM provider protocol: contract for LLM implementations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from transmax_sdk.types import CostRecord


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Interface for LLM providers (OpenAI, Anthropic, etc.)."""

    @property
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        ...

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a completion request. Returns {content, usage, model}."""
        ...
