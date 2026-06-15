
"""
TransMax Regulatory Profile Registry
Defines authority-specific rules, formatting, and templates.
Families: EU, UK, US, ME, JP.
"""

from typing import Any, Dict, Optional

REGULATORY_PROFILES = {
    # FAMILY A: EU (EMA)
    "EMA_SMPC_EN_GB": {
        "authority": "EMA",
        "family": "EU",
        "doc_type": "smpc",
        "locale": "en-GB",
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "mandatory_headings": [
            "1. NAME OF THE MEDICINAL PRODUCT",
            "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
            "3. PHARMACEUTICAL FORM",
            "4. CLINICAL PARTICULARS",
            "5. PHARMACOLOGICAL PROPERTIES",
            "6. PHARMACEUTICAL PARTICULARS"
        ]
    },
    "EMA_SMPC_FR_FR": {
        "authority": "EMA",
        "family": "EU",
        "doc_type": "smpc",
        "locale": "fr-FR",
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ",",
        "mandatory_headings": [
            "1. DÉNOMINATION DU MÉDICAMENT",
            "2. COMPOSITION QUALITATIVE ET QUANTITATIVE",
            "3. FORME PHARMACEUTIQUE",
            "4. DONNÉES CLINIQUES",
            "5. PHARMACOLOGICAL PROPERTIES",
            "6. DONNÉES PHARMACEUTIQUES"
        ]
    },
    
    # FAMILY B: UK (MHRA)
    "MHRA_SMPC_EN_GB": {
        "authority": "MHRA",
        "family": "UK",
        "doc_type": "smpc",
        "locale": "en-GB",
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "mandatory_headings": [
            "1. NAME OF THE MEDICINAL PRODUCT",
            "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
            "3. PHARMACEUTICAL FORM",
            "4. CLINICAL PARTICULARS",
            "5. PHARMACOLOGICAL PROPERTIES",
            "6. PHARMACEUTICAL PARTICULARS"
        ]
    },
    
    # FAMILY C: US (FDA)
    "FDA_PI_EN_US": {
        "authority": "FDA",
        "family": "US",
        "doc_type": "pi",
        "locale": "en-US",
        "date_format": "MM/DD/YYYY",
        "decimal_separator": ".",
        "mandatory_headings": [
            "HIGHLIGHTS OF PRESCRIBING INFORMATION",
            "FULL PRESCRIBING INFORMATION: CONTENTS",
            "FULL PRESCRIBING INFORMATION",
            "INDICATIONS AND USAGE",
            "DOSAGE AND ADMINISTRATION",
            "DOSAGE FORMS AND STRENGTHS",
            "CONTRAINDICATIONS",
            "WARNINGS AND PRECAUTIONS",
            "ADVERSE REACTIONS"
        ]
    },
    
    # FAMILY D: Middle East (SFDA)
    "SFDA_PIL_AR_SA": {
        "authority": "SFDA",
        "family": "ME",
        "doc_type": "pil",
        "locale": "ar-SA",
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "script_direction": "rtl",
        "mandatory_headings": [
            "نشرة داخلية",
            "ما هو هذا الدواء وفيم يُستعمل",
            "قبل استعمال هذا الدواء",
            "كيفية استعمال هذا الدواء",
            "الأعراض الجانبية المحتملة",
            "كيفية حفظ هذا الدواء",
            "محتويات العبوة ومعلومات أخرى"
        ]
    },
    
    # FAMILY E: Japan (PMDA)
    "PMDA_PI_JA_JP": {
        "authority": "PMDA",
        "family": "JP",
        "doc_type": "package_insert",
        "locale": "ja-JP",
        "date_format": "YYYY/MM/DD",
        "decimal_separator": ".",
        "mandatory_headings": [
            "効能又は効果",
            "用法及び用量",
            "禁忌",
            "警告",
            "注意",
            "副作用"
        ]
    },

    # FAMILY F: MARKETING (Non-Regulatory, High Quality)
    "MARKETING_GLOBAL_EN": {
        "authority": "Internal",
        "family": "Marketing",
        "doc_type": "marketing_material",
        "locale": "en-US",
        "date_format": None, # Flexible
        "decimal_separator": ".",
        "mandatory_headings": [] # No mandatory headers
    }
}

def get_profile(profile_id: str):
    """Retrieves a regulatory profile by ID."""
    return REGULATORY_PROFILES.get(profile_id)

def resolve_profile(authority: str, locale: str, doc_type: str):
    """
    Helper to find a profile based on metadata.
    E.g. resolve_profile("EMA", "fr-FR", "smpc") -> "EMA_SMPC_FR_FR"
    """
    for pid, profile in REGULATORY_PROFILES.items():
        if (profile["authority"] == authority and
            profile["locale"] == locale and
            profile["doc_type"] == doc_type):
            return profile
    return None


def regulatory_profile_for_gate(
    content_metadata: Optional[Dict[str, Any]], *, enabled: bool
) -> Optional[str]:
    """The regulatory profile id the quality gate should enforce (TMX-QRD-WIRE).

    Returns the job's explicit ``regulatory_profile`` tag, but ONLY when QRD
    checks are ``enabled``. Returns ``None`` when disabled (so the gate's
    date/header checks stay dead — byte-identical to today) or when the tag is
    absent/unknown (A3: never substitute a default regulatory profile — an
    unrecognised authority must fail to NO check, not a guessed one).
    """
    if not enabled:
        return None
    pid = (content_metadata or {}).get("regulatory_profile")
    if not isinstance(pid, str):
        return None  # absent / malformed tag → no check (A3), never a TypeError into the gate
    return pid if get_profile(pid) else None
