"""Pipeline protocol: contract for translation pipeline implementations."""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable

from transmax_sdk.types import TranslationRequest, TranslationResult


@runtime_checkable
class TranslationPipelineProtocol(Protocol):
    """Interface for translation pipeline implementations."""

    async def execute(self, request: TranslationRequest) -> TranslationResult:
        """Execute the translation pipeline."""
        ...


@runtime_checkable
class PipelineStageProtocol(Protocol):
    """Interface for individual pipeline stages."""

    @property
    def name(self) -> str:
        """Stage name."""
        ...

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process the state and return updated state."""
        ...
