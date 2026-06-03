"""
TransMax Platform v2.0 - Document API Router
CRUD operations for documents and translation jobs.
"""
import os
import uuid
import aiofiles
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.model_pricing import cost_for
from app.models.database import Document, Segment, DeletionRecord, DocumentStatus, SegmentStatus
from app.api.schemas import (
    DocumentUpdate, DocumentResponse, DocumentListResponse,
    TranslationJobRequest, TranslationJobResponse
)
from app.services.pdf_service import PDFService
from app.auth.providers import AuthenticatedIdentity
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permission

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# --- Constants ---
# Use /tmp/uploads in containers (writable by non-root), fallback to project-relative locally
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- Helper Functions ---

def document_to_response(doc: Document, db: Session) -> DocumentResponse:
    """Convert ORM model to response schema."""
    segment_count = db.query(func.count(Segment.id)).filter(Segment.document_id == doc.id).scalar()
    return DocumentResponse(
        id=doc.id,
        name=doc.name,
        source_language=doc.source_language,
        target_language=doc.target_language,
        status=doc.status,
        file_path=doc.file_path,
        file_type=doc.file_type,
        page_count=doc.page_count,
        word_count=doc.word_count,
        confidence_score=doc.confidence_score,
        glossary_id=doc.glossary_id,
        total_tokens=doc.total_tokens,
        total_cost_usd=doc.total_cost_usd,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        segment_count=segment_count
    )


# --- Endpoints ---



# ... (imports)

@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    source_language: str = "en",
    target_language: Optional[str] = None,
    glossary_id: Optional[str] = Query(None, description="Optional glossary ID to bind"),
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.DOCUMENT_CREATE)),
):
    """
    Upload a new document, digitize it (extract text segments), and store in DB.
    """
    # TMX-3705: validate magic bytes + size cap + AV trigger.
    from app.services.file_validation import validate_and_save_upload

    file_ext = os.path.splitext(file.filename)[1].lower()
    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    await validate_and_save_upload(
        upload_file=file,
        dest_path=file_path,
        allowed_extensions=(".pdf", ".docx", ".txt"),
        av_metadata={"doc_id": doc_id, "uploaded_by": str(user.user_id)},
    )
    
    # Ingest / Digitize Content
    ingest_service = PDFService()
    try:
        if file_ext == ".pdf":
            # PDF extraction might still be blocking (PyPDF/Unstructured), so run in threadpool?
            # For now, we assume PDFService is synchronous.
            # Ideally: await run_in_threadpool(ingest_service.extract_text, file_path)
            blocks = ingest_service.extract_text(file_path)
        elif file_ext == ".docx":
            from app.services.docx_ingestion import DocxIngestionService
            blocks = DocxIngestionService().extract_blocks(file_path)
        else:
            # TXT fallback - split by paragraphs (double newline)
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            blocks = [{"text": p, "type": "PlainText"} for p in paragraphs] if paragraphs else [{"text": content, "type": "PlainText"}]
    except Exception as e:
        print(f"Ingestion failed: {e}")
        # Non-blocking failure? Or fail request?
        # For now, create doc but with warning log
        blocks = []

    # Get file size and word count
    # Async I/O for size check not cleanly available in os.path, but stat is fast.
    # os.path.getsize(file_path) 

    total_words = sum(len(b["text"].split()) for b in blocks)
    
    # Create document record. TMX-3012c: organization_id auto-injected from
    # request-scoped tenant context (TenantContextMiddleware → mixin listener).
    doc = Document(
        id=doc_id,
        name=name or file.filename,
        source_language=source_language,
        target_language=target_language,
        glossary_id=glossary_id,
        status=DocumentStatus.UPLOADED.value,
        file_path=file_path,
        file_type=file_ext.replace(".", ""),
        word_count=total_words,
        page_count=len(blocks) if file_ext == ".pdf" else 1 # Rough proxy
    )
    
    db.add(doc)
    
    # Create Segment records from parsed blocks
    for idx, block in enumerate(blocks):
        clean_text = block["text"].strip()
        if not clean_text:
            continue
            
        segment = Segment(
            document_id=doc_id,
            order_index=idx + 1,
            source_text=clean_text,
            element_type=block.get("type"),
            element_meta=block.get("meta"),
            status=SegmentStatus.PENDING,
            gate_results={} # Empty initially
        )
        db.add(segment)
    
    db.commit()
    db.refresh(doc)
    
    return document_to_response(doc, db)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[DocumentStatus] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    List all documents with pagination and filters.
    """
    query = db.query(Document)
    
    if status:
        query = query.filter(Document.status == status)
    if search:
        query = query.filter(Document.name.ilike(f"%{search}%"))
    
    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return DocumentListResponse(
        items=[document_to_response(doc, db) for doc in docs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: Session = Depends(get_db), user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Get a single document by ID.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_to_response(doc, db)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    update: DocumentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.DOCUMENT_UPDATE)),
):
    """
    Update a document's metadata.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    update_data = update.model_dump(exclude_unset=True)
    
    # TMX-043: Learning Loop Trigger
    # If status is changing to APPROVED, trigger ingestion
    if update.status == DocumentStatus.APPROVED:
        # Check manually if it wasn't already approved? 
        # For now, simplistic trigger.
        from app.services.db_service import DatabaseService
        service = DatabaseService()
        # Run in background to not block response
        background_tasks.add_task(service.trigger_learning_loop_ingestion, doc_id)

    for field, value in update_data.items():
        setattr(doc, field, value)
    
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)

    return document_to_response(doc, db)


@router.get("/{doc_id}/audit-export")
async def export_audit_certificate(doc_id: str, user: AuthenticatedIdentity = Depends(require_permission(Permission.AUDIT_EXPORT))):
    """
    TMX-022: Download Audit Certificate.
    """
    from fastapi.responses import Response
    from app.services.db_service import DatabaseService
    
    service = DatabaseService()
    cert_text = service.generate_audit_certificate(doc_id)
    
    return Response(content=cert_text, media_type="text/plain", headers={
        "Content-Disposition": f"attachment; filename=audit_cert_{doc_id}.txt"
    })

@router.get("/deletions")
async def list_deletions(
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.AUDIT_READ)),
):
    """
    List all deletion audit records, most recent first.
    """
    records = db.query(DeletionRecord).order_by(DeletionRecord.deleted_at.desc()).all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "document_name": r.document_name,
            "file_type": r.file_type,
            "source_language": r.source_language,
            "target_language": r.target_language,
            "segment_count": r.segment_count,
            "status_before_delete": r.status_before_delete,
            "deleted_by": r.deleted_by,
            "reason": r.reason,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            "metadata_snapshot": r.metadata_snapshot,
        }
        for r in records
    ]


@router.delete("/{doc_id}", status_code=200)
async def delete_document(
    doc_id: str,
    reason: Optional[str] = Query(None, description="Reason for deletion"),
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.DOCUMENT_DELETE)),
):
    """
    Delete a document and its associated file, creating an audit record first.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Count segments before deletion
    segment_count = db.query(func.count(Segment.id)).filter(Segment.document_id == doc_id).scalar() or 0

    # Create deletion audit record with full metadata snapshot.
    # TMX-3012c: organization_id auto-injected from request-scoped context.
    deletion_record = DeletionRecord(
        document_id=doc.id,
        document_name=doc.name,
        file_type=doc.file_type,
        source_language=doc.source_language,
        target_language=doc.target_language,
        segment_count=segment_count,
        status_before_delete=doc.status,
        deleted_by=user.user_id if user else None,
        reason=reason,
        metadata_snapshot={
            "id": doc.id,
            "name": doc.name,
            "file_type": doc.file_type,
            "source_language": doc.source_language,
            "target_language": doc.target_language,
            "status": doc.status,
            "glossary_id": doc.glossary_id,
            "page_count": doc.page_count,
            "word_count": doc.word_count,
            "confidence_score": doc.confidence_score,
            "total_tokens": doc.total_tokens,
            "total_cost_usd": doc.total_cost_usd,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        },
    )
    db.add(deletion_record)

    # Delete file if exists (filesystem cleanup — does not touch the DB row).
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # TMX-3015: A9 — soft-delete only. The DeletionRecord above is the
    # forensic snapshot; the soft-delete flag is the live status.
    doc.soft_delete(actor_id=user.user_id if user else None)
    db.commit()

    return {"deletion_id": deletion_record.id, "document_name": doc.name}


@router.get("/{doc_id}/estimate")
async def estimate_translation(
    doc_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    Pre-translation cost/time estimate for a document.
    """
    import math

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    segment_count = db.query(func.count(Segment.id)).filter(Segment.document_id == doc_id).scalar() or 0
    word_count = doc.word_count or 0

    batch_size = 5
    translation_batches = math.ceil(segment_count / batch_size) if segment_count > 0 else 0
    reverse_calls = segment_count  # One reverse-translate call per segment
    total_llm_calls = translation_batches + reverse_calls

    # Token estimate: ~1.3 tokens per word for input, ~1.5x for output
    est_input_tokens = int(word_count * 1.3 * 2)  # system + user prompt overhead
    est_output_tokens = int(word_count * 1.5)
    estimated_total_tokens = est_input_tokens + est_output_tokens

    # Cost: priced via the canonical registry (single source of truth,
    # TMX-PRICING-1). The model priced here is the model reported below — they
    # are the same constant so a recorded estimate can never be for a
    # different model than the one named in the response (A3).
    estimate_model = "gpt-4o-mini"
    estimated_cost_usd = round(
        cost_for(estimate_model, est_input_tokens, est_output_tokens), 6
    )

    # Time estimate: ~3s per batch (concurrent), ~1s per reverse call (batched)
    max_concurrent = 4
    estimated_seconds = (
        math.ceil(translation_batches / max_concurrent) * 3
        + math.ceil(reverse_calls / max_concurrent) * 1
    )

    return {
        "segment_count": segment_count,
        "word_count": word_count,
        "translation_batches": translation_batches,
        "total_llm_calls": total_llm_calls,
        "estimated_total_tokens": estimated_total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "estimated_seconds": estimated_seconds,
        "model": estimate_model,
    }


@router.post("/{doc_id}/translate", response_model=TranslationJobResponse)
async def translate_document(
    doc_id: str,
    request: TranslationJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.TRANSLATE_EXECUTE)),
):
    """
    Trigger a translation job for a document.
    Can optionally specify segment_ids to only translate selected segments.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.status == DocumentStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Document is already being processed")
    
    # Update document
    doc.target_language = request.target_language
    doc.status = DocumentStatus.PROCESSING.value
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Queue background job - runs the full LLM + quality gates pipeline.
    # TMX-3012c: capture tenant context now, before the response unwinds the
    # request scope; the runner re-enters `org_context(org_id)` so DB writes
    # inside the pipeline are correctly tenanted.
    from app.agents.runner import run_pipeline_background
    from app.core.tenant_context import current_org_id
    org_id = current_org_id()
    background_tasks.add_task(
        run_pipeline_background,
        doc_id,
        request.target_language,
        request.segment_ids,  # Pass optional segment IDs filter
        org_id=org_id,
    )
    
    segment_info = f" ({len(request.segment_ids)} selected segments)" if request.segment_ids else " (all segments)"
    return TranslationJobResponse(
        document_id=doc_id,
        status="processing",
        message=f"Translation job started for {request.target_language}{segment_info}"
    )


@router.get("/{doc_id}/download-translated")
async def download_translated(
    doc_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.DOCUMENT_READ)),
):
    """
    Download the translated document in its original format.
    DOCX -> DOCX (format-preserving), TXT -> TXT, PDF -> DOCX (fallback).
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    valid_statuses = {DocumentStatus.TRANSLATED.value, DocumentStatus.IN_REVIEW.value, DocumentStatus.APPROVED.value}
    if doc.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Document has not been translated yet")

    # Get translated segments in order
    segments = (
        db.query(Segment)
        .filter(Segment.document_id == doc_id)
        .order_by(Segment.order_index)
        .all()
    )
    seg_dicts = [
        {
            "order_index": s.order_index,
            "source_text": s.source_text,
            "translated_text": s.translated_text,
            "element_type": s.element_type,
            "element_meta": s.element_meta,
        }
        for s in segments
    ]

    from app.services.document_export import DocumentExportService
    export_service = DocumentExportService()

    doc_name_base = os.path.splitext(doc.name)[0]

    if doc.file_type == "txt":
        buffer = export_service.export_txt(seg_dicts)
        filename = f"{doc_name_base}_translated.txt"
        media_type = "text/plain"
    else:
        # DOCX or PDF -> DOCX
        original_path = doc.file_path if doc.file_type == "docx" else None
        buffer = export_service.export_docx(original_path or "", seg_dicts, force_new=(doc.file_type == "pdf"))
        filename = f"{doc_name_base}_translated.docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
