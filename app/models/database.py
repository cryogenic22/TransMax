"""
TransMax Platform v2.0 - Database Models
SQLAlchemy ORM models for Document, Segment, and ChangeLog.
Compatible with SQLAlchemy 2.0+ using Mapped[] annotations.
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

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
    
    # TMX-011: Idempotency
    client_request_id = Column(String(255), unique=True, index=True, nullable=True)
    
    # Metadata
    file_path = Column(String(512), nullable=True)  # Path to original file
    file_type = Column(String(50), nullable=True)   # pdf, docx, txt
    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    
    # Scores
    confidence_score = Column(Float, nullable=True)  # Average of all segments
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    
    # Gate results from the agent
    gate_results = Column(JSON, nullable=True)  # { units_ok, negation_ok, pii_redacted, ... }
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    segment = relationship("Segment", back_populates="change_logs")

    def __repr__(self):
        return f"<ChangeLog(id={self.id}, segment={self.segment_id}, created={self.created_at})>"


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
