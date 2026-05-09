from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, ForeignKeyConstraint, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.models.database import Base
from app.models.types import GUID
from app.models.soft_delete import SoftDeleteMixin
from app.models.tenant_scoped import TenantScopedMixin

class TranslationRule(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    TMX-045: Knowledge System Rule (Black Book v2).
    Represents a learned translation rule with enterprise domain scoping.
    """
    __tablename__ = "translation_rules"

    rule_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)

    source_pattern = Column(String, nullable=False, index=True) # Text or Regex
    target_correction = Column(String, nullable=False)

    context_tag = Column(String, default="general") # e.g. "pharma", "legal"
    confidence_score = Column(Float, nullable=False) # 0.0 - 1.0 (AI Confidence)

    status = Column(String, default="PENDING_APPROVAL") # ACTIVE, PENDING_APPROVAL, REJECTED

    origin_event_id = Column(String, nullable=True) # Link to ChangeLog or Audit

    # --- Black Book v2: Domain Scoping ---
    source_language = Column(String, nullable=True, index=True)  # e.g. "en", None = any
    target_language = Column(String, nullable=True, index=True)  # e.g. "fr", None = any
    project_id = Column(String, nullable=True, index=True)       # Scope to project
    domain = Column(String, default="general", index=True)       # "pharma", "legal", "general"
    is_regex = Column(Boolean, default=False)                    # Pattern is regex vs literal
    is_strict = Column(Boolean, default=False)                   # Strict mode: block if violated
    priority = Column(Integer, default=0)                        # Higher = applied first
    description = Column(Text, nullable=True)                    # Human-readable explanation
    fire_count = Column(Integer, default=0)                      # Analytics: how often triggered
    last_fired_at = Column(DateTime, nullable=True)              # Analytics: last trigger time
    false_positive_count = Column(Integer, default=0)            # Analytics: reported false positives
    created_by = Column(String, nullable=True)                   # User who created the rule

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class TranslationJobQueue(TenantScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "translation_jobs_queue"

    job_id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="PENDING")
    
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    domain = Column(String, default="general")
    audience = Column(String, default="general")
    
    request_json = Column(JSON, nullable=False)
    state_json = Column(JSON, nullable=True) # Checkpoint of graph state
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # audit_trail_id removed to avoid circular dependency. AuditRecord links to Job via job_id.
    # Fully-qualified path: there is also an `AuditRecord` in app.models.audit
    # (the v3 audit_records table). TMX-3017 will rationalise. Until then SQLAlchemy
    # needs the dotted name to disambiguate.
    audit_record = relationship("app.models.models.AuditRecord", back_populates="job", uselist=False)
    config_snapshot = relationship("JobConfigSnapshot", back_populates="job", uselist=False)
    scorecard = relationship("QualityScorecard", back_populates="job", uselist=False)

class JobConfigSnapshot(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    TMX-010: Configuration Snapshot.
    Freezes the exact state of the world (prompts, profiles, parameters) for a job.
    Ensures reproducibility even if system config changes later.
    """
    __tablename__ = "job_config_snapshots"

    snapshot_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("translation_jobs_queue.job_id"), unique=True, nullable=False)
    
    # The frozen config blob
    config_json = Column(JSON, nullable=False)
    
    # Hash for integrity check
    config_hash = Column(String(64), nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    job = relationship("TranslationJobQueue", back_populates="config_snapshot")

class AuditLogEntry(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    TMX-021: Tamper-Evident Event Log.
    Each entry is cryptographically linked to the previous one (Blockchain-style).
    """
    __tablename__ = "audit_log_entries"

    entry_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    audit_id = Column(String, ForeignKey("audit_records_queue.audit_id"), nullable=False, index=True)
    
    sequence_index = Column(Integer, nullable=False) # 0, 1, 2...
    event_type = Column(String, nullable=False) # e.g., "JOB_STARTED", "GATE_PASSED"
    
    payload = Column(JSON, nullable=False)
    
    # Integrity
    previous_hash = Column(String(64), nullable=True) # Hash of the previous entry
    entry_hash = Column(String(64), nullable=False)   # Hash of (this_payload + previous_hash)
    
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    audit_trail = relationship("app.models.models.AuditRecord", back_populates="log_entries")

class QualityScorecard(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    TMX-030: Quality Scorecard.
    Persists pass/fail counts and drift scores per job.
    One scorecard per job (immutable once finalized).
    """
    __tablename__ = "quality_scorecards"

    scorecard_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("translation_jobs_queue.job_id"), unique=True, nullable=False)
    
    # Aggregated Metrics
    critical_defect_count = Column(Integer, default=0, nullable=False)
    major_defect_count = Column(Integer, default=0, nullable=False)
    minor_defect_count = Column(Integer, default=0, nullable=False)
    
    semantic_drift_score = Column(Integer, nullable=True) # 0-100 scale
    gate_pass_rate = Column(Integer, nullable=True)      # 0-100 scale
    
    status = Column(String, nullable=False) # PASS / BLOCK / REVIEW
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    job = relationship("TranslationJobQueue", back_populates="scorecard")
    entries = relationship("ScorecardEntry", back_populates="scorecard")

class ScorecardEntry(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    Granular defect entry linked to the scorecard.
    """
    __tablename__ = "scorecard_entries"

    entry_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    scorecard_id = Column(String, ForeignKey("quality_scorecards.scorecard_id"), nullable=False, index=True)
    
    segment_id = Column(String, nullable=True) # Could be document-level issue
    category = Column(String, nullable=False)   # From DefectCategory Enum
    severity = Column(String, nullable=False)   # From DefectSeverity Enum
    message = Column(String, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    scorecard = relationship("QualityScorecard", back_populates="entries")

class AuditRecord(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    The 'Head' of the Audit Trail.
    Now acts as the summary container.
    """
    __tablename__ = "audit_records_queue"

    audit_id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("translation_jobs_queue.job_id"), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    final_decision = Column(String, nullable=True)
    scores_json = Column(JSON, nullable=True)
    
    # Snapshot of resources used (Summary)
    model_version = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    glossary_version = Column(String, nullable=True)
    language_pack_version = Column(String, nullable=True)
    policy_version = Column(String, nullable=True)
    
    # Summary Hashes
    input_hash = Column(String(64), nullable=True)
    output_hash = Column(String(64), nullable=True)

    # The final "Seal" of the chain
    chain_head_hash = Column(String(64), nullable=True) # Matches the last AuditLogEntry hash

    # TMX-021: Tamper Evidence
    full_payload = Column(JSON, nullable=True)
    hash_signature = Column(String(64), nullable=True)
    events_json = Column(JSON, nullable=True)
    
    # Relationships
    job = relationship("TranslationJobQueue", back_populates="audit_record", foreign_keys=[job_id])
    log_entries = relationship("AuditLogEntry", back_populates="audit_trail", order_by="AuditLogEntry.sequence_index")

class Glossary(TenantScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "glossaries"

    glossary_id = Column(String, primary_key=True, index=True) # e.g., 'global_pharma_v2'
    version = Column(String, primary_key=True) # e.g., '2.4.0'
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)

    is_active = Column(Boolean, default=True)
    meta_json = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    terms = relationship("GlossaryTerm", back_populates="glossary")

class GlossaryTerm(TenantScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "glossary_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    glossary_id = Column(String, nullable=False)
    glossary_version = Column(String, nullable=False)
    
    term_id = Column(String, nullable=False)
    source_text = Column(String, nullable=False, index=True)
    target_text = Column(String, nullable=False)
    
    is_forbidden = Column(Boolean, default=False)
    allowed_variants = Column(JSON, default=list) # List of strings
    metadata_json = Column(JSON, nullable=True)
    
    __table_args__ = (
        ForeignKeyConstraint(
            ['glossary_id', 'glossary_version'],
            ['glossaries.glossary_id', 'glossaries.version'],
            ondelete="CASCADE",
        ),
        UniqueConstraint('glossary_id', 'glossary_version', 'source_text', name='uq_glossary_term_source'),
    )
    
    glossary = relationship("Glossary", 
        primaryjoin="and_(GlossaryTerm.glossary_id==Glossary.glossary_id, GlossaryTerm.glossary_version==Glossary.version)",
        back_populates="terms")

class TMSegment(TenantScopedMixin, SoftDeleteMixin, Base):
    __tablename__ = "tm_segments"

    # TM Identity
    tm_id = Column(String, nullable=False) # Grouping ID
    segment_hash = Column(String, primary_key=True, index=True) # Unique ID of this entry
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Content Integrity (Sprint 6)
    source_content_hash = Column(String(64), index=True, nullable=False) # SHA256(normalized_source)
    segmentation_version = Column(String(10), default="v1", nullable=False)
    normalization_version = Column(String(10), default="v1", nullable=False)
    
    source_text = Column(Text, nullable=False)
    target_text = Column(Text, nullable=False)
    
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    
    # Vector embedding
    embedding = Column(Vector(1536))
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    meta_json = Column(JSON, nullable=True)

class DeadLetterQueue(TenantScopedMixin, SoftDeleteMixin, Base):
    """
    TMX-OPS-04: Dead-Letter Queue (DLQ).
    Stores failed jobs/segments for forensic analysis.
    Prevents "poison pills" from blocking the queue.
    """
    __tablename__ = "dead_letter_queue"

    dlq_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(String, index=True, nullable=True) # Soft link to job
    
    error_code = Column(String, nullable=False) # e.g. "LLM_TIMEOUT", "PARSE_ERROR"
    error_trace = Column(Text, nullable=True)   # Full stack trace
    
    payload_snapshot = Column(JSON, nullable=False) # The input/state that caused the crash
    retry_count = Column(Integer, default=0)
    
    status = Column(String, default="NEW") # NEW, INVESTIGATING, RESOLVED, DISCARDED
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
