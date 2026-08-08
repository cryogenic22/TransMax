import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit_v2 import AuditEventV2
from app.models.database import Document, DocumentStatus, Segment
from app.models.models import QualityScorecard
from app.schemas.api_v1 import (
    AuditBundleResponse,
    AuditLogEntryResponse,
    AuditRef,
    JobCreateRequest,
    JobResponse,
    JobResult,
    ProvenanceRecord,
    TranslationDisposition,
    ValidationSummary,
)
from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.services.reporting_service import ReportingService

# We need to invoke the graph. For now, we import the runner.
# Ideally this is a separate worker process.
from typing import List, Optional
from app.agents.runner import run_pipeline_background
from app.services.webhook_dispatch import dispatch_job_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


def _reconstruct_document_text(segments: List[Segment]) -> str:
    """
    TMX-V1-DURABLE-IR (ADR-0008 hazard 2, two-way half): rebuild a job's full
    text from the segment IR instead of `". ".join(...)`.

    The naive join fabricated a ". " between every pair of segments
    regardless of what punctuation the preceding segment already ended in
    (the segmenter — `app/services/segmenter.py` — always keeps a segment's
    own terminal punctuation attached to it), and it flattened DOCX
    structural roles (headers, paragraphs, table cells, etc. — recorded on
    `Segment.element_type`) into a single run of prose.

    Fix: never invent a punctuation character (A3). The only join decisions
    are whitespace-shaped, driven by data the IR already recorded:
      - `element_type` changes between consecutive segments -> a structural
        boundary was actually recorded; preserve it as a line break instead
        of merging it into running text.
      - otherwise -> a single space. This is the same separator the
        segmenter itself consumed (`[.!?]+\\s+` / clause-boundary splits) —
        it never adds a period, so an already-terminated segment ("...?")
        is never double-punctuated, and an un-terminated one (e.g. a
        length-capped hard wrap, see TMX-OMIT-2) is joined the same way the
        original whitespace joined it, not invented.

    Segments with no translated text are skipped entirely so a missing
    translation cannot inject a stray separator (e.g. "foo. . bar").
    """
    parts: List[str] = []
    prev_element_type: str | None = None
    have_prev = False
    for seg in segments:
        text = seg.translated_text or ""
        if not text:
            continue
        if have_prev:
            parts.append("\n" if seg.element_type != prev_element_type else " ")
        parts.append(text)
        prev_element_type = seg.element_type
        have_prev = True
    return "".join(parts)


def _derive_disposition(
    scorecard: Optional[QualityScorecard],
) -> Optional[TranslationDisposition]:
    """TMX-SEAM-WIRE (ADR-0009 clause 3): the real disposition, taken from the
    persisted `QualityScorecard.status` — the legacy count-based verdict
    `quality_gate.py::evaluate_verdict` actually decided the job on. Never
    re-derived from `Document.status` (that's workflow state — UPLOADED /
    TRANSLATED / IN_REVIEW / APPROVED — a different concept from a quality
    verdict). None (not a guess) if there is no scorecard yet, or if a future
    status string doesn't match one of the three known verdicts (A3).
    """
    if scorecard is None:
        return None
    try:
        return TranslationDisposition(scorecard.status)
    except ValueError:
        logger.warning(
            "Unrecognised QualityScorecard.status %r for scorecard %s — "
            "disposition left None rather than guessed (A3).",
            scorecard.status, scorecard.scorecard_id,
        )
        return None


def _derive_match_type(segments: List[Segment]) -> Optional[str]:
    """TMX-SEAM-WIRE: `match_type` only when every segment agrees on
    `translation_source` (LLM / TM_EXACT / TM_FUZZY / HUMAN). A job mixing
    sources has no single honest job-level match type, so this returns None
    rather than picking one arbitrarily (A3).
    """
    sources = {s.translation_source for s in segments if s.translation_source}
    if len(sources) == 1:
        return next(iter(sources))
    return None


def _build_provenance(db: Session, job_id: str, segments: List[Segment]) -> ProvenanceRecord:
    """TMX-SEAM-WIRE (A6/A8): populate ONLY from the job's own
    CONFIG_SNAPSHOT_CAPTURED v2 audit event — the exact payload
    `app.agents._config_snapshot.build_config_snapshot` froze into the chain
    at job start, so `model` / `prompt_version` / `prompt_content_hash`
    reflect what the job ACTUALLY ran with, not the current live config. No
    field here is ever defaulted (A3): `model_version` and `language_tier`
    have no corresponding artefact anywhere in this codebase yet, so they
    always stay None until one exists.
    """
    snapshot_event = (
        db.query(AuditEventV2)
        .filter(
            AuditEventV2.job_id == job_id,
            AuditEventV2.event_type == "CONFIG_SNAPSHOT_CAPTURED",
        )
        .order_by(AuditEventV2.sequence_index.asc())
        .first()
    )

    model: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_content_hash: Optional[str] = None
    if snapshot_event is not None:
        payload = snapshot_event.payload or {}
        system = payload.get("system") or {}
        model = system.get("model")
        translator_prompt = (system.get("prompts") or {}).get("translator") or {}
        prompt_version = translator_prompt.get("version")
        prompt_content_hash = translator_prompt.get("content_hash")

    return ProvenanceRecord(
        model=model,
        prompt_version=prompt_version,
        prompt_content_hash=prompt_content_hash,
        match_type=_derive_match_type(segments),
    )


def _build_audit_ref(db: Session, job_id: str) -> Optional[AuditRef]:
    """TMX-SEAM-WIRE (A1): `chain_head_hash` from the REAL v2 chain for this
    job — the identical query `GET /api/v1/audit/{job_id}/verify_v2` uses to
    compute its own head hash, so the two independently agree. None if the
    job has no v2 chain — never a placeholder (A3).
    """
    head = (
        db.query(AuditEventV2)
        .filter(AuditEventV2.job_id == job_id)
        .order_by(AuditEventV2.sequence_index.desc())
        .first()
    )
    if head is None:
        return None
    return AuditRef(
        chain_head_hash=head.event_hash.hex(),
        verify_url=f"/api/v1/audit/{job_id}/verify_v2",
    )


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Permission.TRANSLATE_EXECUTE))])
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

    # 5. TMX-WEBHOOK-FIRE: schedule the terminal-status callback AFTER the
    # pipeline task. Starlette runs BackgroundTasks strictly in order, so the
    # dispatcher observes the job's terminal state. A3: this field used to be
    # accepted and silently ignored; now it either fires or fails loud
    # (WEBHOOK_DELIVERY_FAILED audit event + WARNING — never into the job path).
    if request.webhook_url:
        background_tasks.add_task(
            dispatch_job_webhook,
            doc_id,
            str(request.webhook_url),
            request.request_id,
            org_id=org_id,
        )

    return JobResponse(
        job_id=doc_id,
        status="processing", 
        created_at=new_doc.created_at
    )

@router.get("/", response_model=List[JobResponse],
            dependencies=[Depends(require_permission(Permission.DOCUMENT_READ))])
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

@router.get("/{job_id}", response_model=JobResponse,
            dependencies=[Depends(require_permission(Permission.DOCUMENT_READ))])
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == job_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return JobResponse(
        job_id=doc.id,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        created_at=doc.created_at
    )

@router.get("/{job_id}/result", response_model=JobResult,
            dependencies=[Depends(require_permission(Permission.DOCUMENT_READ))])
def get_job_result(job_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == job_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if doc.status not in [DocumentStatus.TRANSLATED, DocumentStatus.IN_REVIEW, DocumentStatus.APPROVED]:
        raise HTTPException(status_code=400, detail="Translation not complete")
        
    # Reconstruct Text (TMX-V1-DURABLE-IR: from the segment IR, never a
    # fabricated ". "-join — see _reconstruct_document_text docstring).
    segments = db.query(Segment).filter(Segment.document_id == job_id).order_by(Segment.order_index).all()
    full_text = _reconstruct_document_text(segments)
    
    # Quality summary — TMX-VALSUMMARY-VERDICT (A3). Two defects fixed here:
    #  1. `decision` used to read `Document.status` (workflow state: UPLOADED /
    #     TRANSLATED / IN_REVIEW / APPROVED). That is NOT the quality verdict.
    #     It now comes from `QualityScorecard.status` — the PASS/BLOCK/REVIEW
    #     the gate actually decided on (the same source `_derive_disposition`
    #     uses). A scorecard saying REVIEW while the doc is TRANSLATED no longer
    #     surfaces as a clean-looking result.
    #  2. The old broad `except Exception` swallowed a genuine lookup failure
    #     into a "0 defects" summary — falsely-empty quality evidence. Each
    #     state is now explicit, and zero counts always carry a non-verdict
    #     decision (NOT_SCORED / UNAVAILABLE) so they can never read as a pass.
    scorecard: Optional[QualityScorecard] = None
    try:
        scorecard = db.query(QualityScorecard).filter(QualityScorecard.job_id == job_id).first()
    except Exception:
        logger.exception("QualityScorecard lookup failed for job %s", job_id)
        scorecard = None
        summary = ValidationSummary(
            critical_count=0, major_count=0, minor_count=0, decision="UNAVAILABLE",
        )
    else:
        if scorecard is not None:
            summary = ValidationSummary(
                critical_count=scorecard.critical_defect_count,
                major_count=scorecard.major_defect_count,
                minor_count=scorecard.minor_defect_count,
                decision=scorecard.status,
                semantic_drift=scorecard.semantic_drift_score,
            )
        else:
            summary = ValidationSummary(
                critical_count=0, major_count=0, minor_count=0, decision="NOT_SCORED",
            )

    # TMX-SEAM-WIRE (ADR-0009 clause 3): the result block, wired honestly —
    # every field below is either derived from a real persisted artefact or
    # left None (never a placeholder/default). See the helper docstrings for
    # the exact provenance of each field. `mqm` is intentionally omitted
    # (stays at its schema default of None): the MQM engine is shadow-only
    # and must not be synthesized from the legacy scorer (A3).
    return JobResult(
        job_id=doc.id,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        original_filename=doc.name,
        translated_text=full_text,
        segments_url=f"/api/v1/translations/{job_id}/segments",
        quality_summary=summary,
        audit_id=None, # To be linked
        completed_at=doc.updated_at,
        disposition=_derive_disposition(scorecard),
        provenance=_build_provenance(db, job_id, segments),
        audit=_build_audit_ref(db, job_id),
    )

@router.get("/{job_id}/audit_bundle", response_model=AuditBundleResponse,
            dependencies=[Depends(require_permission(Permission.AUDIT_READ))])
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

@router.get("/{job_id}/certificate",
            dependencies=[Depends(require_permission(Permission.AUDIT_EXPORT))])
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
        logger.warning(f"PDF Gen Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate certificate")
