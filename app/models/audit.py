from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.models.database import Base

class AuditRecord(Base):
    __tablename__ = "audit_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_trail_id = Column(UUID(as_uuid=True), index=True, nullable=False)  # Shared ID across related records
    
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    tenant_id = Column(String) # Optional tenant identifier
    
    # Context
    job_id = Column(UUID(as_uuid=True), ForeignKey("translation_jobs.id"))
    request_type = Column(String) # translation, review, feedback
    
    # Versioning snapshot
    versions_snapshot = Column(JSON) # model version, prompt version, policy version, glossary version
    
    # Inputs & Outputs hashes (Data privacy)
    input_hash = Column(String, index=True)
    output_hash = Column(String)
    
    # Decision
    decision = Column(String) # PASS, REVIEW_REQUIRED, BLOCKED
    composite_scores = Column(JSON) # {safety: 0.99, terminology: 1.0}
    
    # Structured Log
    event_type = Column(String) # GATE_CHECK, TRANSLATION_GENERATED, REFINEMENT_LOOP
    details_json = Column(JSON) # The full structured log content
    
    # Timestamps
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Integrity
    record_hash = Column(String) # Hash of this record's content for immutability check
    signature = Column(String) # Optional cryptographic signature
    
    # Relationships
    job = relationship("TranslationJob")
