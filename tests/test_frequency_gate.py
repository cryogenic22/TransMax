import pytest
from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory

def test_frequency_gate_tmx031():
    """
    TMX-031: Verify Canonical Frequency Matching (BID == 2x/day).
    """
    service = QualityGateService()

    # CASE 1: BID (2) -> Deux fois (2) [MATCH]
    src_bid = "Take medication BID."
    tgt_fr = "Prendre le médicament deux fois par jour."
    violations = service.check_segment(src_bid, tgt_fr, {}, "fr")
    freq_violations = [v for v in violations if v['category'] == DefectCategory.FREQUENCY_MISMATCH.value]
    assert len(freq_violations) == 0

    # CASE 2: QD (1) -> Une fois (1) [MATCH]
    src_qd = "Apply cream QD."
    tgt_qd = "Appliquer la crème une fois par jour."
    violations = service.check_segment(src_qd, tgt_qd, {}, "fr")
    freq_violations = [v for v in violations if v['category'] == DefectCategory.FREQUENCY_MISMATCH.value]
    assert len(freq_violations) == 0

    # CASE 3: Mismatch (BID=2 vs une fois=1) [FAIL]
    src_fail = "Take medication BID."
    tgt_fail = "Prendre le médicament une fois par jour."
    violations = service.check_segment(src_fail, tgt_fail, {}, "fr")
    freq_violations = [v for v in violations if v['category'] == DefectCategory.FREQUENCY_MISMATCH.value]
    assert len(freq_violations) >= 1

    # CASE 4: Source has frequency, target dropped it [FAIL]
    src_daily = "Take once daily."
    tgt_zero = "Prendre..."
    violations = service.check_segment(src_daily, tgt_zero, {}, "fr")
    freq_violations = [v for v in violations if v['category'] == DefectCategory.FREQUENCY_MISMATCH.value]
    assert len(freq_violations) >= 1

    # CASE 5: Hallucination - target adds frequency not in source [FAIL]
    src_none = "Hello world."
    tgt_add = "Bonjour deux fois par jour."
    violations = service.check_segment(src_none, tgt_add, {}, "fr")
    freq_violations = [v for v in violations if v['category'] == DefectCategory.FREQUENCY_MISMATCH.value]
    assert len(freq_violations) > 0

if __name__ == "__main__":
    test_frequency_gate_tmx031()
    print("PASS test_frequency_gate_tmx031")
