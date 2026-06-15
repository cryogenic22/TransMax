"""
MQM annotation object — the shared currency of the quality engine (TMX-MQM-1).

This is the §5.7 canonical annotation defined in the LangOps Platform Vision.
Every quality finding — whether produced by a deterministic gate, the
independent critique/judge agent (TMX-MQM-4), or a human reviewer — is
expressed as one of these objects. The pure MQM engine (TMX-MQM-3,
``app/services/mqm_engine.py``) consumes a list of them plus a content-type
metric profile and produces a reproducible score.

Design notes
------------
* **Reuse, not replacement.** Severity and dimension come from the existing
  ``app/core/defect_taxonomy.py`` (``DefectSeverity`` gained a NEUTRAL tier;
  ``MqmDimension`` is the seven MQM-Core dimensions). A legacy ``Defect`` or a
  deterministic-gate violation dict converts into an annotation via the
  ``from_defect`` / ``from_violation`` constructors — the gates do not need to
  be re-authored.
* **Lenient construction.** Only ``dimension`` and ``severity`` are required so
  the engine can score cheaply. The full provenance fields (``rule_ref``,
  ``evidence_refs``, ``judge_id``, ``model_version`` …) make an annotation
  *citable*, *reproducible* and *auditable* and are filled by the judge and at
  human review; they default to empty for engine-only paths.
* **Not frozen.** ``human_decision`` is filled at review time (confirm /
  override / amend), which is the gold signal that later feeds calibration and
  Black-Book capture.

Persistence (the ``mqm_annotations`` table + Alembic revision) is a deliberate
follow-up (TMX-MQM-1a): the engine and judge need only the in-memory object, so
this loop ships zero schema risk.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.defect_taxonomy import (
    Defect,
    DefectSeverity,
    MqmDimension,
    dimension_for_category,
)


class Span(BaseModel):
    """A character span within a source or target segment."""

    text: str = ""
    start: Optional[int] = None
    end: Optional[int] = None


ProducedBy = Literal["deterministic-gate", "critique-agent", "human"]
HumanDecision = Literal["confirm", "override", "amend"]


class MqmAnnotation(BaseModel):
    """A single span-level MQM error annotation (§5.7).

    ``dimension`` and ``severity`` are the only fields the scoring engine reads;
    everything else is provenance / reviewer-facing evidence.
    """

    annotation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: Optional[str] = None
    segment_id: Optional[str] = None
    locale: Optional[str] = None
    content_type: Optional[str] = None
    # DEAD — never assigned/read; the live tier signal is the metric profile
    # (ContentRiskTier → profile via resolution.py, TMX-SSOT-TIER). Removal +
    # the matching mqm_engine docstring fix are TMX-SSOT-TIER step 4 (one-way).
    risk_tier: Optional[int] = None

    source_span: Optional[Span] = None
    target_span: Optional[Span] = None

    # --- the scoring inputs (required) ---
    dimension: MqmDimension
    subtype: Optional[str] = None
    severity: DefectSeverity
    # NON-AUTHORITATIVE denormalised convenience (TMX-MQM-1, review cond. 3).
    # The MQM ENGINE is the sole authority on auto-fail: it derives it from
    # `severity == CRITICAL AND profile.critical_auto_fail` and IGNORES this
    # field for the pass/fail verdict. We keep the field (kept consistent with
    # severity by model_post_init below, so a producer cannot set it to lie) only
    # so the reviewer UI can chip a span without re-deriving. Never gate on it.
    is_auto_fail: bool = False

    # --- citable evidence (reviewer-facing) ---
    explanation: str = ""
    rule_ref: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None

    # --- provenance (reproducible / auditable) ---
    produced_by: ProducedBy = "deterministic-gate"
    judge_id: Optional[str] = None
    judge_confidence: Optional[float] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None

    # --- filled at human review (the gold signal) ---
    human_decision: Optional[HumanDecision] = None

    created_at: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        # A Critical annotation is, by definition, an auto-fail candidate. The
        # metric profile decides whether auto-fail is actually enforced; here we
        # just mark the intent so the engine and the reviewer UI agree.
        if self.severity is DefectSeverity.CRITICAL:
            object.__setattr__(self, "is_auto_fail", True)

    # ------------------------------------------------------------------ #
    # Reconciliation constructors — turn existing shapes into annotations #
    # ------------------------------------------------------------------ #
    @classmethod
    def from_defect(cls, defect: Defect, **overrides: Any) -> "MqmAnnotation":
        """Build an annotation from the existing ``Defect`` dataclass."""
        return cls(
            segment_id=defect.segment_id,
            dimension=dimension_for_category(defect.category),
            subtype=getattr(defect.category, "value", str(defect.category)),
            severity=defect.severity,
            explanation=defect.message,
            suggested_fix=defect.suggestion,
            source_span=Span(text=defect.source_text or ""),
            produced_by="deterministic-gate",
            **overrides,
        )

    @classmethod
    def from_violation(cls, violation: Dict[str, Any], **overrides: Any) -> "MqmAnnotation":
        """Build an annotation from a deterministic-gate violation dict.

        The gate emits ``{category, severity, message, segment_id}`` (see
        ``app/services/quality_gate.py``). Severity may be a ``DefectSeverity``,
        its string value, or lower-case legacy text — all are normalised.
        """
        raw_sev = violation.get("severity", DefectSeverity.MAJOR)
        severity = _coerce_severity(raw_sev)
        category = violation.get("category", "")
        return cls(
            segment_id=violation.get("segment_id"),
            dimension=dimension_for_category(category),
            subtype=str(getattr(category, "value", category)) or None,
            severity=severity,
            explanation=str(violation.get("message", "")),
            suggested_fix=violation.get("suggestion"),
            produced_by="deterministic-gate",
            **overrides,
        )


def _coerce_severity(raw: Any) -> DefectSeverity:
    """Normalise a severity that may be an enum, a value string, or legacy
    lower-case text into a ``DefectSeverity`` (defaulting to MAJOR)."""
    if isinstance(raw, DefectSeverity):
        return raw
    try:
        return DefectSeverity(str(getattr(raw, "value", raw)).upper())
    except ValueError:
        return DefectSeverity.MAJOR
