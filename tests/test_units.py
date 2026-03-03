from app.services.quality_gate import QualityGateService
import pytest

@pytest.fixture
def service():
    return QualityGateService()

def test_check_units_match_exact(service):
    """Test exact match passes (10mg -> 10mg)"""
    source = "Take 10mg daily"
    target = "Take 10mg daily"
    violations = service.check_unit_integrity(source, target)
    assert len(violations) == 0

def test_check_units_match_whitespace(service):
    """Test whitespace insensitivity (10 mg -> 10mg)"""
    source = "Take 10 mg daily"
    target = "Take 10mg daily"
    violations = service.check_unit_integrity(source, target)
    assert len(violations) == 0

def test_check_units_mismatch_value(service):
    """Test value mismatch fails (10mg -> 20mg)"""
    source = "Take 10mg daily"
    target = "Take 20mg daily"
    violations = service.check_unit_integrity(source, target)
    assert len(violations) > 0

def test_check_units_mismatch_unit(service):
    """Test unit mismatch fails (10mg -> 10g)"""
    source = "Take 10mg daily"
    target = "Take 10g daily"
    violations = service.check_unit_integrity(source, target)
    assert len(violations) > 0
    assert "missing" in violations[0].message.lower() or "mismatch" in violations[0].message.lower()

def test_check_units_ignore_non_pharma(service):
    """Test that it doesn't freak out on non-pharma text without units"""
    source = "Hello world"
    target = "Hello world"
    violations = service.check_unit_integrity(source, target)
    assert len(violations) == 0
