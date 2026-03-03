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

    with patch.object(service, 'get_session', return_value=mock_db_session):
        job_id = "job-123"
        audit_id = "audit-456"
        state = {
            "final_decision": "PASS",
            "quality_report": {
                "summary": {"score": 98}
            }
        }

        mock_job = TranslationJobQueue(job_id=job_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_job

        service.save_audit_log(job_id, state, audit_id)

        assert mock_db_session.add.called

        audit_record = mock_db_session.add.call_args[0][0]

        assert isinstance(audit_record, AuditRecord)
        assert audit_record.audit_id == audit_id
        assert audit_record.hash_signature is not None

        # Verify hash consistency: re-compute from stored full_payload
        reconstructed_json = json.dumps(audit_record.full_payload, sort_keys=True)
        expected_hash = hashlib.sha256(reconstructed_json.encode()).hexdigest()

        assert audit_record.hash_signature == expected_hash
