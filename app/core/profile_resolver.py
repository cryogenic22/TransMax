
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from app.core.profile_enums import TranslationArchetype, ContentRiskTier, OutputModality, IndustryDomain

@dataclass
class JobProfile:
    """
    Resolved configuration for a translation job.
    Composition: Archetype + Industry + Language + Modality + Tier
    """
    archetype: TranslationArchetype
    industry: IndustryDomain
    source_language: str
    target_language: str
    modality: OutputModality
    tier: ContentRiskTier
    
    # Computed constraints based on the composition
    invariants: Dict[str, Any] = field(default_factory=dict)
    
    def is_safety_critical(self) -> bool:
        return self.archetype == TranslationArchetype.SAFETY_CRITICAL

def resolve_job_profile(metadata: Dict[str, Any]) -> JobProfile:
    """
    Resolves the JobProfile based on input metadata.
    Applies defaults and validates constraints.
    """
    
    # 1. Parse Basic Enums (with defaults)
    try:
        archetype = TranslationArchetype(metadata.get("archetype", TranslationArchetype.SAFETY_CRITICAL))
    except ValueError:
        raise ValueError(f"Invalid Archetype: {metadata.get('archetype')}")
        
    try:
        industry = IndustryDomain(metadata.get("industry", IndustryDomain.PHARMA))
    except ValueError:
        raise ValueError(f"Invalid Industry: {metadata.get('industry')}")
        
    try:
        modality = OutputModality(metadata.get("modality", OutputModality.RICH_TEXT))
    except ValueError:
        raise ValueError(f"Invalid Modality: {metadata.get('modality')}")
        
    try:
        tier = ContentRiskTier(metadata.get("tier", ContentRiskTier.TIER_A))
    except ValueError:
        raise ValueError(f"Invalid Tier: {metadata.get('tier')}")
        
    source_lang = metadata.get("source_language", "en")
    target_lang = metadata.get("target_language")
    
    if not target_lang:
        raise ValueError("Target language is required.")

    # 2. Apply Governance Rules (Constraint Validation)
    
    # Rule: Informational Archetype cannot be Tier A
    if archetype == TranslationArchetype.INFORMATIONAL and tier == ContentRiskTier.TIER_A:
        # Auto-downgrade or Error? For validation rigor, we Error.
        raise ValueError("Governance Violation: Informational Archetype cannot be Tier A.")

    # 3. Construct Profile
    profile = JobProfile(
        archetype=archetype,
        industry=industry,
        source_language=source_lang,
        target_language=target_lang,
        modality=modality,
        tier=tier
    )
    
    # 4. Populate Invariants (Placeholder for future complexity)
    # This is where we would load specific rules from the IndustryPack later
    if profile.is_safety_critical():
        profile.invariants["numeric_fidelity"] = "STRICT"
        profile.invariants["negation_check"] = "CRITICAL"
    
    return profile
