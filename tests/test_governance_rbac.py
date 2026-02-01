
import pytest
import uuid
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.services.db_service import DatabaseService
from app.services.audit_service import AuditService
from app.services.quality_gate import QualityGateService
from app.models.models import QualityScorecard, AuditRecord, AuditLogEntry, TranslationJobQueue

@pytest.fixture
def db():
    return DatabaseService()

@pytest.fixture
def audit():
    return AuditService()

@pytest.fixture
def gate():
    return QualityGateService()

@pytest.fixture
def scaffold_governance(db):
    """
    Sets up a job and its audit trail.
    """
    job_id = str(uuid.uuid4())
    audit_id = str(uuid.uuid4())
    scorecard_id = str(uuid.uuid4())
    
    session = db.get_session()
    try:
        # Create Job
        job = TranslationJobQueue(job_id=job_id, request_id=f"req_{job_id}", source_language="en", target_language="fr", request_json={})
        session.add(job)
        
        # Create Audit Record
        ar = AuditRecord(audit_id=audit_id, job_id=job_id)
        session.add(ar)
        
        # Create Scorecard
        qs = QualityScorecard(scorecard_id=scorecard_id, job_id=job_id, status="REVIEW_REQUIRED")
        session.add(qs)
        
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
        
    return job_id, audit_id

def test_governance_block_without_review(db, gate, scaffold_governance):
    """
    TMX-GOV-02: REVIEW_REQUIRED must block finalization if no Ack event exists.
    """
    job_id, _ = scaffold_governance
    
    # Check Gate
    is_allowed = gate.can_finalize(job_id)
    
    assert is_allowed is False, "Governance Failed: Job allowed to finalize without Reviewer Ack."

def test_governance_allow_with_review(db, gate, audit, scaffold_governance):
    """
    TMX-GOV-02: REVIEW_REQUIRED allows finalization IF Ack event exists.
    """
    job_id, audit_id = scaffold_governance
    
    # 1. Log Reviewer Action (using the new method)
    audit.log_reviewer_action(audit_id, "APPROVE", "user_123", "Risk Accepted")
    
    # 2. Check Gate
    is_allowed = gate.can_finalize(job_id)
    
    assert is_allowed is True, "Governance Failed: Job blocked despite Reviewer Ack."

def test_governance_blocked_status(db, gate):
    """
    TMX-GOV-02: BLOCKED status never finalizes, even with review.
    (Critical defects usually require fixing, not just overriding).
    """
    job_id = str(uuid.uuid4())
    session = db.get_session()
    
    try:
        # 1. Create Job (Fixes FK violation)
        job = TranslationJobQueue(job_id=job_id, request_id=f"req_{job_id}", source_language="en", target_language="fr", request_json={})
        session.add(job)
        
        # 2. Create Scorecard
        qs = QualityScorecard(job_id=job_id, status="BLOCKED")
        session.add(qs)
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
        
    is_allowed = gate.can_finalize(job_id)
    assert is_allowed is False

if __name__ == "__main__":
    pytest.main([__file__])
