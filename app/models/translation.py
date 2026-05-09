from sqlalchemy import Column, String, DateTime, Integer, Float, JSON, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
import enum
from pgvector.sqlalchemy import Vector

from app.models.database import Base
from app.models.types import GUID
from app.models.soft_delete import SoftDeleteMixin


class TranslationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"


class TranslationProvider(str, enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPL = "deepl"
    GOOGLE = "google"
    AZURE = "azure"


class TranslationJob(SoftDeleteMixin, Base):
    __tablename__ = "translation_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source document reference (from digitization service)
    source_document_id = Column(UUID(as_uuid=True), nullable=False)
    # TMX-3011: GUID + FK; was bare UUID
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Translation configuration
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    provider = Column(Enum(TranslationProvider), nullable=False)
    model = Column(String)  # Specific model used
    
    # Job metadata
    title = Column(String)
    description = Column(Text)
    status = Column(Enum(TranslationStatus), default=TranslationStatus.PENDING)
    
    # Audit
    audit_trail_id = Column(UUID(as_uuid=True))
    
    # Configuration
    formality = Column(String)  # formal, informal, auto
    preserve_formatting = Column(Boolean, default=True)
    enable_glossary = Column(Boolean, default=False)
    glossary_id = Column(UUID(as_uuid=True))
    
    # Quality settings
    enable_back_translation = Column(Boolean, default=True)
    quality_check_enabled = Column(Boolean, default=True)
    human_review_required = Column(Boolean, default=False)
    
    # Metrics
    total_chunks = Column(Integer, default=0)
    completed_chunks = Column(Integer, default=0)
    average_confidence = Column(Float)
    processing_time = Column(Float)  # in seconds
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # User tracking
    created_by = Column(String)
    reviewed_by = Column(String)
    
    # Relationships
    chunk_translations = relationship("ChunkTranslation", back_populates="job", cascade="all, delete-orphan")
    quality_reports = relationship("QualityReport", back_populates="job", cascade="all, delete-orphan")


class ChunkTranslation(SoftDeleteMixin, Base):
    __tablename__ = "chunk_translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("translation_jobs.id"), nullable=False)

    # Source chunk reference
    source_chunk_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    
    # Translation content
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text)
    back_translated_text = Column(Text)  # For quality checking
    
    # Metadata
    chunk_type = Column(String)  # heading, paragraph, table, etc.
    confidence_score = Column(Float)
    
    # Quality indicators
    issues_detected = Column(JSON)  # List of detected issues
    human_review_required = Column(Boolean, default=False)
    review_notes = Column(Text)
    
    # Edit tracking
    original_translation = Column(Text)  # Before human edits
    edited = Column(Boolean, default=False)
    edited_by = Column(String)
    edited_at = Column(DateTime)
    
    # Processing metadata
    processing_time = Column(Float)  # in seconds
    token_count = Column(Integer)
    cost_estimate = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    job = relationship("TranslationJob", back_populates="chunk_translations")


class QualityReport(SoftDeleteMixin, Base):
    __tablename__ = "quality_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("translation_jobs.id"), nullable=False)

    # Overall metrics
    overall_confidence = Column(Float)
    consistency_score = Column(Float)
    terminology_accuracy = Column(Float)
    
    # Issue summary
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    
    # Detailed analysis
    issue_details = Column(JSON)
    terminology_mismatches = Column(JSON)
    consistency_issues = Column(JSON)
    
    # Recommendations
    recommendations = Column(JSON)
    chunks_requiring_review = Column(JSON)  # List of chunk IDs
    
    # Report metadata
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    report_version = Column(String, default="1.0")
    
    # Relationships
    job = relationship("TranslationJob", back_populates="quality_reports")


class TranslationGlossary(SoftDeleteMixin, Base):
    __tablename__ = "translation_glossaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # TMX-3011: GUID + FK; was bare UUID
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    description = Column(Text)
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    
    # Glossary entries
    entries = Column(JSON)  # List of {source: "", target: "", context: ""}
    
    # Metadata
    domain = Column(String)  # pharmaceutical, medical, regulatory
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(String)


class TranslationMemory(SoftDeleteMixin, Base):
    __tablename__ = "translation_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # TMX-3011: GUID + FK; was bare UUID
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Content
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    
    # Metadata
    domain = Column(String)
    document_type = Column(String)
    confidence_score = Column(Float)
    usage_count = Column(Integer, default=0)
    
    # Quality
    human_verified = Column(Boolean, default=False)
    quality_score = Column(Float)
    
    # Source tracking
    source_document_id = Column(UUID(as_uuid=True))
    source_chunk_id = Column(UUID(as_uuid=True))
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime)
    verified_at = Column(DateTime)
    verified_by = Column(String)
    
    # Embedding for semantic search (1536 dims for text-embedding-3-small/ada-002)
    embedding = Column(Vector(1536))
    

class LanguagePack(Base):
    __tablename__ = "language_packs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pack_id = Column(String, unique=True, nullable=False)  # e.g., "ar_pack", "ja_pack"
    version = Column(String, nullable=False)
    
    # Configuration
    script_direction = Column(String, default="ltr")  # ltr, rtl
    config_json = Column(JSON, nullable=False)  # rules, tokeniser settings
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))