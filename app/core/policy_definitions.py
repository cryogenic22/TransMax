from enum import Enum
from typing import List, Dict, Any

# TMX-002: Severity Taxonomy
class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"

class ViolationType(str, Enum):
    NUMBER_MISMATCH = "number_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    UNIT_PARSE_ERROR = "unit_parse_error"
    NEGATION_FLIP = "negation_flip"
    FREQUENCY_MISMATCH = "frequency_mismatch"
    PLACEHOLDER_CORRUPTION = "placeholder_integrity_fail"
    PII_LEAK = "pii_integrity_fail"
    MANDATORY_TERM_MISSING = "mandatory_term_missing"
    FORBIDDEN_TERM_PRESENT = "forbidden_term"
    HALLUCINATION = "hallucination_detected"
    PUNCTUATION = "punctuation_mismatch"
    VARIANT_IMPROPER = "variant_improper"
    SPELLING_GRAMMAR = "spelling_grammar"
    TABLE_CORRUPTION = "table_corruption"

# Configuration: Default Severity Map
# Can be overridden by Tenant Policy in future
DEFAULT_SEVERITY_MAP = {
    ViolationType.NUMBER_MISMATCH: Severity.CRITICAL,
    ViolationType.UNIT_MISMATCH: Severity.CRITICAL,
    ViolationType.UNIT_PARSE_ERROR: Severity.MAJOR, # TMX-001 Recommendation
    ViolationType.NEGATION_FLIP: Severity.CRITICAL,
    ViolationType.FREQUENCY_MISMATCH: Severity.CRITICAL,
    ViolationType.PLACEHOLDER_CORRUPTION: Severity.CRITICAL,
    ViolationType.PII_LEAK: Severity.CRITICAL,
    ViolationType.MANDATORY_TERM_MISSING: Severity.MAJOR,
    ViolationType.FORBIDDEN_TERM_PRESENT: Severity.MAJOR, # Can be Critical for specific docs
    ViolationType.HALLUCINATION: Severity.CRITICAL,
    ViolationType.PUNCTUATION: Severity.MINOR,
    ViolationType.VARIANT_IMPROPER: Severity.MINOR,
    ViolationType.TABLE_CORRUPTION: Severity.CRITICAL,
}

# TMX-001: Decision Matrix
class RiskLevel(str, Enum):
    HIGH = "high"       # Pharma Labelling, SmPC
    MEDIUM = "medium"   # MedDev Manuals, Marketing
    LOW = "low"         # Internal comms

def get_severity(v_type: ViolationType) -> Severity:
    return DEFAULT_SEVERITY_MAP.get(v_type, Severity.MINOR)

def evaluate_status(violations: List[Dict[str, Any]], risk_level: RiskLevel = RiskLevel.HIGH) -> str:
    """
    Determines the document/segment status based on violations and risk level.
    Returns: BLOCKED, REVIEW_REQUIRED, or PASS
    """
    if not violations:
        return "PASS"
        
    # 1. Check for Criticals (Always Block)
    if any(v.get('severity') == Severity.CRITICAL for v in violations):
        return "BLOCKED"
        
    # 2. Check for Majors
    has_major = any(v.get('severity') == Severity.MAJOR for v in violations)
    
    if risk_level == RiskLevel.HIGH:
        # Pharma: Major -> Review
        if has_major:
            return "REVIEW_REQUIRED"
        # Minor Density Check (Placeholder threshold: >5 per 1000 words logic usually handled elsewhere)
        # For strict segment checks:
        if violations: # Any minor
            return "REVIEW_REQUIRED" # Strict Pharma: Clean records preferred, or at least review.
            
    elif risk_level == RiskLevel.MEDIUM:
        # MedDev: Major -> Review
        if has_major:
            return "REVIEW_REQUIRED"
        
    # Low risk or clean
    return "PASS"
