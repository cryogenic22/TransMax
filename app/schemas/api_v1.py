from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.profile_enums import TranslationArchetype, ContentRiskTier, OutputModality

class JobProfileRequest(BaseModel):
    """
    TMX-GOV-03: Governance Profile.
    Defines the rigor level for the translation job.
    """
    archetype: TranslationArchetype = Field(..., description="Governance Archetype")
    tier: ContentRiskTier = Field(..., description="Risk Tier (A=Highest, C=Lowest)")
    modality: OutputModality = Field(..., description="Target format/modality")
    
    @validator('tier')
    def validate_tier_archetype_compatibility(cls, v, values):
        """
        Enforce Governance Invariants at the Edge.
        Example: INFORMATIONAL cannot be TIER_A.
        """
        if 'archetype' in values:
            arch = values['archetype']
            if arch == TranslationArchetype.INFORMATIONAL and v == ContentRiskTier.TIER_A:
                raise ValueError("Informational Archetype cannot be Tier A (Critical).")
        return v

class JobCreateRequest(BaseModel):
    """
    TMX-010: Job Creation Schema.
    """
    source_language: str = Field(..., min_length=2, max_length=5, example="en")
    target_language: str = Field(..., min_length=2, max_length=5, example="ja")
    
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
    
    class Config:
        schema_extra = {
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
        }

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

