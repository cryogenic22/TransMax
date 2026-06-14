"""
TMX-MQM-5c — resolve a content-type metric profile from job/document metadata.

This reconciles the two pre-existing, disconnected profile systems
(`regulatory_profiles.py` authority metadata + `profile_resolver.py`
archetype/tier) onto the MQM metric-profile registry: it maps a document's
content type (or its legacy archetype) to the profile the MQM engine scores
against. It replaces the single-default-profile seam in `mqm_shadow`.

Pure + deterministic; never raises (falls back to the configured default).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.metric_profiles import (
    MetricProfile,
    MetricProfileNotFoundError,
    MetricProfileRegistry,
)

# Content-type / doc-type hint → metric-profile id (matched case-insensitively).
_CONTENT_TYPE_TO_PROFILE: Dict[str, str] = {
    "icf": "icf", "informed_consent": "icf", "consent": "icf",
    "smpc": "smpc_pil", "spc": "smpc_pil", "pil": "smpc_pil",
    "labelling": "smpc_pil", "labeling": "smpc_pil", "label": "smpc_pil", "ifu": "smpc_pil",
    "pv": "pv", "pharmacovigilance": "pv", "psur": "pv", "dsur": "pv",
    "ae_narrative": "pv", "icsr": "pv", "narrative": "pv",
    "pro": "pro_coa", "coa": "pro_coa", "pro_coa": "pro_coa", "questionnaire": "pro_coa",
    "promo": "promo", "promotional": "promo", "mlr": "promo", "transcreation": "promo",
}

# Legacy TranslationArchetype → metric profile (used when no content type given).
_ARCHETYPE_TO_PROFILE: Dict[str, str] = {
    "SAFETY_CRITICAL": "smpc_pil",   # strictest profile
    "ANALYTICAL": "pro_coa",         # concept equivalence
    "OPERATIONAL": "pv",
    "LEGAL": "smpc_pil",
    "INFORMATIONAL": "promo",
}


def resolve_profile_id(metadata: Optional[Dict[str, Any]]) -> str:
    """Resolve a metric-profile id from job/document metadata.

    Precedence: explicit override → content-type hint → legacy archetype →
    the configured default profile.
    """
    settings = get_settings()
    md = metadata or {}

    explicit = md.get("metric_profile") or md.get("metric_profile_id")
    if explicit:
        return str(explicit)

    for key in ("content_type", "doc_type", "document_type"):
        val = md.get(key)
        if val and str(val).lower() in _CONTENT_TYPE_TO_PROFILE:
            return _CONTENT_TYPE_TO_PROFILE[str(val).lower()]

    arch = md.get("archetype")
    if arch and str(arch).upper() in _ARCHETYPE_TO_PROFILE:
        return _ARCHETYPE_TO_PROFILE[str(arch).upper()]

    return settings.mqm_default_profile


def resolve_metric_profile(metadata: Optional[Dict[str, Any]]) -> MetricProfile:
    """Resolve the metric profile object; falls back to the default on a bad id."""
    profile_id = resolve_profile_id(metadata)
    try:
        return MetricProfileRegistry.load(profile_id)
    except MetricProfileNotFoundError:
        return MetricProfileRegistry.load(get_settings().mqm_default_profile)
