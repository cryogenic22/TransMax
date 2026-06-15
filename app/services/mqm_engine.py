"""
MQM-2.0 quality engine — the pure calculator and the sole pass/fail authority
(TMX-MQM-3; LangOps Platform Vision §5.5).

This is the platform's measurement instrument. It converts a list of span-level
MQM annotations (``app/core/mqm_annotation.py``) plus a versioned content-type
metric profile (``app/core/metric_profiles/``) into a reproducible score and a
pass/fail verdict. It is **pure**: no LLM calls, no DB, no clock, no randomness —
same annotations + same profile version + same EWC ⇒ identical output, always.
That purity is what makes the score auditable and the verdict trustworthy.

Separation of concerns (review conditions baked in):
  * **The engine is the SOLE authority on the quality verdict.** It derives
    Critical auto-fail itself from ``severity == CRITICAL AND
    profile.critical_auto_fail`` and IGNORES each annotation's non-authoritative
    ``is_auto_fail`` field — a producer cannot mark its own homework (cond. 3).
  * **The engine is pure to the QUALITY verdict only.** Short-document
    uncertainty is reported as a SEPARATE ``insufficient_sample`` flag (+ a
    confidence interval); it is NOT folded into ``passed``. Per §5.6 an
    insufficient sample is a *route-to-human* signal, owned by the risk-tier /
    routing layer — not a quality FAIL (cond. 2).
  * **Ships in shadow.** This module is additive; the legacy
    ``ConfidenceService`` is untouched. ``shadow_compare_legacy`` runs both over
    the same inputs so the distributions can be diffed before any cutover
    (cond. 4 — TMX-MQM-5).

Scoring model (exact, §5.5):
    ETPT_i = ETW_i × Σ_severity ( count_{i,sev} × SPM_sev )
    APT    = Σ_i ETPT_i
    PWPT   = APT / EWC
    NPT    = PWPT × 1000
    RQS    = 100 × (1 − APT/EWC)            # Raw Quality Score (cross-profile)
    SF     = (100 − PT) / APP               # Scaling Factor
    CQS    = 100 − (NPT × SF)               # Calibrated Quality Score (within-profile)
    PASS  iff  CQS ≥ PT  AND  CriticalErrorCount == 0 (when profile auto-fails)
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.defect_taxonomy import (
    SEVERITY_PENALTY_MULTIPLIER,
    DefectSeverity,
    MqmDimension,
)
from app.core.metric_profiles import MetricProfile
from app.core.mqm_annotation import MqmAnnotation

# --- SQC (Statistical Quality Control) for short documents (§5.6) ------------
# The MQM score of a short document is unstable: one error swings it wildly. For
# documents below the profile's sample-size floor we attach a confidence
# interval and set ``insufficient_sample`` so the routing layer can force human
# review. The interval below is a TRANSPARENT STARTING HEURISTIC — the margin
# shrinks as 1/sqrt(EWC) — and is an explicit open calibration item (vision
# §8.3): calibrate against real per-content-type length distributions before
# go-live. It must never be presented as a statistically rigorous CI yet.
SQC_MARGIN_SCALE = 100.0
SQC_MAX_MARGIN = 50.0


@dataclass(frozen=True)
class MqmScore:
    """The reproducible output of the MQM engine for one scored unit."""

    profile_id: str
    profile_version: str
    ewc: int

    apt: float                       # Absolute Penalty Total
    pwpt: float                      # Per-Word Penalty Total
    npt: float                       # Normed Penalty Total (per 1,000 words)
    rqs: float                       # Raw Quality Score (comparable across profiles)
    cqs: float                       # Calibrated Quality Score (interpretable within profile)

    passed: bool                     # PURE quality verdict (CQS ≥ PT and no auto-fail)
    critical_auto_fail: bool         # engine-derived; non-overridable
    critical_count: int
    deciding_reason: str

    # Short-document signal — SEPARATE from the quality verdict (routing owns it)
    insufficient_sample: bool = False
    confidence_interval: Optional[Tuple[float, float]] = None

    evaluation_mode: str = "full"
    etpt_by_dimension: Dict[str, float] = field(default_factory=dict)
    severity_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # tuple → list for JSON/audit friendliness
        if self.confidence_interval is not None:
            d["confidence_interval"] = list(self.confidence_interval)
        return d


def _sqc_interval(cqs: float, ewc: int) -> Tuple[float, float]:
    """Heuristic confidence interval on the CQS for a short sample (§5.6/§8.3).

    Starting heuristic only — margin = min(SCALE/sqrt(EWC), MAX), clamped to
    [0, 100]. Replace with a calibrated interval before go-live.
    """
    margin = min(SQC_MARGIN_SCALE / math.sqrt(max(ewc, 1)), SQC_MAX_MARGIN)
    low = round(max(0.0, cqs - margin), 1)
    high = round(min(100.0, cqs + margin), 1)
    return (low, high)


def score(
    annotations: Sequence[MqmAnnotation],
    profile: MetricProfile,
    ewc: int,
) -> MqmScore:
    """Score an annotation set against a metric profile. Pure + deterministic.

    Args:
        annotations: span-level MQM annotations (from gates, judge, or human).
        profile: a versioned content-type metric profile.
        ewc: Evaluation Word Count — source words evaluated (>= 1).
    """
    # EWC guard — never divide by zero. A non-positive EWC is itself an
    # insufficient sample; clamp the math denominator but keep the real EWC.
    ewc_eff = max(int(ewc), 1)

    # ETPT_i = ETW_i × Σ_severity ( count × SPM )
    etpt: Dict[str, float] = {}
    severity_counts: Dict[str, int] = {}
    by_dimension: Dict[MqmDimension, List[MqmAnnotation]] = {}
    for ann in annotations:
        by_dimension.setdefault(ann.dimension, []).append(ann)
        sev = ann.severity.value if isinstance(ann.severity, DefectSeverity) else str(ann.severity)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    for dim, anns in by_dimension.items():
        sev_penalty = sum(SEVERITY_PENALTY_MULTIPLIER.get(a.severity, 0) for a in anns)
        etpt[dim.value] = profile.etw(dim) * sev_penalty

    apt = float(sum(etpt.values()))
    pwpt = apt / ewc_eff
    npt = pwpt * 1000.0
    rqs = 100.0 * (1.0 - pwpt)
    sf = (100.0 - profile.passing_threshold) / profile.acceptable_penalty_points
    cqs = 100.0 - (npt * sf)

    # Critical auto-fail is ENGINE-derived from severity (cond. 3) — the
    # annotation's is_auto_fail field is deliberately not consulted here.
    critical_count = sum(1 for a in annotations if a.severity is DefectSeverity.CRITICAL)
    critical_auto_fail = bool(profile.critical_auto_fail and critical_count > 0)

    meets_threshold = cqs >= profile.passing_threshold
    # PURE quality verdict — insufficient_sample is intentionally NOT a factor.
    passed = bool(meets_threshold and not critical_auto_fail)

    insufficient_sample = int(ewc) < profile.sample_size_floor
    confidence_interval = _sqc_interval(cqs, int(ewc)) if insufficient_sample else None

    if critical_auto_fail:
        reason = f"FAIL — {critical_count} Critical error(s); auto-fail (non-overridable)"
    elif not meets_threshold:
        reason = f"FAIL — CQS {round(cqs, 2)} < passing threshold {profile.passing_threshold}"
    else:
        reason = f"PASS — CQS {round(cqs, 2)} ≥ {profile.passing_threshold}"
    if insufficient_sample:
        reason += (
            f" · INSUFFICIENT SAMPLE (EWC {ewc} < floor {profile.sample_size_floor}); "
            "route to mandatory human review"
        )

    return MqmScore(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        ewc=int(ewc),
        apt=round(apt, 4),
        pwpt=round(pwpt, 6),
        npt=round(npt, 4),
        rqs=round(rqs, 2),
        cqs=round(cqs, 2),
        passed=passed,
        critical_auto_fail=critical_auto_fail,
        critical_count=critical_count,
        deciding_reason=reason,
        insufficient_sample=insufficient_sample,
        confidence_interval=confidence_interval,
        evaluation_mode=profile.evaluation,
        etpt_by_dimension={k: round(v, 4) for k, v in etpt.items()},
        severity_counts=severity_counts,
    )


def score_from_violations(
    violations: Sequence[Dict[str, Any]],
    profile: MetricProfile,
    ewc: int,
) -> MqmScore:
    """Adapter: score legacy deterministic-gate violation dicts.

    Converts each ``{category, severity, message, segment_id}`` violation into an
    ``MqmAnnotation`` (reusing ``MqmAnnotation.from_violation``) and scores it.
    This is the reconciliation bridge — the gates do not need re-authoring.
    """
    annotations = [MqmAnnotation.from_violation(v) for v in violations]
    return score(annotations, profile, ewc)


def shadow_compare_legacy(
    violations: Sequence[Dict[str, Any]],
    profile: MetricProfile,
    ewc: int,
    *,
    semantic_drift_score: float = 0.0,
    source_text: str = "",
    source_language: str = "en",
    target_language: str = "en",
) -> Dict[str, Any]:
    """Run the legacy ``ConfidenceService`` AND the MQM engine over the same
    inputs and return a diff, for SHADOW validation before any cutover (cond. 4).

    The legacy scorer remains the source of truth in production until the
    distributions have been diffed and signed off (TMX-MQM-5). This helper does
    not change any behaviour; it is an offline comparison tool.
    """
    # Lazy import keeps the engine core free of the legacy scorer dependency.
    from app.services.confidence_service import ConfidenceService

    legacy = ConfidenceService.calculate_score(
        list(violations),
        semantic_drift_score=semantic_drift_score,
        source_text=source_text,
        source_language=source_language,
        target_language=target_language,
    )
    mqm = score_from_violations(violations, profile, ewc)
    return {
        "legacy_final_score": legacy.final_score,
        "legacy_status": legacy.status,
        "legacy_band": legacy.band,
        "mqm_cqs": mqm.cqs,
        "mqm_rqs": mqm.rqs,
        "mqm_passed": mqm.passed,
        "mqm_critical_auto_fail": mqm.critical_auto_fail,
        "mqm_insufficient_sample": mqm.insufficient_sample,
        "delta_cqs_minus_legacy": round(mqm.cqs - legacy.final_score, 2),
        "profile": f"{profile.profile_id}@{profile.version}",
        "ewc": int(ewc),
    }
