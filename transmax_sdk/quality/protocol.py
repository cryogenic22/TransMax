"""Quality gate protocols: contracts for quality checking components."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from transmax_sdk.types import QualityDefect


@runtime_checkable
class QualityCheckPlugin(Protocol):
    """A single composable quality check."""

    @property
    def name(self) -> str:
        """Unique check name (e.g., 'numeric', 'units', 'negation')."""
        ...

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        """Run this check and return any defects found."""
        ...


@runtime_checkable
class QualityGateProtocol(Protocol):
    """Full quality gate that runs multiple checks and produces a verdict."""

    def check_segment(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        """Run all quality checks on a segment."""
        ...

    def evaluate_verdict(self, defects: List[QualityDefect]) -> Dict[str, Any]:
        """Determine PASS/REVIEW_REQUIRED/BLOCKED from defects."""
        ...


@runtime_checkable
class ConfidenceScorerProtocol(Protocol):
    """Scores translation confidence based on defects and signals."""

    def calculate_score(
        self,
        defects: List[Dict[str, Any]],
        semantic_drift_score: float = 0.0,
        source_text: str = "",
        process_flags: Optional[Dict[str, bool]] = None,
    ) -> Any:
        """Calculate confidence score."""
        ...
