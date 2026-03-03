"""LLM call optimization: batching, TM bypass, model routing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.telemetry.cost import CostTracker
from transmax_sdk.types import TranslationSegment


class LLMOptimizer:
    """Optimizes LLM calls by batching, TM bypass, and model selection."""

    def __init__(
        self,
        batch_size: int = 5,
        small_model: str = "gpt-4o-mini",
        large_model: str = "gpt-4o",
        complexity_threshold: int = 200,
        cost_tracker: Optional[CostTracker] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._batch_size = batch_size
        self._small_model = small_model
        self._large_model = large_model
        self._complexity_threshold = complexity_threshold
        self._cost_tracker = cost_tracker or CostTracker()
        self._telemetry = telemetry or NoOpTelemetry()

    def create_batches(self, segments: List[TranslationSegment]) -> List[List[TranslationSegment]]:
        """Split segments into batches of configured size."""
        batches = []
        for i in range(0, len(segments), self._batch_size):
            batches.append(segments[i : i + self._batch_size])
        return batches

    def select_model(self, segment: TranslationSegment) -> str:
        """Route to optimal model based on segment complexity."""
        text = segment.source_text
        # Simple heuristic: long text or special characters -> large model
        if len(text) > self._complexity_threshold:
            return self._large_model
        if any(c in text for c in ["$", "\\", "```", "|"]):
            return self._large_model
        return self._small_model

    def estimate_batch_cost(self, segments: List[TranslationSegment]) -> float:
        """Estimate total cost for translating a batch of segments."""
        total = 0.0
        for seg in segments:
            model = self.select_model(seg)
            total += self._cost_tracker.estimate_cost(seg.source_text, model)
        return total

    def separate_tm_matches(
        self,
        segments: List[TranslationSegment],
        tm_results: Dict[str, Dict[str, Any]],
    ) -> tuple[List[TranslationSegment], List[tuple[TranslationSegment, Dict[str, Any]]]]:
        """Separate segments into those needing LLM and those with TM matches."""
        need_llm = []
        tm_resolved = []
        for seg in segments:
            match = tm_results.get(seg.segment_id)
            if match and match.get("type") == "exact":
                tm_resolved.append((seg, match))
            else:
                need_llm.append(seg)
        return need_llm, tm_resolved
