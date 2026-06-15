
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class DefectSeverity(str, Enum):
    """
    Regulatory Risk Classification — aligned to the MQM severity ladder.
    CRITICAL:    Safety impact. Automatic BLOCK.            (MQM SPM 25)
    MAJOR:       Meaning impact/Confusion. Review Required. (MQM SPM 5)
    MINOR:       Style/Formatting. Auto-fix or Warning.     (MQM SPM 1)
    NEUTRAL:     Preferential / flagged-for-attention, acceptable. (MQM SPM 0)

    NEUTRAL was added for the MQM-2.0 engine (TMX-MQM-1): it is the
    "reviewer-preferred wording that is not an error" tier. The deterministic
    quality gates never emit NEUTRAL today (they only raise real defects), so
    adding it is purely additive — existing CRITICAL/MAJOR/MINOR semantics and
    `is_critical()` are unchanged.
    """
    CRITICAL = "CRITICAL" # Safety, Dosage, Contraindications, Units
    MAJOR = "MAJOR"       # Terminology, Omissions, ambiguous phrasing
    MINOR = "MINOR"       # Style, Punctuation, Spaces
    NEUTRAL = "NEUTRAL"   # Preferential — not an error (MQM only)


# MQM-2.0 Severity Penalty Multipliers (TMX-MQM-1). Exponential ladder per the
# MQM Council recommendation (Neutral=0, Minor=1, Major=5, Critical=25). These
# are the defaults; a content-type metric profile may override (see
# app/core/metric_profiles/). The MQM engine multiplies SPM × Error-Type-Weight
# to produce penalty points — see app/services/mqm_engine.py.
SEVERITY_PENALTY_MULTIPLIER: dict = {
    DefectSeverity.NEUTRAL: 0,
    DefectSeverity.MINOR: 1,
    DefectSeverity.MAJOR: 5,
    DefectSeverity.CRITICAL: 25,
}


class MqmDimension(str, Enum):
    """
    The seven MQM-Core top-level error dimensions, instantiated for pharma
    (TMX-MQM-1; see LangOps-Platform-Vision §5.2). Every quality annotation is
    classified into exactly one dimension; the metric profile assigns an
    Error-Type Weight per dimension.
    """
    TERMINOLOGY = "Terminology"               # term-base / QRD standard-phrase / MedDRA
    ACCURACY = "Accuracy"                      # mistranslation, omission, numeric/unit/dose
    LINGUISTIC = "Linguistic conventions"     # grammar, spelling, punctuation, register
    STYLE = "Style"                           # awkward / inconsistent style
    LOCALE = "Locale conventions"             # number/date/decimal/measurement format
    AUDIENCE = "Audience appropriateness"     # readability / reading-level fit
    DESIGN = "Design & markup"                # tags, layout, lost emphasis on warnings

class DefectCategory(str, Enum):
    NUMERIC_MISMATCH = "NUMERIC_MISMATCH"     # Critical
    UNIT_MISMATCH = "UNIT_MISMATCH"           # Critical
    OMISSION = "OMISSION"                     # Major/Critical
    ADDITION = "ADDITION"                     # Major
    MISTRANSLATION = "MISTRANSLATION"         # Major/Critical
    TERMINOLOGY = "TERMINOLOGY"               # Major
    FORMATTING = "FORMATTING"                 # Minor
    PII_LEAK = "PII_LEAK"                     # Major/Critical
    NEGATION_FLIP = "NEGATION_FLIP"           # Critical
    ANCHOR_MISMATCH = "ANCHOR_MISMATCH"       # Critical (Analytical)
    SENTIMENT_SHIFT = "SENTIMENT_SHIFT"       # Major (Analytical)
    TABLE_CORRUPTION = "TABLE_CORRUPTION"     # Critical (Structure)
    COMPLEXITY_WARNING = "COMPLEXITY_WARNING" # Major (Human Review Required)
    PLACEHOLDER_CORRUPTION = "PLACEHOLDER_CORRUPTION" # Critical (Integrity)
    FREQUENCY_MISMATCH = "FREQUENCY_MISMATCH"         # Critical (Dosing)
    FORMATTING_ERROR = "FORMATTING_ERROR"             # Major (Regulatory)
    STRUCTURE_ERROR = "STRUCTURE_ERROR"               # Major (Regulatory)
    PROMPT_INJECTION = "PROMPT_INJECTION"             # Critical (Input safety — TMX-INJ-1)


# Bridge the existing deterministic-gate taxonomy onto the seven MQM dimensions
# (TMX-MQM-1). This is what lets a legacy gate violation become an MQM
# annotation without re-authoring the gates — reconciliation, not replacement.
# Any DefectCategory absent here, or any free-form category string, falls back
# to ACCURACY (the safest, highest-weighted default in regulated content).
CATEGORY_TO_DIMENSION: dict = {
    DefectCategory.NUMERIC_MISMATCH: MqmDimension.ACCURACY,
    DefectCategory.UNIT_MISMATCH: MqmDimension.ACCURACY,
    DefectCategory.OMISSION: MqmDimension.ACCURACY,
    DefectCategory.ADDITION: MqmDimension.ACCURACY,
    DefectCategory.MISTRANSLATION: MqmDimension.ACCURACY,
    DefectCategory.NEGATION_FLIP: MqmDimension.ACCURACY,
    DefectCategory.FREQUENCY_MISMATCH: MqmDimension.ACCURACY,
    DefectCategory.ANCHOR_MISMATCH: MqmDimension.ACCURACY,
    DefectCategory.TERMINOLOGY: MqmDimension.TERMINOLOGY,
    DefectCategory.SENTIMENT_SHIFT: MqmDimension.STYLE,
    DefectCategory.FORMATTING: MqmDimension.LOCALE,
    DefectCategory.FORMATTING_ERROR: MqmDimension.LOCALE,
    DefectCategory.STRUCTURE_ERROR: MqmDimension.DESIGN,
    DefectCategory.TABLE_CORRUPTION: MqmDimension.DESIGN,
    DefectCategory.PLACEHOLDER_CORRUPTION: MqmDimension.DESIGN,
    DefectCategory.COMPLEXITY_WARNING: MqmDimension.AUDIENCE,
    DefectCategory.PII_LEAK: MqmDimension.ACCURACY,
    DefectCategory.PROMPT_INJECTION: MqmDimension.ACCURACY,
}


def dimension_for_category(category) -> "MqmDimension":
    """Resolve a DefectCategory (or its string value) to an MQM dimension.

    Falls back to ACCURACY for unknown / free-form categories — never raises,
    so the engine can score legacy violations without a taxonomy round-trip.
    """
    if isinstance(category, DefectCategory):
        return CATEGORY_TO_DIMENSION.get(category, MqmDimension.ACCURACY)
    # Accept a raw string (the deterministic gate emits category strings).
    try:
        return CATEGORY_TO_DIMENSION.get(DefectCategory(category), MqmDimension.ACCURACY)
    except (ValueError, KeyError):
        return MqmDimension.ACCURACY


def is_critical(severity) -> bool:
    """Case-insensitive check whether a severity is CRITICAL (TMX-QG-SEVCASE).

    Defect severities are produced as the uppercase enum value ("CRITICAL")
    by the quality gate, but some legacy paths emit lowercase ("critical").
    Several call sites compared against the lowercase literal and so silently
    NEVER matched a real critical defect — auto-blocking and refine-exclusion
    were broken. This canonical helper normalises both forms.
    """
    if severity is None:
        return False
    value = getattr(severity, "value", severity)  # accept DefectSeverity or str
    return str(value).upper() == DefectSeverity.CRITICAL.value


@dataclass
class Defect:
    category: DefectCategory
    severity: DefectSeverity
    message: str
    segment_id: Optional[str] = None
    source_text: Optional[str] = None
    suggestion: Optional[str] = None

class TaxonomyService:
    """
    Maps technical violations to Regulatory Defect Severity.
    """
    
    @staticmethod
    def classify_violation(violation_type: str, message: str) -> DefectSeverity:
        """
        Determines severity based on the nature of the violation.
        """
        message_lower = message.lower()
        
        # 1. CRITICAL RULES (Safety/Dosing/Negation)
        if "unit" in message_lower or "numeric" in message_lower or "number" in message_lower:
            return DefectSeverity.CRITICAL
            
        if "negation" in message_lower: # "Do NOT take" vs "Take"
            return DefectSeverity.CRITICAL

        if "injection" in message_lower: # TMX-INJ-1: embedded prompt-injection in source
            return DefectSeverity.CRITICAL

        if "omission" in message_lower or "untranslated" in message_lower: # TMX-OMIT-1: gross content drop
            return DefectSeverity.CRITICAL

        if "contraindication" in message_lower:
            return DefectSeverity.CRITICAL

        if "anchor" in message_lower:
            return DefectSeverity.CRITICAL

        if "placeholder" in message_lower:
            return DefectSeverity.CRITICAL

        if "frequency" in message_lower:
            return DefectSeverity.CRITICAL
            
        # 2. MAJOR RULES (Terminology/Meaning)
        if "glossary" in message_lower or "terminology" in message_lower:
            return DefectSeverity.MAJOR
            
        if "sentiment" in message_lower:
            return DefectSeverity.MAJOR
            
        if "pii" in message_lower or "redacted" in message_lower:
            return DefectSeverity.CRITICAL # PII leak is Critical compliance risk

        if "table" in message_lower and ("mismatch" in message_lower or "corruption" in message_lower):
            return DefectSeverity.CRITICAL

        if "complexity" in message_lower or "check" in message_lower:
            return DefectSeverity.MAJOR # Soft mark for human review

        # 3. MINOR RULES (Style)
        if "space" in message_lower or "punctuation" in message_lower or "format" in message_lower:
            return DefectSeverity.MINOR
            
        # Default fallback
        return DefectSeverity.MAJOR
