from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import app.core.database as core_db
from app.core.database import get_db
from app.core.tenant_context import TenantContextMissing, current_org_id
from app.models.audit_v2 import AuditEventV2
from app.models.models import AuditRecord
from app.schemas.api_v1 import (
    AuditRecordResponse,
    AuditVerificationResponse,
    VerifyFinding,
)
from app.services.audit_service import AuditService
from app.services.audit_verifier_v2 import AuditVerifierV2

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


@router.get("/{job_id}/verify_v2", response_model=AuditVerificationResponse)
def verify_v2_audit_chain(job_id: str, db: Session = Depends(get_db)):
    """
    TMX-3105: Independent re-compute verification of the v2 audit chain.

    Calls :py:meth:`app.services.audit_verifier_v2.AuditVerifierV2.verify_job_chain`
    under the current tenant context (set by ``TenantContextMiddleware``)
    and returns a regulator-readable JSON report.

    Status codes:
      * 200 — chain exists; ``ok`` reflects integrity (true iff zero
        findings). A3: a corrupted chain returns 200 + ``ok=false`` +
        populated findings — NEVER 200 + ``ok=true`` for tampered data.
      * 404 — no v2 events for ``(current_org, job_id)``. The tenant
        auto-filter means a job belonging to another org also lands
        here (NOT 403) — see AC-5: don't leak existence cross-tenant.
      * 500 — propagated TenantContextMissing if middleware fails to
        set context (misconfigured deployment; loud crash per A3).

    Pinned by TMX-3105 tests in ``tests/test_audit_verify_endpoint.py``.
    """
    org_id = current_org_id()
    if org_id is None:
        # Middleware should always set this. If it doesn't, the deployment
        # is broken — fail loud rather than silently default (A3).
        raise TenantContextMissing(
            "verify_v2 endpoint requires tenant context — middleware misconfigured?"
        )

    # Count-pre-check upgrades "empty chain is valid" → loud 404. The
    # TenantScopedMixin auto-filter restricts this count to the current org,
    # so cross-tenant access also returns 0 (no existence leak — AC-5).
    event_count = db.query(AuditEventV2).filter(
        AuditEventV2.job_id == job_id
    ).count()
    if event_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No v2 audit chain found for job {job_id}",
        )

    # NB: pass the SessionLocal via the module attribute, not a captured
    # reference, so tests that swap `core_db.SessionLocal` (see
    # tests/conftest.py:fresh_engine_for_db) reach the swapped factory
    # at request time. A captured `from app.core.database import SessionLocal`
    # would freeze the binding at import time and break test isolation.
    verifier = AuditVerifierV2(session_factory=core_db.SessionLocal)
    report = verifier.verify_job_chain(job_id)

    return AuditVerificationResponse(
        ok=report.is_valid,
        organization_id=report.organization_id,
        job_id=str(report.job_id),
        event_count=report.event_count,
        ok_count=report.ok_count,
        findings=[
            VerifyFinding(
                event_id=f.event_id,
                sequence_index=f.sequence_index,
                finding=f.finding.value,
                detail=f.detail,
            )
            for f in report.findings
        ],
    )
