
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class DefectSeverity(str, Enum):
    """
    Regulatory Risk Classification.
    CRITICAL:    Safety impact. Automatic BLOCK.
    MAJOR:       Meaning impact/Confusion. Review Required.
    MINOR:       Style/Formatting. Auto-fix or Warning.
    """
    CRITICAL = "CRITICAL" # Safety, Dosage, Contraindications, Units
    MAJOR = "MAJOR"       # Terminology, Omissions, ambiguous phrasing
    MINOR = "MINOR"       # Style, Punctuation, Spaces

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
