import pytest
from app.services.quality_gate import QualityGateService

@pytest.fixture
def quality_gate():
    return QualityGateService()

def test_check_numbers_mismatch(quality_gate):
    source = "Take 10 mg daily."
    target = "Take 100 mg daily." # Critical error
    violations = quality_gate.check_numbers(source, target)
    assert len(violations) > 0
    assert violations[0]['type'] == 'number_mismatch'
    assert violations[0]['severity'] == 'critical'

def test_check_numbers_match(quality_gate):
    source = "Take 10 mg daily."
    target = "Take 10 mg daily."
    violations = quality_gate.check_numbers(source, target)
    assert len(violations) == 0

def test_check_mandatory_terms_missing(quality_gate):
    glossary = [{"source": "Kidney", "target": "Renal"}]
    source = "Kidney failure."
    target = "Liver failure." # Wrong term
    violations = quality_gate.check_mandatory_terms(source, target, glossary)
    assert len(violations) > 0
    assert violations[0]['type'] == 'mandatory_term_missing'

def test_check_mandatory_terms_present(quality_gate):
    glossary = [{"source": "Kidney", "target": "Renal"}]
    source = "Kidney failure."
    target = "Renal failure."
    violations = quality_gate.check_mandatory_terms(source, target, glossary)
    assert len(violations) == 0

def test_check_units_equivalence(quality_gate):
    # Pint should handle this: 1000 mg == 1 g
    source = "Take 1000 mg."
    target = "Take 1 g."
    violations = quality_gate.check_units(source, target)
    assert len(violations) == 0

def test_check_units_mismatch(quality_gate):
    # 10 mg != 10 g
    source = "Take 10 mg."
    target = "Take 10 g."
    violations = quality_gate.check_units(source, target)
    assert len(violations) > 0
    assert violations[0]['type'] == 'unit_mismatch'
    
def test_check_units_hallucination(quality_gate):
    source = "Take medicine."
    target = "Take 10 mg."
    violations = quality_gate.check_units(source, target)
    assert len(violations) > 0
    assert violations[0]['type'] == 'unit_hallucination'

def test_composite_score_blocking(quality_gate):
    # Critical violation -> BLOCKED
    violations = [{"severity": "critical", "type": "test_crit"}]
    status = quality_gate.evaluate_quality_report(violations, word_count=100)
    assert status == "BLOCKED"

def test_composite_score_major(quality_gate):
    # Major violation -> REVIEW_REQUIRED
    violations = [{"severity": "major", "type": "test_major"}]
    status = quality_gate.evaluate_quality_report(violations, word_count=100)
    assert status == "REVIEW_REQUIRED"
    
def test_composite_score_minor_pass(quality_gate):
    # 3 minor violations in 1000 words -> PASS (Threshold is > 5)
    violations = [
        {"severity": "minor"} for _ in range(3)
    ]
    status = quality_gate.evaluate_quality_report(violations, word_count=1000)
    assert status == "PASS"

def test_composite_score_minor_fail(quality_gate):
    # 6 minor violations in 1000 words -> REVIEW_REQUIRED
    violations = [
        {"severity": "minor"} for _ in range(6)
    ]
    status = quality_gate.evaluate_quality_report(violations, word_count=1000)
    assert status == "REVIEW_REQUIRED"
