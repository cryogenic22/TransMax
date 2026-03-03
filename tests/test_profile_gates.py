
import pytest
from app.services.quality_gate import QualityGateService
from app.core.regulatory_profiles import REGULATORY_PROFILES

def test_date_formatting_ema():
    gate = QualityGateService()
    profile_id = "EMA_SMPC_EN_GB"

    # Valid Case (DD/MM/YYYY)
    text_ok = "Date of revision: 01/12/2025"
    violations = gate.check_segment("source", text_ok, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'FORMATTING_ERROR' for v in violations)

    # Invalid Case (Month=30 is impossible for DD/MM/YYYY)
    text_fail_ddmm = "Date: 01/30/2025"
    violations = gate.check_segment("source", text_fail_ddmm, {}, "en", profile_id=profile_id)
    assert any(v['category'] == 'FORMATTING_ERROR' for v in violations)
    assert "required format" in str(violations)

def test_date_formatting_fda():
    gate = QualityGateService()
    profile_id = "FDA_PI_EN_US"

    # Valid (MM/DD/YYYY)
    text_ok = "Revised: 01/30/2025"
    violations = gate.check_segment("source", text_ok, {}, "en", profile_id=profile_id)
    assert not any(v['category'] == 'FORMATTING_ERROR' for v in violations)

    # Invalid (DD/MM/YYYY with day=30 in month slot)
    text_bad = "Revised: 30/01/2025"
    violations = gate.check_segment("source", text_bad, {}, "en", profile_id=profile_id)
    assert any(v['category'] == 'FORMATTING_ERROR' for v in violations)

def test_profile_loading_integration():
    gate = QualityGateService()
    # No profile -> No date format check
    text_bad = "Date: 30/01/2025"
    violations = gate.check_segment("source", text_bad, {}, "en", profile_id=None)
    assert not any(v['category'] == 'FORMATTING_ERROR' for v in violations)
