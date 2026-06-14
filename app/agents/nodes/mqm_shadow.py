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
from app.core.metric_profiles import MetricProfile, MetricProfileRegistry
from app.services.mqm_engine import score_from_violations

logger = logging.getLogger(__name__)


def resolve_metric_profile(state: Dict[str, Any]) -> MetricProfile:
    """Resolve the content-type metric profile for a job.

    Reconciliation seam: for now this returns the configured default profile.
    Content-type → profile resolution (mapping document type / archetype to a
    profile) lands in TMX-MQM-5c, which is also where the two pre-existing
    profile systems (`regulatory_profiles.py`, `profile_resolver.py`) get wired
    onto this registry. Until then a single strict default is the safe choice.
    """
    settings = get_settings()
    return MetricProfileRegistry.load(settings.mqm_default_profile)


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
        return {
            "profile": f"{profile.profile_id}@{profile.version}",
            "ewc": ewc,
            "legacy_status": legacy_status,
            "mqm": mqm.to_dict(),
            "block_agreement": block_agreement,
        }
    except Exception as e:  # never let the shadow break the gate
        logger.warning("MQM shadow scoring failed (non-fatal, verdict unaffected): %s", e)
        return None
