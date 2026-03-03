"""Default document manager for headless SDK use."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.documents.strategies import (
    ParagraphStrategy,
    PageStrategy,
    SentenceStrategy,
)
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import TranslationSegment


# Strategy registry
_STRATEGIES = {
    "sentence": SentenceStrategy(),
    "paragraph": ParagraphStrategy(),
    "page": PageStrategy(),
}


class DefaultDocumentManager:
    """Manages document ingestion and segmentation.

    Works headless (no filesystem dependency for text input).
    """

    def __init__(self, telemetry: Optional[TelemetryProtocol] = None) -> None:
        self._telemetry = telemetry or NoOpTelemetry()

    def segment_text(self, text: str, strategy: str = "sentence") -> List[str]:
        """Segment text using the specified strategy."""
        strat = _STRATEGIES.get(strategy)
        if strat is None:
            raise ValueError(f"Unknown strategy: {strategy}. Options: {list(_STRATEGIES.keys())}")
        return strat.segment(text)

    def text_to_segments(
        self, text: str, strategy: str = "sentence", doc_id: str = "doc_0"
    ) -> List[TranslationSegment]:
        """Convert raw text into TranslationSegment objects."""
        raw_segments = self.segment_text(text, strategy)
        return [
            TranslationSegment(
                segment_id=f"{doc_id}_seg_{i}",
                source_text=seg,
                order_index=i,
            )
            for i, seg in enumerate(raw_segments)
        ]

    def register_strategy(self, name: str, strategy: Any) -> None:
        """Register a custom segmentation strategy."""
        _STRATEGIES[name] = strategy
