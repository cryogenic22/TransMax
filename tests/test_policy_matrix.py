import pytest
from app.core.policy_definitions import Severity, ViolationType, get_severity, evaluate_status, RiskLevel

def test_default_severity_map():
    """Verify TMX-002 Severity Taxonomy defaults."""
    assert get_severity(ViolationType.NUMBER_MISMATCH) == Severity.CRITICAL
    assert get_severity(ViolationType.UNIT_MISMATCH) == Severity.CRITICAL
    assert get_severity(ViolationType.NEGATION_FLIP) == Severity.CRITICAL
    assert get_severity(ViolationType.MANDATORY_TERM_MISSING) == Severity.MAJOR
    assert get_severity(ViolationType.PUNCTUATION) == Severity.MINOR

def test_evaluate_status_high_risk_critical():
    """TMX-001: High Risk + Critical -> BLOCKED."""
    violations = [{"severity": Severity.CRITICAL, "type": "any"}]
    assert evaluate_status(violations, RiskLevel.HIGH) == "BLOCKED"

def test_evaluate_status_high_risk_major():
    """TMX-001: High Risk + Major -> REVIEW_REQUIRED."""
    violations = [{"severity": Severity.MAJOR, "type": "any"}]
    assert evaluate_status(violations, RiskLevel.HIGH) == "REVIEW_REQUIRED"

def test_evaluate_status_medium_risk_major():
    """TMX-001: Medium Risk + Major -> REVIEW_REQUIRED."""
    violations = [{"severity": Severity.MAJOR, "type": "any"}]
    assert evaluate_status(violations, RiskLevel.MEDIUM) == "REVIEW_REQUIRED"

def test_evaluate_status_medium_risk_minor():
    """TMX-001: Medium Risk + Minor -> PASS (assuming low density)."""
    # Current logic ignores density here for simplicity in unit test, 
    # but strictly checks presence. 
    # Wait, implementation says MedDev: Pass (<2%).
    # Current impl: "Pass" if no major/critical.
    violations = [{"severity": Severity.MINOR, "type": "any"}]
    assert evaluate_status(violations, RiskLevel.MEDIUM) == "PASS"

def test_evaluate_status_high_risk_minor():
    """TMX-001: High Risk + Minor -> REVIEW_REQUIRED (Strict Mode)."""
    violations = [{"severity": Severity.MINOR, "type": "any"}]
    assert evaluate_status(violations, RiskLevel.HIGH) == "REVIEW_REQUIRED"

def test_clean_pass():
    assert evaluate_status([], RiskLevel.HIGH) == "PASS"
