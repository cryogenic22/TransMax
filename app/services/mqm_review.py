"""
MQM critique-loop primitives (TMX-MQM-6): ensemble aggregation + the
conservation constraint. Both are PURE and deterministic — they are the
backstops that make the critique loop honour *no vacuous green* (ensemble
disagreement escalates instead of averaging away) and *conservation before
correctness* (the reviser may not touch unflagged text).

Wired into the judge/reviser in a later loop; shipped pure + tested first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation

# Risk-averse ordering: a span's merged severity is the MOST severe any judge
# assigned (never an average — averaging disagreement manufactures vacuous green).
_SEVERITY_RANK: Dict[DefectSeverity, int] = {
    DefectSeverity.NEUTRAL: 0,
    DefectSeverity.MINOR: 1,
    DefectSeverity.MAJOR: 2,
    DefectSeverity.CRITICAL: 3,
}


def _span_key(a: MqmAnnotation) -> Tuple:
    """Identity of the 'same span' across judges: segment + dimension + the
    target text it points at (falling back to source/subtype/explanation)."""
    anchor = (
        (a.target_span.text if a.target_span else None)
        or (a.source_span.text if a.source_span else None)
        or a.subtype
        or (a.explanation or "")[:40]
    )
    dim = a.dimension.value if isinstance(a.dimension, MqmDimension) else str(a.dimension)
    return (a.segment_id, dim, anchor)


@dataclass
class EnsembleResult:
    merged: List[MqmAnnotation]
    disagreements: List[dict] = field(default_factory=list)
    escalate: bool = False


def aggregate_ensemble(
    annotation_sets: Sequence[Sequence[MqmAnnotation]],
    *,
    min_judges_for_disagreement: int = 2,
) -> EnsembleResult:
    """Merge multiple judges' annotations: take the MOST SEVERE per span, and
    flag disagreement (a span not all judges flagged, or where they assigned
    different severities) as an ESCALATION signal rather than averaging it away
    (§6.4)."""
    num_judges = len(annotation_sets)
    groups: Dict[Tuple, List[Tuple[int, MqmAnnotation]]] = {}
    for idx, anns in enumerate(annotation_sets):
        for a in anns:
            groups.setdefault(_span_key(a), []).append((idx, a))

    merged: List[MqmAnnotation] = []
    disagreements: List[dict] = []
    for key, items in groups.items():
        most = max(items, key=lambda ia: _SEVERITY_RANK.get(ia[1].severity, 0))[1]
        merged.append(most)
        if num_judges >= min_judges_for_disagreement:
            judges_flagging = {idx for idx, _ in items}
            severities = {ia[1].severity for ia in items}
            if len(judges_flagging) < num_judges or len(severities) > 1:
                disagreements.append({
                    "span": key,
                    "severities": sorted(s.value for s in severities),
                    "judges_flagging": len(judges_flagging),
                    "num_judges": num_judges,
                })
    return EnsembleResult(merged=merged, disagreements=disagreements, escalate=bool(disagreements))


@dataclass
class ConservationResult:
    accepted: bool
    out_of_scope_chunks: List[str] = field(default_factory=list)
    reason: str = ""


def _unflagged_chunks(text: str, flagged_spans: Sequence[Tuple[int, int]]) -> List[str]:
    spans = sorted((max(0, s), min(len(text), e)) for s, e in flagged_spans if e > s)
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    chunks: List[str] = []
    cursor = 0
    for s, e in merged:
        if s > cursor:
            chunks.append(text[cursor:s])
        cursor = e
    if cursor < len(text):
        chunks.append(text[cursor:])
    return chunks


def enforce_conservation(
    original: str,
    revised: str,
    flagged_spans: Sequence[Tuple[int, int]],
) -> ConservationResult:
    """Reject a revision that changed text OUTSIDE the flagged spans (§6.3 /
    principle 3). Heuristic: every non-flagged chunk of the original must still
    appear in the revised text; a missing chunk means the reviser edited
    out-of-scope content, so the revision is rejected and must be re-done."""
    chunks = [c for c in _unflagged_chunks(original, flagged_spans) if c.strip()]
    missing = [c for c in chunks if c.strip() not in revised]
    accepted = not missing
    reason = "conserved" if accepted else f"{len(missing)} unflagged chunk(s) altered out of scope"
    return ConservationResult(accepted=accepted, out_of_scope_chunks=missing, reason=reason)
