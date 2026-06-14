"""
Judge-reliability metrics (TMX-MQM-EVAL; E13.S2 / §6.10).

The judge is a model and must be measured like one. This is the pure core of
the "no vacuous green" CI gate: a judge that stops catching planted Critical
defects fails the build. Phase 2 wires these metrics into a release-blocking
gate over a growing gold set; this loop ships the deterministic computation +
its tests so the metric exists before the gate.

Pure — no LLM, no DB. The judge's annotations are the input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Set

from app.core.defect_taxonomy import DefectSeverity
from app.core.mqm_annotation import MqmAnnotation


@dataclass(frozen=True)
class JudgeReliability:
    planted_total: int        # planted Critical defects
    planted_caught: int       # planted Criticals the judge flagged Critical
    recall: float             # caught / planted (the headline gate metric)
    false_positive_segments: int  # judge-Critical on a non-planted segment
    precision: float          # caught / (caught + false positives)


def _critical_segments(annotations: Iterable[MqmAnnotation]) -> Set[str]:
    return {
        a.segment_id
        for a in annotations
        if a.segment_id and a.severity is DefectSeverity.CRITICAL
    }


def compute_judge_reliability(
    planted_critical_segment_ids: Sequence[str],
    judge_annotations: Sequence[MqmAnnotation],
) -> JudgeReliability:
    """Recall over planted Critical defects + precision of the judge's Criticals.

    recall = (planted Criticals the judge caught) / (planted Criticals).
    A judge-Critical on a segment that was NOT planted is a false positive
    (over-flagging erodes reviewer trust); precision tracks that.
    """
    planted: Set[str] = {s for s in planted_critical_segment_ids if s}
    judge_critical = _critical_segments(judge_annotations)

    caught = planted & judge_critical
    false_positives = judge_critical - planted

    recall = len(caught) / len(planted) if planted else 1.0
    denom = len(caught) + len(false_positives)
    precision = len(caught) / denom if denom else 1.0

    return JudgeReliability(
        planted_total=len(planted),
        planted_caught=len(caught),
        recall=round(recall, 3),
        false_positive_segments=len(false_positives),
        precision=round(precision, 3),
    )
