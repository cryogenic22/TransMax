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
        # TMX-MQM-EVAL-KAPPA: persist the judge's PER-SEGMENT verdict (strings
        # only — canonical-JSON safe) so a future judge↔human agreement (Cohen's
        # κ) can join on segment_id. Aggregate counts alone are not joinable.
        judge_segment_labels = [
            {"segment_id": a.segment_id, "severity": a.severity.value, "dimension": a.dimension.value}
            for a in annotations
            if a.segment_id
        ]
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
                    "judge_segment_labels": judge_segment_labels,
                    "judge_mqm": judge_score.to_dict(),
                },
            )
        return {"annotation_count": len(annotations), "judge_mqm": judge_score.to_dict()}
    except Exception as e:
        logger.warning("MQM judge shadow failed (non-fatal, verdict unaffected): %s", e)
        return None


async def run_ensemble_shadow(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the independent judge N times in SHADOW and combine them with the
    most-severe + disagreement-escalation aggregator (TMX-MQM-ENSEMBLE-RUN).

    Changes NO verdict. Default OFF (N× the per-job judge cost). Fully fail-safe.
    Composition only: it reuses ``judge_segments`` (the single-judge runner),
    ``mqm_review.aggregate_ensemble`` (most-severe merge — never averaged), the
    ONE ``mqm_engine.score`` authority, and ``cohen_kappa`` for inter-judge
    agreement. It introduces no new scoring or aggregation logic.

    Honesty (A3/A6): with ``enable_llm_router`` off, every judge resolves to the
    SAME model, so the "ensemble" is single-lineage self-consistency, not
    independent corroboration — the emitted ``single_lineage`` flag + the
    inter-judge κ say so (high κ under single lineage is NOT evidence of
    reliability). When a 2nd in-boundary lineage is validated and the router
    flips, this SAME code becomes a true ensemble (ADR-0007 review cond. 1).
    """
    settings = get_settings()
    if not getattr(settings, "mqm_ensemble_shadow_enabled", False):
        return None
    try:
        from app.services.judge_eval import binary_severity_label_map, cohen_kappa
        from app.services.llm import resolve_model
        from app.services.mqm_engine import score as _score
        from app.services.mqm_judge import judge_segments
        from app.services.mqm_review import aggregate_ensemble

        segs = [s for s in state.get("segments", []) if s.get("translated_text")]
        if not segs:
            return None

        # Clamp [2, 5]: <2 is not an ensemble; an upper cap stops a misconfigured
        # size from multiplying the per-job LLM cost without bound (cost reckoning).
        n_judges = min(5, max(2, int(getattr(settings, "mqm_ensemble_size", 2) or 2)))
        content_type = (state.get("content_metadata") or {}).get("content_type", "") or ""
        source_language = state.get("source_language", "en")
        target_language = state.get("target_language", "en")
        grounding = state.get("constraint_pack")

        annotation_sets: List[List[Any]] = []
        for i in range(n_judges):
            anns = await judge_segments(
                segs,
                source_language,
                target_language,
                content_type=content_type,
                grounding=grounding,
                judge_id=f"judge-{chr(ord('a') + i)}",
            )
            annotation_sets.append(anns)

        result = aggregate_ensemble(annotation_sets)

        profile = resolve_metric_profile(state)
        ewc = sum(len((s.get("source_text") or "").split()) for s in segs)
        ensemble_score = _score(result.merged, profile, max(ewc, 1))

        # Inter-judge agreement over the FULL segment universe (unflagged ⇒ "OK",
        # so the κ is not biased toward the few flagged spans). PAIRWISE on the
        # first two judges — the field name says so, so an N-judge run does not
        # misread it as overall ensemble agreement.
        seg_ids = [s.get("segment_id") or s.get("id") for s in segs]
        kappa_first_pair = None
        kappa_pair = None
        if len(annotation_sets) >= 2 and any(seg_ids):
            crit_a = {a.segment_id for a in annotation_sets[0] if a.segment_id and a.severity.value == "CRITICAL"}
            crit_b = {a.segment_id for a in annotation_sets[1] if a.segment_id and a.severity.value == "CRITICAL"}
            labels_a = binary_severity_label_map(seg_ids, crit_a)
            labels_b = binary_severity_label_map(seg_ids, crit_b)
            kappa_first_pair = cohen_kappa(labels_a, labels_b).kappa
            kappa_pair = ["judge-a", "judge-b"]

        # Record the REAL models the judges used (from annotation provenance), so
        # `single_lineage` reflects observed reality. When NO judge produced an
        # annotation we have no provenance to compare — report None (unknown)
        # rather than asserting independence from the router flag alone (A3).
        distinct_models = {a.model_version for anns in annotation_sets for a in anns if a.model_version}
        if distinct_models:
            models = sorted(distinct_models)
            single_lineage = len(distinct_models) == 1
        else:
            models = [resolve_model(task="judge")]
            single_lineage = None

        logger.info(
            "MQM_ENSEMBLE_SHADOW job=%s judges=%s merged=%s escalate=%s "
            "single_lineage=%s inter_judge_kappa_first_pair=%s ensemble_passed=%s",
            state.get("job_id"), n_judges, len(result.merged), result.escalate,
            single_lineage, kappa_first_pair, ensemble_score.passed,
        )

        job_id = state.get("job_id")
        if job_id:
            from app.agents._audit_v2_emit import emit_v2_audit_event
            emit_v2_audit_event(
                job_id=job_id,
                event_type="MQM_ENSEMBLE_SHADOW",
                actor_id=None,
                actor_kind="agent",
                payload={
                    "_actor_node": "judge_ensemble",
                    "num_judges": n_judges,
                    "per_judge_annotation_counts": [len(a) for a in annotation_sets],
                    "merged_annotation_count": len(result.merged),
                    "escalate": result.escalate,
                    "disagreement_count": len(result.disagreements),
                    "single_lineage": single_lineage,
                    "models": models,
                    "inter_judge_kappa_first_pair": kappa_first_pair,
                    "kappa_pair": kappa_pair,
                    "ensemble_mqm": ensemble_score.to_dict(),
                },
            )
        return {
            "num_judges": n_judges,
            "merged_annotation_count": len(result.merged),
            "escalate": result.escalate,
            "single_lineage": single_lineage,
            "inter_judge_kappa_first_pair": kappa_first_pair,
            "ensemble_mqm": ensemble_score.to_dict(),
        }
    except Exception as e:
        logger.warning("MQM ensemble shadow failed (non-fatal, verdict unaffected): %s", e)
        return None
