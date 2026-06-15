"""
Judge-reliability metrics (TMX-MQM-EVAL; E13.S2 / §6.10).

The judge is a model and must be measured like one. This is the pure core of
the "no vacuous green" CI gate: a judge that stops catching planted Critical
defects fails the build. Phase 2 wires these metrics into a release-blocking
gate over a growing gold set; this loop ships the deterministic computation +
its tests so the metric exists before the gate.

The metrics are pure — no LLM, no DB; the judge's annotations are the input.
The one IO concession is ``load_judge_gold`` (the canonical gold-set loader,
shared by the pytest cases and the CI gate so the JSONL parsing lives in ONE
place — TMX-MQM-EVAL-CI).
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from app.core.defect_taxonomy import DefectSeverity
from app.core.mqm_annotation import MqmAnnotation

# The single canonical judge gold set (planted-defect cases). Both the pytest
# suite and the release gate load THROUGH ``load_judge_gold`` — no forked parser.
DEFAULT_GOLD_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "tests" / "evals" / "judge" / "planted_critical.jsonl"
)


def load_judge_gold(path: Optional[pathlib.Path | str] = None) -> List[Dict[str, Any]]:
    """Load the judge gold set (one JSON object per non-blank line).

    Returns ``[]`` when the file is missing or empty — the integrity guard in
    the CI gate turns that into a hard failure (an empty gold set must never
    score a vacuously-green recall=1.0).
    """
    p = pathlib.Path(path) if path else DEFAULT_GOLD_PATH
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


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


# ── Inter-rater agreement (TMX-MQM-EVAL-KAPPA) ───────────────────────────────
# Recall/precision measure the judge against a planted gold; Cohen's kappa
# measures whether two raters AGREE — judge↔judge (ensemble consistency) now,
# judge↔human (calibration) once structured human MQM labels land (TMX-MQM-1a).
# Pure, deterministic, no LLM/DB. Honest about degeneracy: zero shared items
# yields kappa=None (NEVER a fabricated 0 or 1 — A3).

@dataclass(frozen=True)
class KappaResult:
    n_items: int                 # items BOTH raters labelled (the inner join)
    observed_agreement: float    # p_o
    expected_agreement: float    # p_e (agreement expected by chance)
    kappa: Optional[float]       # (p_o - p_e)/(1 - p_e); None when undefined
    categories: Tuple[str, ...]  # the label categories seen across both raters


def cohen_kappa(
    labels_a: Mapping[str, str],
    labels_b: Mapping[str, str],
) -> KappaResult:
    """Cohen's kappa between two raters over the items they BOTH labelled.

    Labels are opaque category strings (the caller builds them — e.g.
    "CRITICAL"/"OK" per segment). Only the inner join of keys is scored, so a
    rater that didn't see an item never counts as a (dis)agreement.

    Degenerate cases are explicit (A3): no shared items → kappa=None; a single
    category where both raters fully agree → kappa=1.0; a single category with
    any disagreement → kappa=0.0. No NaN/Infinity is ever produced.
    """
    keys = sorted(set(labels_a) & set(labels_b))
    n = len(keys)
    if n == 0:
        return KappaResult(0, 0.0, 0.0, None, ())

    categories = tuple(sorted({labels_a[k] for k in keys} | {labels_b[k] for k in keys}))
    agree = sum(1 for k in keys if labels_a[k] == labels_b[k])
    p_o = agree / n

    count_a = Counter(labels_a[k] for k in keys)
    count_b = Counter(labels_b[k] for k in keys)
    p_e = sum((count_a.get(c, 0) / n) * (count_b.get(c, 0) / n) for c in categories)

    if 1.0 - p_e == 0.0:
        # Both raters used one category for everything: agreement is trivial.
        kappa: float = 1.0 if p_o == 1.0 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    return KappaResult(
        n_items=n,
        observed_agreement=round(p_o, 3),
        expected_agreement=round(p_e, 3),
        kappa=round(kappa, 3),
        categories=categories,
    )


def binary_severity_label_map(
    segment_ids: Iterable[str],
    critical_segment_ids: Iterable[str],
) -> Dict[str, str]:
    """Build a complete ``{segment_id: "CRITICAL"|"OK"}`` map over a KNOWN
    segment universe, so an unflagged segment is an explicit "OK" rather than an
    absent key. Without this, a judge↔human kappa would inner-join only the
    flagged/overridden segments and be biased toward agreement."""
    critical = {s for s in critical_segment_ids if s}
    return {s: ("CRITICAL" if s in critical else "OK") for s in segment_ids if s}
