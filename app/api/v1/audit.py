from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AuditRecord
from app.schemas.api_v1 import AuditRecordResponse
from app.services.audit_service import AuditService

router = APIRouter()

@router.get("/{audit_id}", response_model=AuditRecordResponse)
def get_audit_record(audit_id: str, db: Session = Depends(get_db)):
    """
    TMX-020: Retrieve inspection-grade audit record.
    """
    record = db.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found")
    
    # Map Flat DB columns to Schema Dict
    versions = {
        "model": record.model_version,
        "prompts": record.prompt_version,
        "glossary": record.glossary_version,
        "lang_pack": record.language_pack_version,
        "policy": record.policy_version
    }
    
    return AuditRecordResponse(
        audit_id=record.audit_id,
        job_id=record.job_id,
        final_decision=record.final_decision,
        versions=versions,
        hash_signature=record.hash_signature or record.chain_head_hash,
        full_payload=record.full_payload,
        created_at=record.created_at
    )


@router.get("/{audit_id}/verify")
def verify_audit_integrity(audit_id: str, db: Session = Depends(get_db)):
    """
    TMX-020: Verify tamper-evident hash chain integrity for an audit trail.
    Returns detailed integrity report including broken link location if tampered.
    """
    record = db.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found")

    report = AuditService().verify_chain_integrity(audit_id)
    return {
        "audit_id": audit_id,
        "job_id": record.job_id,
        "is_tampered": not report.get("valid", True),
        "chain_head_hash": record.chain_head_hash,
        **report,
    }
