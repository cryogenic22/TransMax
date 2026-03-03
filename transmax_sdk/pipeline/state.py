"""Pipeline state dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transmax_sdk.types import TranslationSegment, QualityDefect


@dataclass
class PipelineState:
    """State passed through pipeline stages."""
    # Input
    segments: List[TranslationSegment]
    source_lang: str
    target_lang: str
    domain: str = "pharma"
    glossary_id: Optional[str] = None

    # Processing
    constraint_pack: Dict[str, Any] = field(default_factory=dict)
    translations: Dict[str, str] = field(default_factory=dict)  # segment_id -> translated_text
    defects: Dict[str, List[QualityDefect]] = field(default_factory=dict)  # segment_id -> defects
    back_translations: Dict[str, str] = field(default_factory=dict)
    drift_scores: Dict[str, float] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    translation_sources: Dict[str, str] = field(default_factory=dict)  # segment_id -> MT/TM_EXACT/etc.

    # Control
    iteration_count: int = 0
    max_iterations: int = 3
    final_decision: Optional[str] = None
    error: Optional[str] = None

    # Audit
    audit_id: Optional[str] = None
    job_id: Optional[str] = None

    # Cost
    total_cost_usd: float = 0.0
