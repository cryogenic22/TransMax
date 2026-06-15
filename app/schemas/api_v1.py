from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.profile_enums import (
    ContentRiskTier,
    OutputModality,
    TranslationArchetype,
    is_tier_archetype_compatible,
)

class JobProfileRequest(BaseModel):
    """
    TMX-GOV-03: Governance Profile.
    Defines the rigor level for the translation job.
    """
    archetype: TranslationArchetype = Field(..., description="Governance Archetype")
    tier: ContentRiskTier = Field(..., description="Risk Tier (A=Highest, C=Lowest)")
    modality: OutputModality = Field(..., description="Target format/modality")
    
    @field_validator('tier')
    @classmethod
    def validate_tier_archetype_compatibility(cls, v, info):
        """
        Enforce Governance Invariants at the Edge (TMX-SSOT-TIER: one predicate).
        Example: INFORMATIONAL cannot be TIER_A.
        """
        if 'archetype' in info.data and not is_tier_archetype_compatible(info.data['archetype'], v):
            raise ValueError("Informational Archetype cannot be Tier A (Critical).")
        return v

class JobCreateRequest(BaseModel):
    """
    TMX-010: Job Creation Schema.
    """
    source_language: str = Field(..., min_length=2, max_length=5, json_schema_extra={"example": "en"})
    target_language: str = Field(..., min_length=2, max_length=5, json_schema_extra={"example": "ja"})
    
    request_id: str = Field(..., description="Idempotency Key")
    
    # Nested strict profile
    profile: JobProfileRequest
    
    # Metadata
    domain: str = Field("pharma", description="Industry domain")
    
    # Content
    text_content: Optional[str] = None
    document_name: Optional[str] = "untitled.txt"
    
    # Async Callback
    webhook_url: Optional[HttpUrl] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "source_language": "en",
            "target_language": "fr",
            "request_id": "req-001",
            "profile": {
                "archetype": "SAFETY_CRITICAL",
                "tier": "TIER_A",
                "modality": "NARRATIVE"
            },
            "text_content": "Take 10mg daily.",
            "domain": "pharma"
        }
    })

class Alert(BaseModel):
    severity: str
    message: str

class ValidationSummary(BaseModel):
    critical_count: int
    major_count: int
    minor_count: int
    decision: str
    semantic_drift: Optional[int] = None

class JobResponse(BaseModel):
    """
    TMX-010: Job Status Response.
    """
    job_id: str
    status: str
    confidence_score: Optional[float] = None
    score_breakdown: Optional[Dict[str, float]] = None
    created_at: datetime
    estimated_completion: Optional[datetime] = None

class JobResult(BaseModel):
    """
    TMX-010: Final Result Payload.
    """
    job_id: str
    status: str
    original_filename: Optional[str]
    
    translated_text: Optional[str]
    quality_summary: ValidationSummary
    audit_id: Optional[str]
    
    completed_at: datetime

class AuditLogEntryResponse(BaseModel):
    sequence_index: int
    event_type: str
    timestamp: datetime
    entry_hash: str
    payload_summary: Optional[Dict[str, Any]]

class AuditBundleResponse(BaseModel):
    """
    TMX-020: Regulatory Audit Bundle Export.
    """
    audit_id: str
    job_id: str
    final_decision: str
    created_at: datetime
    
    chain_head_hash: str
    is_tampered: bool
    
    entries: List[AuditLogEntryResponse]

class AuditRecordResponse(BaseModel):
    """
    TMX-020: Detailed Audit Record View.
    """
    audit_id: str
    job_id: Optional[str]
    final_decision: Optional[str]
    versions: Dict[str, Optional[str]]
    hash_signature: Optional[str]
    full_payload: Optional[Dict[str, Any]] = None
    created_at: datetime


class VerifyFinding(BaseModel):
    """
    TMX-3105: One defect surfaced by the v2 audit verifier.

    Mirrors `app.services.audit_verifier_v2.EventReport`. Wire format is
    stable: the regulator-facing reviewer reads `finding` as the
    machine-stable classifier string and `detail` as human prose.
    """
    event_id: str
    sequence_index: int
    finding: str = Field(
        ...,
        description=(
            "One of: ok, tampered_payload, tampered_event_hash, "
            "broken_chain, sequence_gap, sequence_duplicate, "
            "invalid_hash_length, genesis_violation."
        ),
    )
    detail: Optional[str] = None


class AuditVerificationResponse(BaseModel):
    """
    TMX-3105: Independent verification result for a v2 audit chain.

    `ok` is true iff the verifier found zero defects across the chain.
    A3-loud: a tampered chain returns `ok=False` with populated
    `findings`, NEVER an empty findings list with `ok=True`.

    TMX-3105a: `status` is a single machine-stable headline the reviewer UI
    renders as a badge without parsing the findings array; `chain_head_hash`
    is the hex `event_hash` of the latest event, the value a regulator
    anchors against the daily Merkle root / external timestamp.
    """
    ok: bool = Field(..., description="True iff zero defects detected.")
    status: str = Field(
        ...,
        description=(
            "Headline verdict: OK (clean) | TAMPERED (hash/payload/chain "
            "defect) | SEQUENCE_GAP (missing or duplicate sequence) | EMPTY "
            "(no events). Derived from findings; `ok == (status == 'OK')`."
        ),
    )
    organization_id: str
    job_id: str
    event_count: int
    ok_count: int
    chain_head_hash: Optional[str] = Field(
        None,
        description="Hex event_hash of the highest-sequence event; null for an empty chain.",
    )
    findings: List[VerifyFinding] = Field(default_factory=list)


class OrgChainSummary(BaseModel):
    """TMX-VERIFY-ORG: one job's verdict in an org-wide verification sweep."""
    job_id: str
    ok: bool
    status: str = Field(..., description="OK | TAMPERED | SEQUENCE_GAP | EMPTY")
    event_count: int
    ok_count: int


class OrgAuditVerificationResponse(BaseModel):
    """
    TMX-VERIFY-ORG: independent verification of EVERY v2 chain owned by the
    current tenant, in one regulator-facing call.

    `all_ok` is the single gate a compliance dashboard reads: true iff every
    chain verified clean. A3-loud: any tampered/gapped chain flips `all_ok`
    to false and is itemised in `chains`.
    """
    organization_id: str
    total_chains: int
    ok_chains: int
    all_ok: bool
    chains: List[OrgChainSummary] = Field(default_factory=list)

