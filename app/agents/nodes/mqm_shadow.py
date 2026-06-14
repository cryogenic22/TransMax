"""
MQM engine shadow integration (TMX-MQM-5, phase a).

Runs the pure MQM-2.0 engine (``app/services/mqm_engine.py``) ALONGSIDE the
legacy deterministic gate verdict and records a comparison. It changes NO
verdict — the legacy `evaluate_verdict` remains authoritative until the cutover
(TMX-MQM-5b). This exists to collect the distribution diff that review
condition 4 (ADR-0007) requires before flipping `mqm_engine_enabled`.

Kept out of `graph.py` so the gate node stays thin (engine first, surface
second). The function is defensive: any failure is logged and swallowed — the
shadow must never affect the live pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.metric_profiles import MetricProfile
from app.services.mqm_engine import score_from_violations

logger = logging.getLogger(__name__)


def resolve_metric_profile(state: Dict[str, Any]) -> MetricProfile:
    """Resolve the content-type metric profile for a job (TMX-MQM-5c).

    Maps the document's content metadata (content_type / doc_type / legacy
    archetype, stashed into state by ``validate_request``) to a metric profile,
    reconciling the two legacy profile systems onto the registry. Falls back to
    the configured default when no hint is present.
    """
    from app.core.metric_profiles.resolution import resolve_metric_profile as _resolve
    return _resolve(state.get("content_metadata"))


def run_mqm_shadow(
    state: Dict[str, Any],
    violations: List[Dict[str, Any]],
    legacy_status: str,
) -> Optional[Dict[str, Any]]:
    """Score the same violations through the MQM engine and log the diff.

    Returns the comparison dict (also useful for tests) or ``None`` when the
    shadow is disabled or scoring fails. NEVER raises; NEVER affects the verdict.
    """
    settings = get_settings()
    if not settings.mqm_shadow_enabled:
        return None
    try:
        profile = resolve_metric_profile(state)
        ewc = sum(
            len((seg.get("source_text") or "").split())
            for seg in state.get("segments", [])
            if seg.get("translated_text")
        )
        mqm = score_from_violations(violations, profile, max(ewc, 1))

        legacy_blocked = legacy_status == "BLOCKED"
        mqm_would_block = (not mqm.passed) or mqm.critical_auto_fail
        block_agreement = legacy_blocked == mqm_would_block

        logger.info(
            "MQM_SHADOW job=%s profile=%s ewc=%s legacy_status=%s mqm_cqs=%s "
            "mqm_rqs=%s mqm_passed=%s critical_auto_fail=%s insufficient_sample=%s "
            "block_agreement=%s",
            state.get("job_id"),
            f"{profile.profile_id}@{profile.version}",
            ewc,
            legacy_status,
            mqm.cqs,
            mqm.rqs,
            mqm.passed,
            mqm.critical_auto_fail,
            mqm.insufficient_sample,
            block_agreement,
        )
        comparison = {
            "profile": f"{profile.profile_id}@{profile.version}",
            "ewc": ewc,
            "legacy_status": legacy_status,
            "mqm": mqm.to_dict(),
            "block_agreement": block_agreement,
        }

        # TMX-MQM-5a-emit: persist the diff to the v2 audit chain so the
        # distribution comparison is durable + queryable for the phase-b cutover
        # gate review and Phase-2 calibration. The emit helper is itself fail-safe.
        job_id = state.get("job_id")
        if job_id:
            from app.agents._audit_v2_emit import emit_v2_audit_event
            emit_v2_audit_event(
                job_id=job_id,
                event_type="MQM_SHADOW_SCORE",
                actor_id=None,
                actor_kind="agent",
                payload={"_actor_node": "mqm_engine_shadow", **comparison},
            )
        return comparison
    except Exception as e:  # never let the shadow break the gate
        logger.warning("MQM shadow scoring failed (non-fatal, verdict unaffected): %s", e)
        return None


async def run_judge_shadow(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the INDEPENDENT judge in shadow (TMX-MQM-4): emit §5.7 annotations +
    a judge-only MQM score to the audit chain. Changes no verdict. Default OFF
    (one extra LLM call/job); enable for the pilot tenant to gather judge-vs-gate
    data before the cutover. Fully fail-safe."""
    settings = get_settings()
    if not settings.mqm_judge_shadow_enabled:
        return None
    try:
        from app.services.mqm_engine import score as _score
        from app.services.mqm_judge import judge_segments

        segs = [s for s in state.get("segments", []) if s.get("translated_text")]
        if not segs:
            return None
        content_type = (state.get("content_metadata") or {}).get("content_type", "") or ""
        annotations = await judge_segments(
            segs,
            state.get("source_language", "en"),
            state.get("target_language", "en"),
            content_type=content_type,
            grounding=state.get("constraint_pack"),
        )
        profile = resolve_metric_profile(state)
        ewc = sum(len((s.get("source_text") or "").split()) for s in segs)
        judge_score = _score(annotations, profile, max(ewc, 1))

        critical = sum(1 for a in annotations if a.severity.value == "CRITICAL")
        logger.info(
            "MQM_JUDGE_SHADOW job=%s judge_annotations=%s critical=%s judge_passed=%s",
            state.get("job_id"), len(annotations), critical, judge_score.passed,
        )
        job_id = state.get("job_id")
        if job_id:
            from app.agents._audit_v2_emit import emit_v2_audit_event
            emit_v2_audit_event(
                job_id=job_id,
                event_type="MQM_JUDGE_SHADOW",
                actor_id=None,
                actor_kind="agent",
                payload={
                    "_actor_node": "judge",
                    "judge_annotation_count": len(annotations),
                    "judge_critical_count": critical,
                    "judge_mqm": judge_score.to_dict(),
                },
            )
        return {"annotation_count": len(annotations), "judge_mqm": judge_score.to_dict()}
    except Exception as e:
        logger.warning("MQM judge shadow failed (non-fatal, verdict unaffected): %s", e)
        return None
