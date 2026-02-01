import pytest
from app.services.quality_gate import QualityGateService
from app.core.policy_definitions import ViolationType

def test_placeholder_integrity():
    """
    TMX-034: Verify strict placeholder preservation ({{var}}, [1]).
    """
    service = QualityGateService()
    # Using 'en' target which uses DefaultPack (impl covers all unless overridden)
    
    # CASE 1: Perfect Preservation
    src = "Click {{button}} to confirm [1]."
    tgt = "Cliquez sur {{button}} pour confirmer [1]."
    violations = service.check_segment(src, tgt, {}, "fr")
    assert len(violations) == 0
    
    # CASE 2: Dropped Placeholder
    src_drop = "Value is {{val}}."
    tgt_drop = "La valeur est..."
    violations = service.check_segment(src_drop, tgt_drop, {}, "fr")
    assert len(violations) == 1
    assert violations[0]['type'] == ViolationType.PLACEHOLDER_CORRUPTION.value
    assert "missing" in violations[0]['message']
    
    # CASE 3: Corrupted Placeholder (Case Sensitivity)
    src_case = "Value is {{val}}."
    tgt_case = "La valeur est {{Val}}."
    violations = service.check_segment(src_case, tgt_case, {}, "fr")
    assert len(violations) >= 1 # Might flag as missing {{val}} AND added {{Val}} (hallucination)
    # Counter logic: missing {{val}}, added {{Val}}. Both appended.
    # Check messages
    msgs = [v['message'] for v in violations]
    assert any("missing" in m for m in msgs)
    assert any("hallucinated" in m for m in msgs)

    # CASE 4: Reordering (Allowed)
    src_swap = "{{a}} then {{b}}."
    tgt_swap = "{{b}} puis {{a}}."
    violations = service.check_segment(src_swap, tgt_swap, {}, "fr")
    assert len(violations) == 0
    
    # CASE 5: Numeric Reference Corruption
    src_ref = "See [1] and [2]."
    tgt_ref = "Voir [1] et [1]." # Duplication/Missing [2]
    violations = service.check_segment(src_ref, tgt_ref, {}, "fr")
    assert len(violations) >= 1
    msgs = [v['message'] for v in violations]
    assert any("missing" in m and "[2]" in m for m in msgs)

if __name__ == "__main__":
    test_placeholder_integrity()
    print("PASS test_placeholder_integrity")
