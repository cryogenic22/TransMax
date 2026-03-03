"""Document management protocol."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SegmentationStrategyProtocol(Protocol):
    """Interface for text segmentation strategies."""

    @property
    def name(self) -> str: ...

    def segment(self, text: str) -> List[str]:
        """Split text into segments."""
        ...


@runtime_checkable
class DocumentManagerProtocol(Protocol):
    """Interface for document management."""

    def segment_text(self, text: str, strategy: str = "sentence") -> List[str]:
        """Segment text using the specified strategy."""
        ...
