"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


# --- Enums (mirror SQLAlchemy enums) ---

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


# --- Document Schemas ---

class DocumentCreate(BaseModel):
    """Schema for creating a document (metadata only, file uploaded separately)."""
    name: str = Field(..., min_length=1, max_length=255)
    source_language: str = Field(default="en", max_length=10)
    target_language: Optional[str] = Field(default=None, max_length=10)

class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    target_language: Optional[str] = Field(None, max_length=10)
    status: Optional[DocumentStatus] = None
    glossary_id: Optional[str] = None

class DocumentResponse(BaseModel):
    """Schema for document responses."""
    id: str
    name: str
    source_language: str
    target_language: Optional[str]
    status: DocumentStatus
    file_path: Optional[str]
    file_type: Optional[str]
    page_count: Optional[int]
    word_count: Optional[int]
    confidence_score: Optional[float]
    glossary_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    segment_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


# --- Segment Schemas ---

class SegmentResponse(BaseModel):
    """Schema for segment responses."""
    id: str
    document_id: str
    order_index: int
    source_text: str
    translated_text: Optional[str]
    confidence_score: Optional[float]
    status: SegmentStatus
    gate_results: Optional[Dict[str, Any]]
    # Quality scoring fields from Reflexion
    validation_score: Optional[float] = None  # Semantic drift score from back-translation (0-100)
    reverse_translation: Optional[str] = None  # Back-translation text
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SegmentUpdate(BaseModel):
    """Schema for updating a segment's translation."""
    translated_text: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for the edit")

class SegmentReverseRequest(BaseModel):
    """Schema for reverse translation request."""
    # Empty for now, uses existing translated_text
    pass

class SegmentReverseResponse(BaseModel):
    """Schema for reverse translation response."""
    segment_id: str
    original_source: str
    translated_text: str
    reverse_translation: str


# --- ChangeLog Schemas ---

class ChangeLogResponse(BaseModel):
    """Schema for change log responses."""
    id: str
    segment_id: str
    original_text: str
    new_text: str
    reason: str
    user_id: Optional[str]
    user_name: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Translation Job Schemas ---

class TranslationJobRequest(BaseModel):
    """Schema for triggering a translation job."""
    target_language: str = Field(..., min_length=2, max_length=10)
    segment_ids: Optional[List[str]] = Field(None, description="Optional list of segment IDs to translate. If omitted, all segments are translated.")

class TranslationJobResponse(BaseModel):
    """Schema for translation job response."""
    document_id: str
    status: str
    message: str


# --- Glossary Schemas (Future) ---

class GlossaryTermCreate(BaseModel):
    source_term: str
    target_term: str
    language_pair: str  # e.g., "en-fr"

class GlossaryTermResponse(BaseModel):
    id: str
    source_term: str
    target_term: str
    language_pair: str
    created_at: datetime
