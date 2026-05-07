"""
TransMax Platform v2.0 - Database Models
SQLAlchemy ORM models for Document, Segment, and ChangeLog.
Compatible with SQLAlchemy 2.0+ using Mapped[] annotations.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship, declarative_base

from app.models.types import GUID

Base = declarative_base()

# Identity of the seeded "system" organization. TMX-3011 will backfill all
# existing rows to this id before flipping organization_id NOT NULL.
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Allowed values for Organization.org_kind. Kept in code so callers can
# reference the canonical set without re-deriving from the CheckConstraint.
ORG_KINDS = ("system", "customer", "partner")

# --- Enums ---

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSLATED = "translated"
    IN_REVIEW = "in_review"
    APPROVED = "approved"

class SegmentStatus(str, Enum):
    PENDING = "pending"
    TRANSLATED = "translated"
    EDITED = "edited"
    APPROVED = "approved"
    BLOCKED = "blocked"

# --- Models ---

class Organization(Base):
    """
    Tenant root. Every domain row hangs off an organization (TMX-3011 wires
    the FK on each table). The seeded `system` org with id DEFAULT_ORG_ID
    owns historical rows that pre-date multi-tenancy.
    """
    __tablename__ = "organizations"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    org_kind = Column(String(32), nullable=False, default="customer")
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "org_kind IN ('system','customer','partner')",
            name="ck_organizations_org_kind",
        ),
    )

    def __repr__(self):
        return f"<Organization(id={self.id}, slug='{self.slug}', kind={self.org_kind})>"


class Document(Base):
    """
    Represents an uploaded document for translation.
    """
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    source_language = Column(String(10), nullable=False, default="en")
    target_language = Column(String(10), nullable=True)
    status = Column(String(50), default=DocumentStatus.UPLOADED.value, nullable=False)
    
    # Glossary binding
    glossary_id = Column(String, nullable=True)

    # Profile / metadata (stored as JSON for governance)
    meta_json = Column(JSON, nullable=True)

    # TMX-011: Idempotency
    client_request_id = Column(String(255), unique=True, index=True, nullable=True)
    
    # Metadata
    file_path = Column(String(512), nullable=True)  # Path to original file
    file_type = Column(String(50), nullable=True)   # pdf, docx, txt
    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    
    # Scores
    confidence_score = Column(Float, nullable=True)  # Average of all segments

    # Financial metrics (Feature 5)
    total_tokens = Column(Integer, nullable=True, default=0)
    total_cost_usd = Column(Float, nullable=True, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships (use string reference to avoid circular import issues)
    segments = relationship("Segment", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, name='{self.name}', status={self.status})>"


class Segment(Base):
    """
    Represents a single translatable segment within a document.
    """
    __tablename__ = "segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)  # Position in document
    
    # Content
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)
    
    # Quality
    confidence_score = Column(Float, nullable=True)
    status = Column(String(50), default=SegmentStatus.PENDING.value, nullable=False)
    
    # Source Tracking (Sprint 3)
    translation_source = Column(String(20), default="LLM", nullable=False) # LLM, TM_EXACT, TM_FUZZY, HUMAN
    match_score = Column(Float, nullable=True) # TM Similarity Score (0-1)
    
    # Reflexion (Sprint D)
    reverse_translation = Column(Text, nullable=True) # Back-translation
    validation_score = Column(Float, nullable=True)   # Semantic Similarity (0-1)
    
    # DOCX element tracking
    element_type = Column(String(50), nullable=True)  # Paragraph, TableCell, Header, Footer, Footnote, Endnote, TextBox
    element_meta = Column(JSON, nullable=True)  # e.g. {"section_idx": 0, "variant": "default"}

    # Gate results from the agent
    gate_results = Column(JSON, nullable=True)  # { units_ok, negation_ok, pii_redacted, ... }
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="segments")
    change_logs = relationship("ChangeLog", back_populates="segment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Segment(id={self.id}, doc={self.document_id}, order={self.order_index}, status={self.status})>"


class ChangeLog(Base):
    """
    Audit trail for segment edits. Captures original text, new text, and reason.
    """
    __tablename__ = "change_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id = Column(String(36), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Change details
    original_text = Column(Text, nullable=False)
    new_text = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)  # Mandatory reason for change
    
    # User (optional, for future auth)
    user_id = Column(String(36), nullable=True)
    user_name = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    segment = relationship("Segment", back_populates="change_logs")

    def __repr__(self):
        return f"<ChangeLog(id={self.id}, segment={self.segment_id}, created={self.created_at})>"


class DeletionRecord(Base):
    """
    Permanent audit record created before a document is deleted.
    Captures a snapshot of the document metadata for forensic purposes.
    """
    __tablename__ = "deletion_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), nullable=False, index=True)
    document_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)
    source_language = Column(String(10), nullable=True)
    target_language = Column(String(10), nullable=True)
    segment_count = Column(Integer, nullable=False, default=0)
    status_before_delete = Column(String(50), nullable=False)
    deleted_by = Column(String(36), nullable=True)
    reason = Column(Text, nullable=True)
    deleted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    metadata_snapshot = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<DeletionRecord(id={self.id}, doc={self.document_id}, deleted_at={self.deleted_at})>"


# --- Database Setup ---

def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)

def drop_tables(engine):
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)


# --- Backward Compatibility Re-exports ---
# Legacy db_service.py imports these from here. Re-export from core.database.
from app.core.database import engine, SessionLocal, get_db_session
