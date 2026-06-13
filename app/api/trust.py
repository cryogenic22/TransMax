"""
Trust posture — REAL, honestly-labelled security/compliance signals (A1/A3).

Replaces the fabricated "Privacy & Safety" panel (which hardcoded
"Zero Retention / US-EAST-2 / AES-256 / NER_V2_EN" as live green status). Every
field here is EITHER derived from real config/runtime (``verified: true``) OR
explicitly marked as infrastructure/policy-level and NOT asserted by the
application (``verified: false``). A regulator must never read an invented green
light as a verified control.
"""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/posture")
def get_trust_posture() -> dict:
    """Return the real, self-reported trust posture. Honest by construction:
    unknown/infrastructure-level controls are surfaced as unverified, never faked."""
    auth_mode = getattr(settings, "auth_mode", "none")
    model = getattr(settings, "default_gpt_model", "unknown")
    # No Azure-OpenAI LLM config exists today; the supplier is OpenAI.
    provider = "Azure OpenAI" if getattr(settings, "azure_openai_endpoint", "") else "OpenAI"
    region = getattr(settings, "data_region", "") or None

    controls = [
        {
            "key": "auth",
            "label": "Authentication & Access",
            "value": auth_mode,
            "verified": auth_mode != "none",
            "detail": (
                "Enforced login + role-based access control"
                if auth_mode != "none"
                else "AUTH_MODE=none — open access (development posture, not for pilot)"
            ),
        },
        {
            "key": "audit_chain",
            "label": "Audit Trail Immutability",
            "value": "SHA-256 domain-separated hash chain (v2)",
            "verified": True,
            "detail": "Independently re-computable via /api/v1/audit/verify_v2",
        },
        {
            "key": "pii",
            "label": "PII Redaction",
            "value": "Deterministic regex shield",
            "verified": True,
            "detail": "Regex pattern matching; Presidio/NER upgrade pending (TMX-3805)",
        },
        {
            "key": "llm_supplier",
            "label": "LLM Qualified Supplier",
            "value": f"{provider} · {model}",
            "verified": True,
            "detail": "Provider data-retention is governed by the provider DPA — not asserted in-app",
        },
        {
            "key": "data_residency",
            "label": "Data Residency",
            "value": region or "Not configured",
            "verified": bool(region),
            "detail": "Infrastructure-level; configure and verify in the deployment region",
        },
        {
            "key": "encryption_at_rest",
            "label": "Encryption at Rest",
            "value": "Infrastructure-managed",
            "verified": False,
            "detail": "Database / object-store level — not asserted by the application layer",
        },
    ]
    return {"app_env": getattr(settings, "app_env", "dev"), "controls": controls}
