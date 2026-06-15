
from enum import Enum

class TranslationArchetype(str, Enum):
    """
    The 5 Translation Rigor Archetypes defining base invariants.
    """
    SAFETY_CRITICAL = "SAFETY_CRITICAL"   # Regulated Narrative, Patient Safety
    ANALYTICAL = "ANALYTICAL"             # Research, Psychometric Equivalence
    OPERATIONAL = "OPERATIONAL"           # Execution, Manufacturing, Logistics
    LEGAL = "LEGAL"                       # Contractual, Liability
    INFORMATIONAL = "INFORMATIONAL"       # Corporate, Training

class ContentRiskTier(str, Enum):
    """
    Scaling mechanism for rigor within an archetype.
    """
    TIER_A = "TIER_A" # Zero Tolerance (Safety/Obligation)
    TIER_B = "TIER_B" # High Standard (Important/Clinical)
    TIER_C = "TIER_C" # Basic Standard (Informational)

class OutputModality(str, Enum):
    """
    Format fidelity requirements.
    """
    RICH_TEXT = "RICH_TEXT"         # Standard HTML/RTF
    MARKDOWN_TABLE = "MARKDOWN_TABLE" # strict table structure
    XML_STRICT = "XML_STRICT"       # Tag preservation
    PLAIN_TEXT = "PLAIN_TEXT"       # No formatting constraints
    NARRATIVE = "NARRATIVE"         # Flowing text
    TECHNICAL = "TECHNICAL"         # Concise technical specs

class IndustryDomain(str, Enum):
    """
    Industry-specific data packs.
    """
    PHARMA = "PHARMA"
    MEDTECH = "MEDTECH"
    GENERAL = "GENERAL"


def is_tier_archetype_compatible(
    archetype: TranslationArchetype, tier: ContentRiskTier
) -> bool:
    """Single source of truth for the tier↔archetype governance invariant
    (TMX-SSOT-TIER): an INFORMATIONAL archetype cannot be the zero-tolerance
    TIER_A. Both the live API-edge validator (`api_v1.JobProfileRequest`) and the
    legacy `profile_resolver` call this — the rule lives in ONE place, not two."""
    return not (
        archetype == TranslationArchetype.INFORMATIONAL
        and tier == ContentRiskTier.TIER_A
    )
