import pytest
from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory

def test_placeholder_integrity():
    """
    TMX-034: Verify strict placeholder preservation ({{var}}, [1]).
    """
    service = QualityGateService()

    # CASE 1: Perfect Preservation
    src = "Click {{button}} to confirm [1]."
    tgt = "Cliquez sur {{button}} pour confirmer [1]."
    violations = service.check_segment(src, tgt, {}, "fr")
    ph_violations = [v for v in violations if v['category'] == DefectCategory.PLACEHOLDER_CORRUPTION.value]
    assert len(ph_violations) == 0

    # CASE 2: Dropped Placeholder
    src_drop = "Value is {{val}}."
    tgt_drop = "La valeur est..."
    violations = service.check_segment(src_drop, tgt_drop, {}, "fr")
    ph_violations = [v for v in violations if v['category'] == DefectCategory.PLACEHOLDER_CORRUPTION.value]
    assert len(ph_violations) >= 1
    assert any("missing" in v['message'].lower() for v in ph_violations)

    # CASE 3: Corrupted Placeholder (Case Sensitivity)
    src_case = "Value is {{val}}."
    tgt_case = "La valeur est {{Val}}."
    violations = service.check_segment(src_case, tgt_case, {}, "fr")
    ph_violations = [v for v in violations if v['category'] == DefectCategory.PLACEHOLDER_CORRUPTION.value]
    assert len(ph_violations) >= 1
    msgs = [v['message'] for v in ph_violations]
    assert any("missing" in m.lower() for m in msgs)
    assert any("hallucinated" in m.lower() for m in msgs)

    # CASE 4: Reordering (Allowed)
    src_swap = "{{a}} then {{b}}."
    tgt_swap = "{{b}} puis {{a}}."
    violations = service.check_segment(src_swap, tgt_swap, {}, "fr")
    ph_violations = [v for v in violations if v['category'] == DefectCategory.PLACEHOLDER_CORRUPTION.value]
    assert len(ph_violations) == 0

    # CASE 5: Numeric Reference Corruption
    src_ref = "See [1] and [2]."
    tgt_ref = "Voir [1] et [1]."
    violations = service.check_segment(src_ref, tgt_ref, {}, "fr")
    ph_violations = [v for v in violations if v['category'] == DefectCategory.PLACEHOLDER_CORRUPTION.value]
    assert len(ph_violations) >= 1
    msgs = [v['message'] for v in ph_violations]
    assert any("missing" in m.lower() and "[2]" in m for m in msgs)

if __name__ == "__main__":
    test_placeholder_integrity()
    print("PASS test_placeholder_integrity")
