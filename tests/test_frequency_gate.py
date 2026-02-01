import pytest
from app.services.quality_gate import QualityGateService
from app.core.policy_definitions import ViolationType

def test_frequency_gate_tmx031():
    """
    TMX-031: Verify Canonical Frequency Matching (BID == 2x/day).
    """
    service = QualityGateService()
    
    # CASE 1: BID (2) -> Deux fois (2) [MATCH]
    src_bid = "Take medication BID."
    tgt_fr = "Prendre le médicament deux fois par jour."
    violations = service.check_segment(src_bid, tgt_fr, {}, "fr") # "fr" uses DefaultPack (fallback) but regexes are in DefaultPack
    assert len(violations) == 0
    
    # CASE 2: QD (1) -> Une fois (1) [MATCH]
    src_qd = "Apply cream QD."
    tgt_qd = "Appliquer la crème une fois par jour."
    assert len(service.check_segment(src_qd, tgt_qd, {}, "fr")) == 0
    
    # CASE 3: Mismatch (2 vs 1) [FAIL]
    src_fail = "Take medication BID."
    tgt_fail = "Prendre le médicament une fois par jour."
    violations = service.check_segment(src_fail, tgt_fail, {}, "fr")
    # Expect 2 violations: 1 missing (BID), 1 hallucinated (Une fois)
    assert len(violations) >= 1
    # Check for the mismatch logic
    msgs = [v['message'] for v in violations]
    assert any("Expected bid (2.0/day)" in m for m in msgs)
    assert any("Extra frequency" in m or "extra frequency" in m for m in msgs)
    
    # CASE 4: Mismatch (1 vs 3) [FAIL]
    src_daily = "Take once daily."
    tgt_zero = "Prendre..."
    violations = service.check_segment(src_daily, tgt_zero, {}, "fr")
    if len(violations) != 1:
        print(f"DEBUG CASE 4: Violations: {violations}")
    assert len(violations) == 1
    
    # CASE 5: Hallucination [FAIL]
    src_none = "Hello world."
    tgt_add = "Bonjour deux fois par jour."
    violations = service.check_segment(src_none, tgt_add, {}, "fr")
    assert len(violations) > 0
    assert "extra frequency" in violations[0]['message']

if __name__ == "__main__":
    test_frequency_gate_tmx031()
    print("PASS test_frequency_gate_tmx031")
