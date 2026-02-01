"""
TransMax Platform v2.0 - Document API Router
CRUD operations for documents and translation jobs.
"""
import os
import uuid
import aiofiles
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.database import Document, Segment, DocumentStatus, SegmentStatus
from app.api.schemas import (
    DocumentUpdate, DocumentResponse, DocumentListResponse,
    TranslationJobRequest, TranslationJobResponse
)
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# --- Constants ---
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
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
    db: Session = Depends(get_db)
):
    """
    Upload a new document, digitize it (extract text segments), and store in DB.
    """
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT.")
    
    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save file
    # Save file asynchronously
    async with aiofiles.open(file_path, 'wb') as out_file:
         while content := await file.read(1024 * 1024):  # 1MB chunks
            await out_file.write(content)
    
    # Ingest / Digitize Content
    ingest_service = PDFService()
    try:
        if file_ext == ".pdf":
            # PDF extraction might still be blocking (PyPDF/Unstructured), so run in threadpool?
            # For now, we assume PDFService is synchronous.
            # Ideally: await run_in_threadpool(ingest_service.extract_text, file_path)
            blocks = ingest_service.extract_text(file_path)
        else:
            # Placeholder for DOCX/TXT - minimal fallback
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
                blocks = [{"text": content, "type": "PlainText"}]
    except Exception as e:
        print(f"Ingestion failed: {e}")
        # Non-blocking failure? Or fail request?
        # For now, create doc but with warning log
        blocks = []

    # Get file size and word count
    # Async I/O for size check not cleanly available in os.path, but stat is fast.
    # os.path.getsize(file_path) 

    total_words = sum(len(b["text"].split()) for b in blocks)
    
    # Create document record
    doc = Document(
        id=doc_id,
        name=name or file.filename,
        source_language=source_language,
        target_language=target_language,
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
    db: Session = Depends(get_db)
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
async def get_document(doc_id: str, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
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
    
    doc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    
    return document_to_response(doc, db)


@router.get("/{doc_id}/audit-export")
async def export_audit_certificate(doc_id: str):
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

@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """
    Delete a document and its associated file.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file if exists
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    
    db.delete(doc)
    db.commit()
    return None


@router.post("/{doc_id}/translate", response_model=TranslationJobResponse)
async def translate_document(
    doc_id: str,
    request: TranslationJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
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
    doc.status = DocumentStatus.PROCESSING
    doc.updated_at = datetime.utcnow()
    db.commit()
    
    # Queue background job - runs the full LLM + quality gates pipeline
    from app.agents.runner import run_pipeline_background
    background_tasks.add_task(
        run_pipeline_background, 
        doc_id, 
        request.target_language,
        request.segment_ids  # Pass optional segment IDs filter
    )
    
    segment_info = f" ({len(request.segment_ids)} selected segments)" if request.segment_ids else " (all segments)"
    return TranslationJobResponse(
        document_id=doc_id,
        status="processing",
        message=f"Translation job started for {request.target_language}{segment_info}"
    )
