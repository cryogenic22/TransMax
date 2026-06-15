from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import os
import tempfile

from app.services.db_service import DatabaseService
from app.services.queue_service import QueueService
from app.services.pdf_service import PDFService
from app.auth.providers import AuthenticatedIdentity
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permission

router = APIRouter()

# Initialize Services
db_service = DatabaseService()
queue_service = QueueService()
pdf_service = PDFService()

# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

class ContentBlock(BaseModel):
    block_id: Optional[str] = None
    text: str
    type: str = "text" # e.g., 'header', 'paragraph', 'table_cell'

class TranslationRequest(BaseModel):
    blocks: List[ContentBlock]
    source_language: str
    target_language: str
    domain: str = "general"
    audience: str = "general"
    risk_level: str = "medium"
    glossary_id: Optional[str] = None
    
class TranslationResponse(BaseModel):
    request_id: str
    job_id: str
    decision: str
    quality_report: Optional[Dict[str, Any]] = None
    translated_text: Optional[str] = None
    audit_trail_id: Optional[str] = None

# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.post("/translate", response_model=TranslationResponse,
             dependencies=[Depends(require_permission(Permission.TRANSLATE_EXECUTE))])
async def translate_text(request: TranslationRequest, background_tasks: BackgroundTasks, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Triggers the TransMax Agentic Workflow asynchronously.
    Returns immediately with PENDING status.
    """
    request_id = str(uuid.uuid4())
    
    # Process blocks: Ensure IDs
    processed_blocks = []
    for idx, b in enumerate(request.blocks):
        processed_blocks.append({
            "block_id": b.block_id or f"b{idx}",
            "content": b.text,
            "type": b.type
        })

    # Construct Initial State
    initial_state = {
        "request_id": request_id,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "domain": request.domain,
        "audience": request.audience,
        "content_blocks": processed_blocks,
        "segments": [],
        "constraint_pack": {},
        "draft_segments": [],
        "quality_report": {},
        "iteration_count": 0,
        "final_decision": "PENDING",
        "audit_trail_id": str(uuid.uuid4()),
        "error": None,
        # We can pass job_id here after creation
    }
    
    try:
        # 1. Create Job in DB (PENDING)
        job_id = db_service.create_job(initial_state)
        initial_state['job_id'] = job_id
        
        # 2. Enqueue Background Task
        queue_service.enqueue_translation(initial_state, background_tasks)
        
        # 3. Return Immediate Response
        return TranslationResponse(
            request_id=request_id,
            job_id=job_id, # Return the job_id for polling
            decision="PENDING",
            quality_report=None,
            translated_text=None,
            audit_trail_id=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QuickTranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: str = "en"

class QuickTranslateResponse(BaseModel):
    translated_text: str
    confidence: int
    checks: List[Dict[str, str]]
    source_text: str
    target_language: str

@router.post("/translate/quick", response_model=QuickTranslateResponse,
             dependencies=[Depends(require_permission(Permission.TRANSLATE_EXECUTE))])
async def quick_translate(request: QuickTranslateRequest, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    High-quality synchronous translation for short text snippets.
    Uses the same pharma-grade prompting and quality checks as the full pipeline.
    Returns translation with real quality gate results.
    """
    from app.services.llm import get_llm
    from app.services.quality_gate import QualityGateService
    from app.services.language_detection import detect_language, get_language_name, LANGUAGE_NAMES
    from langchain_core.messages import SystemMessage, HumanMessage

    try:
        llm = get_llm()
        gate_service = QualityGateService()

        # Auto-detect source language if set to "auto" or empty
        source_lang = request.source_language
        if not source_lang or source_lang == "auto":
            detection = detect_language(request.text)
            source_lang = detection.language

        target_name = get_language_name(request.target_language)
        source_name = get_language_name(source_lang)
        
        # Use the same pharma-grade prompt as the full pipeline
        system_msg = SystemMessage(content=f"""You are an expert pharmaceutical/medical translator specializing in regulatory documents.

CRITICAL RULES FOR PHARMACEUTICAL TRANSLATION:
1. PRESERVE NEGATIONS EXACTLY - Never drop "not", "no", "do not", "should not", "must not"
2. KEEP MEDICAL UNITS UNCHANGED - mg, mL, kg, IU, etc. stay exactly as written
3. USE APPROVED TERMINOLOGY - Use standard medical terms for the target language
4. MAINTAIN NUMBER PRECISION - All dosages, percentages, and measurements must be exact
5. PRESERVE WARNINGS AND CONTRAINDICATIONS - These are life-critical

Translate the following text from {source_name} to {target_name}.
Return ONLY the translation with no explanations or notes.""")
        
        user_msg = HumanMessage(content=request.text)
        
        # Call LLM - this uses the same model as the full pipeline
        response = await llm.ainvoke([system_msg, user_msg])
        translated_text = response.content.strip()
        
        # Run comprehensive quality checks (same as pipeline)
        violations = gate_service.check_segment(
            request.text,
            translated_text,
            {},  # No glossary constraints for quick translate
            request.target_language,
            source_lang=source_lang
        )
        
        # Analyze violation types
        has_terminology_issue = any(v.get('category') == 'terminology' for v in violations)
        has_negation_issue = any(v.get('category') == 'negation' for v in violations)
        has_unit_issue = any(v.get('category') == 'units' for v in violations)
        has_critical = any(v.get('severity') == 'critical' for v in violations)
        
        # Build quality check results
        checks = [
            {"label": "Terminology", "status": "warning" if has_terminology_issue else "pass"},
            {"label": "Negation", "status": "fail" if has_negation_issue else "pass"},
            {"label": "Medical accuracy", "status": "fail" if has_critical else ("warning" if violations else "pass")},
        ]
        
        # Calculate confidence based on violations (same logic as pipeline)
        confidence = 95
        for v in violations:
            severity = v.get('severity', 'low')
            if severity == 'critical':
                confidence -= 15
            elif severity == 'high':
                confidence -= 10
            elif severity == 'medium':
                confidence -= 5
            else:
                confidence -= 2
        confidence = max(50, confidence)
        
        return QuickTranslateResponse(
            translated_text=translated_text,
            confidence=confidence,
            checks=checks,
            source_text=request.text,
            target_language=request.target_language
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@router.post("/translate/upload",
             dependencies=[Depends(require_permission(Permission.TRANSLATE_EXECUTE))])
async def translate_file_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_language: str = Form("fr"),
    source_language: str = Form("en"),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """
    Accepts file upload (PDF, TXT), extracts text, and triggers translation pipeline.
    Returns job_id for polling status.
    """
    request_id = str(uuid.uuid4())
    
    # Save uploaded file temporarily
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Extract text from file
        if suffix.lower() == ".pdf":
            blocks = pdf_service.extract_text(tmp_path)
        else:
            # Plain text file
            text_content = content.decode('utf-8', errors='ignore')
            blocks = [{"type": "text", "text": line.strip(), "element_id": f"line-{i}"} 
                      for i, line in enumerate(text_content.split('\n')) if line.strip()]
        
        # Construct initial state
        processed_blocks = [
            {"block_id": b.get("element_id", f"b{i}"), "content": b["text"], "type": b.get("type", "text")}
            for i, b in enumerate(blocks)
        ]
        
        initial_state = {
            "request_id": request_id,
            "source_language": source_language,
            "target_language": target_language,
            "domain": "pharma",
            "audience": "general",
            "content_blocks": processed_blocks,
            "segments": [],
            "constraint_pack": {},
            "draft_segments": [],
            "quality_report": {},
            "iteration_count": 0,
            "final_decision": "PENDING",
            "audit_trail_id": str(uuid.uuid4()),
            "error": None,
            "original_filename": file.filename,
        }
        
        # Create job and enqueue
        job_id = db_service.create_job(initial_state)
        initial_state['job_id'] = job_id
        queue_service.enqueue_translation(initial_state, background_tasks)
        
        return {
            "request_id": request_id,
            "job_id": job_id,
            "status": "PENDING",
            "segments_count": len(processed_blocks),
            "filename": file.filename
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.get("/translate/{job_id}")
async def get_translation_job(job_id: str, user: AuthenticatedIdentity = Depends(get_current_user)):
    """
    Polls the status of a translation job.
    """
    db = db_service.get_session()
    try:
        from app.models.models import TranslationJobQueue
        job = db.query(TranslationJobQueue).filter(TranslationJobQueue.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Construct response
        data_payload = job.state_json if job.state_json else job.request_json
        
        # Aggregate translated text from segments
        translated_text = None
        if data_payload:
            segments = data_payload.get("segments", [])
            if segments:
                translated_parts = [
                    s.get("translated_text", "") or s.get("target_text", "") 
                    for s in segments 
                    if s.get("translated_text") or s.get("target_text")
                ]
                if translated_parts:
                    translated_text = " ".join(translated_parts)
        
        return {
            "request_id": job.request_id,
            "job_id": job.job_id,
            "decision": job.status,  # PENDING/COMPLETED
            "status": job.status,
            "quality_report": data_payload.get("quality_report") if data_payload else None,
            "translated_text": translated_text,
            "extended_data": data_payload  # Pass full state for UI
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/audit/{audit_id}", dependencies=[Depends(require_permission(Permission.AUDIT_READ))])
async def get_audit_log(audit_id: str):
    """
    Retrieves the structured audit log including chain entries and integrity status.
    """
    from app.services.audit_service import AuditService
    from app.services.db_service import DatabaseService

    db_service = DatabaseService()
    session = db_service.get_session()
    try:
        from app.models.models import AuditRecord, AuditLogEntry
        record = session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Audit record not found")

        entries = (
            session.query(AuditLogEntry)
            .filter(AuditLogEntry.audit_id == audit_id)
            .order_by(AuditLogEntry.sequence_index)
            .all()
        )

        integrity = AuditService(db_service).verify_chain_integrity(audit_id)

        return {
            "audit_id": audit_id,
            "job_id": record.job_id,
            "final_decision": record.final_decision,
            "chain_head_hash": record.chain_head_hash,
            "is_tampered": not integrity.get("valid", True),
            "integrity": integrity,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "entries": [
                {
                    "sequence_index": e.sequence_index,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "entry_hash": e.entry_hash,
                    "payload": e.payload,
                }
                for e in entries
            ],
        }
    finally:
        session.close()

@router.get("/knowledge/rules", dependencies=[Depends(require_permission(Permission.KNOWLEDGE_READ))])
async def list_knowledge_rules(status: str = "ACTIVE"):
    """
    Exposes the Black Book rules for the UI.
    """
    # Quick implementation directly using DB Service logic or raw query
    # db_service.get_constraints gets active rules but mixes them in 'glossary'
    # We should add a dedicated method or query here.
    # For speed, let's use a direct session here or add method to db_service.
    # Let's add a helper to endpoints for now to keep db_service clean-ish or reuse get_session
    
    db = db_service.get_session()
    try:
        from app.models.models import TranslationRule
        rules = db.query(TranslationRule).filter(TranslationRule.status == status).all()
        return [
            {
                "rule_id": r.rule_id,
                "source_pattern": r.source_pattern,
                "target_correction": r.target_correction,
                "context_tag": r.context_tag,
                "confidence_score": r.confidence_score,
                "status": r.status
            }
            for r in rules
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
