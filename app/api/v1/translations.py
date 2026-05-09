from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.database import Document, DocumentStatus, Segment
from app.schemas.api_v1 import JobCreateRequest, JobResponse, JobResult, ValidationSummary

# We need to invoke the graph. For now, we import the runner.
# Ideally this is a separate worker process.
from typing import List
from app.agents.runner import run_pipeline_background

router = APIRouter()

@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_translation_job(
    request: JobCreateRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    TMX-010: Create a new translation job (Async).
    TMX-GOV-03: Enforces Governance Profile (Archetype+Tier).
    """
    # 1. Idempotency Check
    existing = db.query(Document).filter(Document.client_request_id == request.request_id).first()
    if existing:
        return JobResponse(
            job_id=existing.id,
            status=existing.status.value if hasattr(existing.status, 'value') else existing.status,
            created_at=existing.created_at,
            estimated_completion=None 
        )

    # 2. Create Document Record. TMX-3012c: organization_id auto-injected
    # from request-scoped tenant context (TenantContextMiddleware → mixin).
    doc_id = str(uuid.uuid4())
    new_doc = Document(
        id=doc_id,
        name=request.document_name or "api_upload.txt",
        source_language=request.source_language,
        target_language=request.target_language,
        status=DocumentStatus.UPLOADED.value,
        client_request_id=request.request_id,
        created_at=datetime.now(timezone.utc),
        meta_json=request.profile.model_dump() # Persist Profile for Graph
    )
    db.add(new_doc)
    
    # 3. Handle Content
    if request.text_content:
        # TMX-3800: abbreviation-aware segmenter replaces the naive .split('.')
        from app.services.segmenter import get_segmenter
        segmenter = get_segmenter(request.source_language or "en")
        segments = segmenter.segment(request.text_content)
        for idx, text in enumerate(segments):
            seg = Segment(
                document_id=doc_id,
                order_index=idx,
                source_text=text,
                status="pending"
            )
            db.add(seg)
            
    db.commit()
    
    # 4. Enqueue Job
    # We pass the PROFILE to the background runner
    # We should update run_pipeline_background to accept profile too, or efficient read from DB.
    # For now, it reads from doc.meta_json.
    # TMX-3012c: capture tenant context for the background pipeline.
    from app.core.tenant_context import current_org_id
    org_id = current_org_id()
    background_tasks.add_task(
        run_pipeline_background,
        doc_id,
        request.target_language,
        org_id=org_id,
    )
    
    return JobResponse(
        job_id=doc_id,
        status="processing", 
        created_at=new_doc.created_at
    )

@router.get("/", response_model=List[JobResponse])
def list_translation_jobs(
    limit: int = 50, 
    skip: int = 0, 
    db: Session = Depends(get_db)
):
    """
    TMX-010: List recent translation jobs.
    """
    docs = db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    # Safely map enums
    results = []
    for d in docs:
        status_val = d.status.value if hasattr(d.status, 'value') else d.status
        results.append(JobResponse(
            job_id=d.id,
            status=status_val,
            confidence_score=d.confidence_score,
            created_at=d.created_at
        ))
    return results

@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == job_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return JobResponse(
        job_id=doc.id,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        created_at=doc.created_at
    )

@router.get("/{job_id}/result", response_model=JobResult)
def get_job_result(job_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == job_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if doc.status not in [DocumentStatus.TRANSLATED, DocumentStatus.IN_REVIEW, DocumentStatus.APPROVED]:
        raise HTTPException(status_code=400, detail="Translation not complete")
        
    # Reconstruct Text
    segments = db.query(Segment).filter(Segment.document_id == job_id).order_by(Segment.order_index).all()
    full_text = ". ".join([s.translated_text or "" for s in segments])
    
    # Calc Quality Stats
    try:
        from app.models.models import QualityScorecard
        scorecard = db.query(QualityScorecard).filter(QualityScorecard.job_id == job_id).first()
        
        summary = ValidationSummary(
            critical_count=scorecard.critical_defect_count if scorecard else 0,
            major_count=scorecard.major_defect_count if scorecard else 0,
            minor_count=scorecard.minor_defect_count if scorecard else 0,
            decision=doc.status.value if hasattr(doc.status, 'value') else doc.status,
            semantic_drift=scorecard.semantic_drift_score if scorecard else None
        )
    except Exception:
        # Fallback if no scorecard
        summary = ValidationSummary(critical_count=0, major_count=0, minor_count=0, decision="UNKNOWN")

    return JobResult(
        job_id=doc.id,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        original_filename=doc.name,
        translated_text=full_text,
        segments_url=f"/api/v1/translations/{job_id}/segments",
        quality_summary=summary,
        audit_id=None, # To be linked
        completed_at=doc.updated_at
    )

from app.schemas.api_v1 import AuditBundleResponse, AuditLogEntryResponse

@router.get("/{job_id}/audit_bundle", response_model=AuditBundleResponse)
def get_audit_bundle(job_id: str, db: Session = Depends(get_db)):
    """
    TMX-020: Export Regulatory Audit Bundle.
    """
    from app.models.models import AuditRecord, AuditLogEntry
    
    # 1. Fetch Audit Root
    audit_record = db.query(AuditRecord).filter(AuditRecord.job_id == job_id).first()
    if not audit_record:
        raise HTTPException(status_code=404, detail="Audit Trail not found for this Job")
        
    # 2. Fetch Chain
    entries = db.query(AuditLogEntry).filter(
        AuditLogEntry.audit_id == audit_record.audit_id
    ).order_by(AuditLogEntry.sequence_index).all()
    
    # 3. Verify Chain Integrity
    from app.services.audit_service import AuditService
    integrity = AuditService().verify_chain_integrity(audit_record.audit_id)
    is_tampered = not integrity.get("valid", True)

    response_entries = [
        AuditLogEntryResponse(
            sequence_index=e.sequence_index,
            event_type=e.event_type,
            timestamp=e.timestamp,
            entry_hash=e.entry_hash,
            payload_summary={"count": len(str(e.payload))}
        )
        for e in entries
    ]

    return AuditBundleResponse(
        audit_id=audit_record.audit_id,
        job_id=job_id,
        final_decision=audit_record.final_decision or "PENDING",
        created_at=audit_record.created_at,
        chain_head_hash=audit_record.chain_head_hash or "N/A",
        is_tampered=is_tampered,
        entries=response_entries
    )

from fastapi.responses import StreamingResponse
from app.services.reporting_service import ReportingService

@router.get("/{job_id}/certificate")
def download_certificate(job_id: str, db: Session = Depends(get_db)):
    """
    TMX-025: Download Translation Certificate (PDF).
    """
    try:
        pdf_buffer = ReportingService.generate_certificate(db, job_id)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Certificate_{job_id}.pdf"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"PDF Gen Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate certificate")
