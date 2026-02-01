
import pytest
from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory, DefectSeverity

@pytest.fixture
def gate_service():
    return QualityGateService()

def test_req_res_01_anchor_mismatch(gate_service):
    """
    REQ-RES-01: Scale anchors must match valid translations.
    Source: "Strongly Agree"
    Target: "D'accord" (This is "Agree", not "Strongly Agree") -> FAIL
    """
    source = "Strongly Agree"
    target = "D'accord" # Mismatch
    
    constraints = {"archetype": "ANALYTICAL"}
    
    defects = gate_service.check_segment(source, target, constraints, "fr")
    
    anchor_defects = [d for d in defects if d['category'] == DefectCategory.ANCHOR_MISMATCH]
    
    assert len(anchor_defects) > 0
    assert anchor_defects[0]['severity'] == DefectSeverity.CRITICAL.value
    assert "Expected one of" in anchor_defects[0]['message']

def test_req_res_01_anchor_match(gate_service):
    """
    REQ-RES-01: Valid translation should pass.
    """
    source = "Strongly Agree"
    target = "Tout à fait d'accord" # Valid
    
    constraints = {"archetype": "ANALYTICAL"}
    
    defects = gate_service.check_segment(source, target, constraints, "fr")
    
    anchor_defects = [d for d in defects if d['category'] == DefectCategory.ANCHOR_MISMATCH]
    assert len(anchor_defects) == 0

def test_req_res_02_sentiment_drift_fail(gate_service):
    """
    REQ-RES-02: Sentiment polarity shift.
    Source: "This is bad." (Negative)
    Target: "C'est bien." (Positive) -> FAIL
    """
    # Note: Our simple heuristic checks for 'negative markers'.
    # "bad" is in NEGATIVE_MARKERS['en'].
    # "bien" is NOT in NEGATIVE_MARKERS['fr'].
    # So Source=Neg=1, Target=Neg=0 -> Mismatch.
    
    source = "This result is bad."
    target = "Ce résultat est bien." 
    
    constraints = {"archetype": "ANALYTICAL"}
    
    defects = gate_service.check_segment(source, target, constraints, "fr")
    
    sentiment_defects = [d for d in defects if d['category'] == DefectCategory.SENTIMENT_SHIFT]
    assert len(sentiment_defects) > 0
    assert sentiment_defects[0]['severity'] == DefectSeverity.MAJOR.value

def test_req_res_02_sentiment_match(gate_service):
    """
    REQ-RES-02: Polarity match should pass.
    """
    source = "This result is bad."
    target = "Ce résultat est mauvais." # "mauvais" is in NEGATIVE_MARKERS['fr']
    
    constraints = {"archetype": "ANALYTICAL"}
    
    defects = gate_service.check_segment(source, target, constraints, "fr")
    
    sentiment_defects = [d for d in defects if d['category'] == DefectCategory.SENTIMENT_SHIFT]
    assert len(sentiment_defects) == 0

def test_analytical_inactive_for_safety_archetype(gate_service):
    """
    Ensure Analytical checks don't fire for Safety archetype unless specified.
    """
    source = "Strongly Agree"
    target = "D'accord" # Mismatch
    
    constraints = {"archetype": "SAFETY_CRITICAL"} # Not ANALYTICAL
    
    defects = gate_service.check_segment(source, target, constraints, "fr")
    
    anchor_defects = [d for d in defects if d['category'] == DefectCategory.ANCHOR_MISMATCH]
    assert len(anchor_defects) == 0

if __name__ == "__main__":
    pytest.main([__file__])
