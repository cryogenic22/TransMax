from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AuditRecord
from app.schemas.api_v1 import AuditRecordResponse

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
        hash_signature=record.chain_head_hash, # Using chain_head_hash as signature for now
        created_at=record.created_at
    )
