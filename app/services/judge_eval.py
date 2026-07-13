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
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from app.core.defect_taxonomy import DefectSeverity
from app.core.mqm_annotation import MqmAnnotation

# The single canonical judge gold set (planted-defect cases). Both the pytest
# suite and the release gate load THROUGH ``load_judge_gold`` — no forked parser.
DEFAULT_GOLD_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "tests"
    / "evals"
    / "judge"
    / "planted_critical.jsonl"
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
    return [
        json.loads(ln)
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


@dataclass(frozen=True)
class JudgeReliability:
    planted_total: int  # planted Critical defects
    planted_caught: int  # planted Criticals the judge flagged Critical
    recall: float  # caught / planted (the headline gate metric)
    false_positive_segments: int  # judge-Critical on a non-planted segment
    precision: float  # caught / (caught + false positives)


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
    n_items: int  # items BOTH raters labelled (the inner join)
    observed_agreement: float  # p_o
    expected_agreement: float  # p_e (agreement expected by chance)
    kappa: Optional[float]  # (p_o - p_e)/(1 - p_e); None when undefined
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

    categories = tuple(
        sorted({labels_a[k] for k in keys} | {labels_b[k] for k in keys})
    )
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


# ── Judge-reliability drift (TMX-MQM-EVAL-DRIFT; E13.S2 / §6.10) ──────────────
# EVAL-CI enforces an ABSOLUTE floor on recall/precision at a single point in
# time. That misses EROSION: a judge whose recall slides 0.95 → 0.80 is still
# above the floor but has measurably regressed. §6.10 asks for "control limits
# over a rolling window; a regression blocks release". This is that — a pure,
# one-sided control-limit detector over a window of REAL past judge runs.
#
# NOTE: this is judge-META-EVAL drift (the judge's reliability over time), wholly
# distinct from ``app/services/semantic_drift.py`` (back-translation MEANING
# drift of a single translation). Different concept; named explicitly to avoid
# confusion with TMX-DRIFT-GATE.

# The committed rolling-window baseline (beside the gold set; ``eval_results/``
# is transient/untracked so the baseline must NOT live there).
DEFAULT_DRIFT_BASELINE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "tests"
    / "evals"
    / "judge"
    / "drift_baseline.json"
)


@dataclass(frozen=True)
class MetricDriftFinding:
    metric: str
    current: float
    status: str  # "OK" | "DRIFT" | "INSUFFICIENT_HISTORY"
    n_history: int  # observations in the rolling window
    baseline_mean: Optional[float]  # None until >= min_history
    baseline_std: Optional[float]  # population std of the window
    lower_control_limit: Optional[float]  # mean - max(k*std, min_abs_drop)
    reason: str


def detect_metric_drift(
    series: Sequence[float],
    current: float,
    *,
    k: float = 3.0,
    min_history: int = 5,
    min_abs_drop: float = 0.05,
) -> MetricDriftFinding:
    """One-sided rolling-window drift detection for a single reliability metric.

    Drift fires iff the current value drops below the window mean by more than
    ``max(k*std, min_abs_drop)``:

    * ``k*std`` is the statistical-process-control margin — a genuinely noisy
      judge must drop a lot before we cry wolf.
    * ``min_abs_drop`` is a floor so that a perfectly stable window (std≈0) is
      not hair-triggered by trivial noise, AND a small-but-real erosion still
      fires even when std is tiny.

    One-sided by construction: an improvement (``current >= mean``) yields a
    non-positive drop and never reports DRIFT. Below ``min_history`` the result
    is ``INSUFFICIENT_HISTORY`` — we never fabricate a control limit from too
    few points (A3); the caller defers to the absolute EVAL-CI floor.
    """
    window = [float(x) for x in series]
    n = len(window)
    cur = float(current)
    if n < min_history:
        return MetricDriftFinding(
            metric="",
            current=round(cur, 4),
            status="INSUFFICIENT_HISTORY",
            n_history=n,
            baseline_mean=None,
            baseline_std=None,
            lower_control_limit=None,
            reason=f"only {n} observation(s); need >= {min_history} to set a control limit",
        )

    mean = statistics.fmean(window)
    std = statistics.pstdev(window)
    threshold = max(k * std, min_abs_drop)
    lcl = mean - threshold
    drop = mean - cur
    drifted = drop > threshold
    return MetricDriftFinding(
        metric="",
        current=round(cur, 4),
        status="DRIFT" if drifted else "OK",
        n_history=n,
        baseline_mean=round(mean, 4),
        baseline_std=round(std, 4),
        lower_control_limit=round(lcl, 4),
        reason=(
            f"current {cur:.4f} is {drop:.4f} below mean {mean:.4f}; "
            f"control limit {lcl:.4f} (max({k}*std={k*std:.4f}, min_abs_drop={min_abs_drop}))"
            + (" — REGRESSED" if drifted else " — within limit")
        ),
    )


def detect_judge_drift(
    current: Mapping[str, float],
    history: Sequence[Mapping[str, Any]],
    *,
    metrics: Sequence[str] = ("recall", "precision"),
    k: float = 3.0,
    min_history: int = 5,
    min_abs_drop: float = 0.05,
) -> Dict[str, MetricDriftFinding]:
    """Run :func:`detect_metric_drift` over each configured metric.

    Metric-agnostic: ``metrics`` defaults to ``recall``/``precision`` but accepts
    ``agreement`` (judge↔human κ) once that series exists (TMX-MQM-EVAL-KAPPA-JOIN)
    — no new math needed. A metric absent from ``current`` is skipped (not
    measured this run); ``None`` values in history are dropped honestly.
    """
    out: Dict[str, MetricDriftFinding] = {}
    for m in metrics:
        if m not in current or current[m] is None:
            continue
        series = [
            float(obs[m])
            for obs in history
            if isinstance(obs, Mapping) and obs.get(m) is not None
        ]
        finding = detect_metric_drift(
            series, current[m], k=k, min_history=min_history, min_abs_drop=min_abs_drop
        )
        # stamp the metric name (the single-metric detector is name-agnostic)
        out[m] = MetricDriftFinding(
            metric=m,
            current=finding.current,
            status=finding.status,
            n_history=finding.n_history,
            baseline_mean=finding.baseline_mean,
            baseline_std=finding.baseline_std,
            lower_control_limit=finding.lower_control_limit,
            reason=finding.reason,
        )
    return out


def load_drift_baseline(path: Optional[pathlib.Path | str] = None) -> Dict[str, Any]:
    """Load the rolling-window drift baseline.

    Missing file → an honest empty baseline (cold start). A malformed file is
    NOT swallowed — ``json.JSONDecodeError`` propagates so the gate turns it into
    a structured FAIL_INTEGRITY (mirrors ``load_judge_gold``).
    """
    p = pathlib.Path(path) if path else DEFAULT_DRIFT_BASELINE_PATH
    if not p.exists():
        return {"config": {}, "observations": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("config", {})
    data.setdefault("observations", [])
    return data
