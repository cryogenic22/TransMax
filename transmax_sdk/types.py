"""Shared data types for the TransMax SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Regulatory risk classification for translation defects."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class TranslationStatus(str, Enum):
    """Status of a translation result."""
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class RouteStrategy(str, Enum):
    """How a language pair is routed for translation."""
    DIRECT = "DIRECT"
    PIVOT_ENGLISH = "PIVOT_ENGLISH"


@dataclass
class RouteStep:
    """A single step in a translation route plan."""

    source_lang: str
    target_lang: str
    provider_name: str
    model: str
    confidence: float
    estimated_cost: float = 0.0


@dataclass
class RoutePlan:
    """Complete plan for translating a language pair."""

    strategy: RouteStrategy
    steps: List["RouteStep"] = field(default_factory=list)


@dataclass
class QualityDefect:
    """A single quality defect found during translation checking."""
    category: str
    severity: Severity
    message: str
    segment_id: Optional[str] = None
    source_text: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "segment_id": self.segment_id,
            "source_text": self.source_text,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityDefect":
        return cls(
            category=data["category"],
            severity=Severity(data["severity"]),
            message=data["message"],
            segment_id=data.get("segment_id"),
            source_text=data.get("source_text"),
            suggestion=data.get("suggestion"),
        )


@dataclass
class TranslationSegment:
    """A single segment of text to translate."""
    segment_id: str
    source_text: str
    order_index: int = 0
    context_before: str = ""
    context_after: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationRequest:
    """Request to translate text or segments."""
    segments: List[TranslationSegment]
    source_lang: str = "auto"
    target_lang: str = "en"
    domain: str = "pharma"
    glossary_id: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SegmentResult:
    """Result of translating a single segment."""
    segment_id: str
    source_text: str
    translated_text: str
    confidence: float = 0.0
    defects: List[QualityDefect] = field(default_factory=list)
    back_translation: Optional[str] = None
    drift_score: float = 0.0
    translation_source: str = "MT"  # MT, TM_EXACT, TM_FUZZY, HUMAN
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "confidence": self.confidence,
            "defects": [d.to_dict() for d in self.defects],
            "back_translation": self.back_translation,
            "drift_score": self.drift_score,
            "translation_source": self.translation_source,
            "cost_usd": self.cost_usd,
        }


@dataclass
class TranslationResult:
    """Complete result of a translation request."""
    segments: List[SegmentResult]
    source_lang: str
    target_lang: str
    route_strategy: RouteStrategy = RouteStrategy.DIRECT
    status: TranslationStatus = TranslationStatus.PASS
    audit_id: Optional[str] = None
    total_cost_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def translated_text(self) -> str:
        """Convenience: join all segment translations."""
        return "\n".join(s.translated_text for s in self.segments)

    @property
    def confidence(self) -> float:
        """Average confidence across segments."""
        if not self.segments:
            return 0.0
        return sum(s.confidence for s in self.segments) / len(self.segments)

    @property
    def defects(self) -> List[QualityDefect]:
        """All defects across all segments."""
        result = []
        for s in self.segments:
            result.extend(s.defects)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "route_strategy": self.route_strategy.value,
            "status": self.status.value,
            "audit_id": self.audit_id,
            "total_cost_usd": self.total_cost_usd,
            "translated_text": self.translated_text,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""
    lang_code: str
    confidence: float
    lang_name: str = ""


@dataclass
class CostRecord:
    """Token usage and cost for an LLM call."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_id: Optional[str] = None
