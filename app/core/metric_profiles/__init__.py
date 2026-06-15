"""
Content-type MQM metric profiles (TMX-MQM-2).

Public API: the registry + the frozen profile record. Profiles live as
versioned YAML under ``<profile_id>/v<MAJOR>.<MINOR>.<PATCH>.yaml`` and are
loaded by ``MetricProfileRegistry.load(profile_id, version="latest")``.

Starting profiles (§5.4 of the LangOps Platform Vision; all thresholds are
proposals to be calibrated against gold data before go-live):
    icf       — Informed Consent Form (patient-facing)
    smpc_pil  — SmPC / PIL (labelling)
    pv        — Pharmacovigilance narrative
    pro_coa   — PRO / COA item
    promo     — Promotional / transcreation
"""
from app.core.metric_profiles.registry import (
    MetricProfile,
    MetricProfileNotFoundError,
    MetricProfileRegistry,
    MetricProfileSchemaError,
)

__all__ = [
    "MetricProfile",
    "MetricProfileRegistry",
    "MetricProfileNotFoundError",
    "MetricProfileSchemaError",
]
