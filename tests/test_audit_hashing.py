import pytest
import json
import hashlib
from unittest.mock import MagicMock, patch
from app.services.db_service import DatabaseService
from app.models.models import TranslationJobQueue, AuditRecord

@pytest.fixture
def mock_db_session():
    return MagicMock()

def test_audit_log_hashing(mock_db_session):
    """
    Verifies that save_audit_log computes a consistent SHA-256 hash.
    """
    service = DatabaseService()
    
    # Mock get_session to return our mock
    with patch.object(service, 'get_session', return_value=mock_db_session):
        # Setup data
        job_id = "job-123"
        audit_id = "audit-456"
        state = {
            "final_decision": "PASS",
            "quality_report": {
                "summary": {"score": 98}
            }
        }
        
        # Mock finding the job
        mock_job = TranslationJobQueue(job_id=job_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_job
        
        # Execute
        service.save_audit_log(job_id, state, audit_id)
        
        # Verification
        # 1. Check if add was called
        assert mock_db_session.add.called
        
        # 2. Get the AuditRecord object passed to add
        # add is called with the audit record
        # args[0] is the object
        audit_record = mock_db_session.add.call_args[0][0]
        
        assert isinstance(audit_record, AuditRecord)
        assert audit_record.audit_id == audit_id
        assert audit_record.hash_signature is not None
        
        # 3. Re-compute hash manually to verify correctness
        # integrity_payload = f"{audit_id}:{job_id}:{audit.final_decision}:{json.dumps(audit.scores_json, sort_keys=True)}"
        expected_payload = f"{audit_id}:{job_id}:PASS:{json.dumps({'score': 98}, sort_keys=True)}"
        expected_hash = hashlib.sha256(expected_payload.encode()).hexdigest()
        
        assert audit_record.hash_signature == expected_hash
