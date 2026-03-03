
import pytest
from app.services.quality_gate import QualityGateService

def test_mandatory_headers_ema():
    gate = QualityGateService()
    profile_id = "EMA_SMPC_EN_GB"

    # 1. Valid Header (Exact Match)
    text_ok = "1. NAME OF THE MEDICINAL PRODUCT"
    violations = gate.check_segment("source", text_ok, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'STRUCTURE_ERROR' for v in violations)

    # 2. Invalid Header (Wrong Terminology)
    text_bad = "1. NAME OF THE DRUG"
    violations = gate.check_segment("source", text_bad, {}, "en", profile_id=profile_id)
    assert any(v['category'] == 'STRUCTURE_ERROR' for v in violations)
    assert "Non-standard header" in str(violations)

    # 3. Invalid Header (Typo)
    text_typo = "1. NAME OF MEDICINAL PRODUCT"
    violations = gate.check_segment("source", text_typo, {}, "en", profile_id=profile_id)
    assert any(v['category'] == 'STRUCTURE_ERROR' for v in violations)

    # 4. Normal Text (Should be ignored)
    text_normal = "This product differs from the original."
    violations = gate.check_segment("source", text_normal, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'STRUCTURE_ERROR' for v in violations)

def test_marketing_mode_headers():
    gate = QualityGateService()
    profile_id = "MARKETING_GLOBAL_EN"

    text_loose = "1. NAME OF THE DRUG"
    violations = gate.check_segment("source", text_loose, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'STRUCTURE_ERROR' for v in violations)

def test_header_detection_heuristics():
    gate = QualityGateService()
    profile_id = "EMA_SMPC_EN_GB"

    # Mixed case doesn't match header regex, so no check triggered
    text_mixed = "1. Introduction"
    violations = gate.check_segment("source", text_mixed, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'STRUCTURE_ERROR' for v in violations)
