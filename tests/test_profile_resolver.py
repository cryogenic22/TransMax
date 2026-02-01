
import pytest
from app.core.profile_resolver import resolve_job_profile, JobProfile
from app.core.profile_enums import TranslationArchetype, ContentRiskTier, OutputModality, IndustryDomain

def test_resolve_standard_pharma_safety():
    """Verify standard safety-critical profile resolution."""
    meta = {
        "archetype": "SAFETY_CRITICAL",
        "industry": "PHARMA",
        "target_language": "fr",
        "modality": "RICH_TEXT",
        "tier": "TIER_A"
    }
    profile = resolve_job_profile(meta)
    
    assert profile.archetype == TranslationArchetype.SAFETY_CRITICAL
    assert profile.tier == ContentRiskTier.TIER_A
    assert profile.invariants["numeric_fidelity"] == "STRICT"
    assert profile.is_safety_critical() is True

def test_resolve_defaults():
    """Verify default values are applied correctly."""
    meta = {
        "target_language": "es"
    }
    profile = resolve_job_profile(meta)
    
    # Defaults: Safety Critical, Pharma, RichText, Tier A
    assert profile.archetype == TranslationArchetype.SAFETY_CRITICAL
    assert profile.industry == IndustryDomain.PHARMA
    assert profile.tier == ContentRiskTier.TIER_A

def test_governance_violation_informational_tier_a():
    """Verify that Informational Archetype cannot be Tier A."""
    meta = {
        "archetype": "INFORMATIONAL",
        "target_language": "de",
        "tier": "TIER_A"
    }
    
    with pytest.raises(ValueError, match="Governance Violation"):
        resolve_job_profile(meta)

def test_invalid_enum_handling():
    """Verify invalid enum values raise ValueError."""
    meta = {
        "archetype": "INVALID_ARCHETYPE",
        "target_language": "it"
    }
    with pytest.raises(ValueError, match="Invalid Archetype"):
        resolve_job_profile(meta)

if __name__ == "__main__":
    pytest.main([__file__])
