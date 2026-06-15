"""
TransMax Platform v2.0 - Segment API Router
Operations for segments: read, update, reverse translate, change log.
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant_context import org_context
from app.models.database import Document, Segment, ChangeLog, SegmentStatus
from app.api.schemas import (
    SegmentResponse, SegmentUpdate,
    SegmentReverseResponse,
    ChangeLogResponse
)
from app.auth.providers import AuthenticatedIdentity
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permission

import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["Segments"])


# --- Helper Functions ---

async def _capture_hitl_override(
    segment_id: str,
    source_text: str,
    mt_text: str,
    corrected_text: str,
    org_id: Optional[str],
) -> None:
    """TMX-MQM-CAPTURE: feed a reviewer override into the learning bridge as a
    PROPOSED Black-Book candidate — the gold signal for Phase-2 judge
    calibration (review cond. 6).

    Reconnects the existing ``LearningService.process_learning_event`` path
    (which the vision-gap audit found reachable from no production endpoint).
    Runs as a FastAPI BackgroundTask so it adds no request latency, and
    re-establishes the request's tenant context (the candidate row is
    tenant-scoped, so a missing context would fail loud). Fully defensive: any
    failure is logged, never surfaced to the reviewer.
    """
    if not org_id:
        logger.warning(
            "HITL learning capture skipped for %s: no tenant context", segment_id
        )
        return
    try:
        from app.services.learning_service import LearningService

        with org_context(org_id):
            await LearningService().process_learning_event(
                segment_id=segment_id,
                human_correction=corrected_text,
                source_text=source_text,
                mt_text=mt_text,
            )
        logger.info("HITL override captured as learning candidate for %s", segment_id)
    except Exception as e:  # never break on capture
        logger.warning(
            "HITL learning capture failed for %s (non-fatal): %s", segment_id, e
        )


def segment_to_response(seg: Segment) -> SegmentResponse:
    """Convert ORM model to response schema."""
    return SegmentResponse(
        id=seg.id,
        document_id=seg.document_id,
        order_index=seg.order_index,
        source_text=seg.source_text,
        translated_text=seg.translated_text,
        confidence_score=seg.confidence_score,
        status=seg.status,
        gate_results=seg.gate_results,
        element_meta=seg.element_meta,  # TMX-3702 — surfaces DOCX revision metadata
        created_at=seg.created_at,
        updated_at=seg.updated_at
    )


# --- Endpoints ---

@router.get("/documents/{doc_id}/segments", response_model=List[SegmentResponse])
async def list_segments(doc_id: str, db: Session = Depends(get_db), user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    List all segments for a document.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    segments = db.query(Segment).filter(Segment.document_id == doc_id).order_by(Segment.order_index).all()
    return [segment_to_response(seg) for seg in segments]


@router.get("/segments/{segment_id}", response_model=SegmentResponse)
async def get_segment(segment_id: str, db: Session = Depends(get_db), user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Get a single segment by ID.
    """
    seg = db.query(Segment).filter(Segment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment_to_response(seg)


@router.patch("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: str,
    update: SegmentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(require_permission(Permission.SEGMENT_EDIT)),
):
    """
    Update a segment's translation. Requires a reason for the change.
    Creates a ChangeLog entry.
    """
    seg = db.query(Segment).filter(Segment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Update segment first
    original_text = seg.translated_text or ""
    source_text = seg.source_text or ""
    seg_org_id = getattr(seg, "organization_id", None)
    seg.translated_text = update.translated_text
    seg.status = SegmentStatus.EDITED
    seg.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(seg)

    # TMX-062: Log Change via Central Service
    # Run in background or sync? Sync to ensure log exists before return.
    from app.services.db_service import DatabaseService
    service = DatabaseService()
    try:
        service.log_segment_change(
            segment_id=segment_id,
            original=original_text,
            new=update.translated_text,
            reason=update.reason,
            user_id=user.user_id,
            user_name=user.name
        )
    except Exception as e:
        logger.warning(f"Failed to write ChangeLog: {e}")
        # We don't rollback segment change here as it was committed.

    # TMX-MQM-CAPTURE: a reviewer override (the MT text actually changed) is the
    # gold signal for Phase-2 judge calibration. Feed it into the learning
    # bridge as a PROPOSED candidate, off the request path. Only fires on a real
    # change, so confirms/no-ops cost nothing.
    if (
        get_settings().enable_hitl_learning_capture
        and original_text
        and original_text != update.translated_text
    ):
        background_tasks.add_task(
            _capture_hitl_override,
            segment_id,
            source_text,
            original_text,
            update.translated_text,
            seg_org_id,
        )

    return segment_to_response(seg)


@router.post("/segments/{segment_id}/reverse", response_model=SegmentReverseResponse)
async def reverse_translate_segment(
    segment_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    Perform reverse translation on a segment to verify accuracy.
    Sends the translated text back through the agent to get English output.
    """
    seg = db.query(Segment).filter(Segment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    if not seg.translated_text:
        raise HTTPException(status_code=400, detail="Segment has no translation to reverse")

    # Get document for language info
    doc = db.query(Document).filter(Document.id == seg.document_id).first()
    target_lang = doc.target_language if doc else "unknown"
    source_lang = doc.source_language if doc else "en"

    from app.services.llm import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = get_llm()
    system_msg = SystemMessage(content=(
        f"You are a strict linguistic auditor performing back-translation verification. "
        f"Translate the following {target_lang} text back into {source_lang}. "
        f"Maintain exact meaning, tone, and technical precision. "
        f"Return ONLY the translation."
    ))
    user_msg = HumanMessage(content=f"Text: {seg.translated_text}")

    try:
        response = await llm.ainvoke([system_msg, user_msg])
        reverse_text = response.content.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM reverse translation failed: {e}")

    # Persist on the segment
    seg.reverse_translation = reverse_text
    db.commit()

    return SegmentReverseResponse(
        segment_id=segment_id,
        original_source=seg.source_text,
        translated_text=seg.translated_text,
        reverse_translation=reverse_text
    )


@router.get("/segments/{segment_id}/changelog", response_model=List[ChangeLogResponse])
async def get_segment_changelog(segment_id: str, db: Session = Depends(get_db), user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Get the change history for a segment.
    """
    seg = db.query(Segment).filter(Segment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    logs = db.query(ChangeLog).filter(ChangeLog.segment_id == segment_id).order_by(ChangeLog.created_at.desc()).all()
    
    return [
        ChangeLogResponse(
            id=log.id,
            segment_id=log.segment_id,
            original_text=log.original_text,
            new_text=log.new_text,
            reason=log.reason,
            user_id=log.user_id,
            user_name=log.user_name,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/documents/{doc_id}/audit", response_model=List[ChangeLogResponse])
async def get_document_audit_trail(doc_id: str, db: Session = Depends(get_db), user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Get the full audit trail for a document (all segment changes).
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all segment IDs for this document
    segment_ids = db.query(Segment.id).filter(Segment.document_id == doc_id).all()
    segment_ids = [s[0] for s in segment_ids]
    
    if not segment_ids:
        return []
    
    logs = db.query(ChangeLog).filter(ChangeLog.segment_id.in_(segment_ids)).order_by(ChangeLog.created_at.desc()).all()
    
    return [
        ChangeLogResponse(
            id=log.id,
            segment_id=log.segment_id,
            original_text=log.original_text,
            new_text=log.new_text,
            reason=log.reason,
            user_id=log.user_id,
            user_name=log.user_name,
            created_at=log.created_at
        )
        for log in logs
    ]
