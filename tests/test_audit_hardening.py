import pytest
import json
import hashlib
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.services.db_service import DatabaseService
from app.models.models import AuditRecord
from app.api.v1.audit import get_audit_record
from fastapi import HTTPException

def test_audit_record_population():
    """Verify DBService.save_audit_log populates new schema fields."""
    mock_db = MagicMock()

    with patch("app.services.db_service.SessionLocal", return_value=mock_db):
        service = DatabaseService()

        job_id = "job-123"
        audit_id = "audit-999"
        state = {
            "final_decision": "APPROVED",
            "quality_report": {"violations": []},
            "versions": {
                "model": "gpt-4",
                "prompts": "v2",
                "glossary": "v1.1",
                "policy": "v1.0"
            },
            "iteration_count": 1
        }

        mock_job = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        service.save_audit_log(job_id, state, audit_id)

        assert mock_db.add.called
        args = mock_db.add.call_args[0]
        record = args[0]

        assert isinstance(record, AuditRecord)
        assert record.audit_id == audit_id
        assert record.policy_version == "v1.0"
        assert record.glossary_version == "v1.1"
        assert record.full_payload is not None
        assert record.hash_signature is not None

        # Verify Hash Logic (TMX-021)
        ref_payload = record.full_payload
        ref_json = json.dumps(ref_payload, sort_keys=True)
        expected_hash = hashlib.sha256(ref_json.encode()).hexdigest()

        assert record.hash_signature == expected_hash

def test_audit_endpoint_retrieval():
    """Verify API mapping from DB Record to Schema."""
    mock_db = MagicMock()
    record = AuditRecord(
        audit_id="audit-test-1",
        job_id="job-test-1",
        final_decision="BLOCKED",
        model_version="v1",
        prompt_version="v1",
        glossary_version="v1",
        language_pack_version="v1",
        policy_version="v1",
        full_payload={"foo": "bar"},
        hash_signature="abc12345",
        created_at=datetime.utcnow()
    )

    mock_db.query.return_value.filter.return_value.first.return_value = record

    response = get_audit_record("audit-test-1", db=mock_db)

    assert response.audit_id == "audit-test-1"
    assert response.versions['policy'] == "v1"
    assert response.versions['model'] == "v1"
    assert response.full_payload == {"foo": "bar"}

if __name__ == "__main__":
    try:
        test_audit_record_population()
        print("PASS test_audit_record_population")
        test_audit_endpoint_retrieval()
        print("PASS test_audit_endpoint_retrieval")
    except Exception as e:
        import traceback
        traceback.print_exc()
