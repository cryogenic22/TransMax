import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pydantic import ValidationError
from app.schemas.api_v1 import JobProfileRequest, JobCreateRequest
from app.core.profile_enums import TranslationArchetype, ContentRiskTier, OutputModality

def test_valid_profile_creation():
    """TMX-GOV-03: Accept valid Profile."""
    profile = JobProfileRequest(
        archetype=TranslationArchetype.SAFETY_CRITICAL,
        tier=ContentRiskTier.TIER_A,
        modality=OutputModality.NARRATIVE
    )
    assert profile.archetype == "SAFETY_CRITICAL"

def test_invalid_archetype_value():
    """Reject un-modeled archetype string."""
    with pytest.raises(ValidationError):
        JobProfileRequest(
            archetype="MARKETING_FLUFF", # Invalid
            tier=ContentRiskTier.TIER_C,
            modality=OutputModality.NARRATIVE
        )

def test_policy_violation_informational_tier_a():
    """Reject INFORMATIONAL + TIER_A combo."""
    with pytest.raises(ValueError) as excinfo:
        JobProfileRequest(
            archetype=TranslationArchetype.INFORMATIONAL,
            tier=ContentRiskTier.TIER_A, # Policy Violation
            modality=OutputModality.TECHNICAL
        )
    assert "Informational Archetype cannot be Tier A" in str(excinfo.value)

def test_full_request_integrity():
    """Verify nesting in JobCreateRequest."""
    req = JobCreateRequest(
        source_language="en",
        target_language="ja",
        request_id="req-test-1",
        domain="pharma",
        profile={
            "archetype": "ANALYTICAL",
            "tier": "TIER_B",
            "modality": "TECHNICAL"
        },
        text_content="Hello"
    )
    assert req.profile.archetype == TranslationArchetype.ANALYTICAL

if __name__ == "__main__":
    # Simple manual run shim
    try:
        test_valid_profile_creation()
        test_invalid_archetype_value()
        test_policy_violation_informational_tier_a()
        test_full_request_integrity()
        print("Contract Tests Passed")
    except Exception as e:
        print(f"Contract Tests Failed: {e}")
        exit(1)
