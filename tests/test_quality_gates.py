import pytest
from app.services.quality_gate import QualityGateService

@pytest.fixture
def quality_gate():
    return QualityGateService()

def test_number_mismatch_detected(quality_gate):
    """Critical number mismatch detected via check_segment."""
    source = "Take 10 mg daily."
    target = "Take 100 mg daily."
    violations = quality_gate.check_segment(source, target, {}, "en")
    # Should detect numeric mismatch (10 missing in target replaced by 100)
    assert any(v['category'] == 'NUMERIC_MISMATCH' or v['category'] == 'UNIT_MISMATCH' for v in violations)

def test_numbers_match(quality_gate):
    """No violations when numbers match."""
    source = "Take 10 mg daily."
    target = "Take 10 mg daily."
    violations = quality_gate.check_segment(source, target, {}, "en")
    num_violations = [v for v in violations if v['category'] in ('NUMERIC_MISMATCH', 'UNIT_MISMATCH')]
    assert len(num_violations) == 0

def test_glossary_term_missing(quality_gate):
    """Glossary term missing detected."""
    glossary = [{"source": "Kidney", "target": "Renal"}]
    source = "Kidney failure."
    target = "Liver failure."
    constraints = {"glossary": glossary}
    violations = quality_gate.check_segment(source, target, constraints, "en")
    term_violations = [v for v in violations if v['category'] == 'TERMINOLOGY']
    assert len(term_violations) > 0

def test_glossary_term_present(quality_gate):
    """No violation when glossary term is present."""
    glossary = [{"source": "Kidney", "target": "Renal"}]
    source = "Kidney failure."
    target = "Renal failure."
    constraints = {"glossary": glossary}
    violations = quality_gate.check_segment(source, target, constraints, "en")
    term_violations = [v for v in violations if v['category'] == 'TERMINOLOGY']
    assert len(term_violations) == 0

def test_unit_integrity_match(quality_gate):
    """Units present correctly."""
    source = "Take 10 mg."
    target = "Take 10 mg."
    violations = quality_gate.check_unit_integrity(source, target)
    assert len(violations) == 0

def test_unit_integrity_mismatch(quality_gate):
    """Unit mismatch detected."""
    source = "Take 10 mg."
    target = "Take 10 g."
    violations = quality_gate.check_unit_integrity(source, target)
    assert len(violations) > 0

def test_verdict_blocking(quality_gate):
    """Critical violation -> BLOCKED."""
    violations = [{"severity": "CRITICAL", "category": "UNIT_MISMATCH", "message": "test", "segment_id": None}]
    result = quality_gate.evaluate_verdict(violations)
    assert result["status"] == "BLOCKED"

def test_verdict_major(quality_gate):
    """Major violation -> REVIEW_REQUIRED."""
    violations = [{"severity": "MAJOR", "category": "TERMINOLOGY", "message": "test", "segment_id": None}]
    result = quality_gate.evaluate_verdict(violations)
    assert result["status"] == "REVIEW_REQUIRED"

def test_verdict_pass(quality_gate):
    """No violations -> PASS."""
    result = quality_gate.evaluate_verdict([])
    assert result["status"] == "PASS"
