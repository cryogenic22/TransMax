"""Tests for tamper detection in audit chain."""
import pytest
from app.services.audit_service import AuditService
from app.services.db_service import DatabaseService


@pytest.fixture
def audit_svc():
    """TMX-3012: enter tenant context for direct DB tests."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    with org_context(DEFAULT_ORG_ID):
        yield AuditService()


@pytest.fixture
def job_with_audit(audit_svc):
    """Create a job audit trail with several events."""
    import uuid
    from app.models.models import TranslationJobQueue
    from app.models.database import DEFAULT_ORG_ID

    job_id = str(uuid.uuid4())

    # TMX-3011 added a FK from audit_records_queue.job_id to
    # translation_jobs_queue.job_id. Create the parent row first so the
    # audit_svc.create_audit_trail insert satisfies the constraint.
    db = DatabaseService()
    session = db.get_session()
    try:
        session.add(TranslationJobQueue(
            job_id=job_id,
            organization_id=DEFAULT_ORG_ID,
            request_id=f"req_{job_id}",
            source_language="en",
            target_language="fr",
            status="PROCESSING",
            request_json={},
        ))
        session.commit()
    finally:
        session.close()

    audit_id = audit_svc.create_audit_trail(job_id)

    audit_svc.log_event(audit_id, "JOB_STARTED", {"doc_id": "test"})
    audit_svc.log_event(audit_id, "TRANSLATION_COMPLETE", {"segments": 5})
    audit_svc.log_event(audit_id, "SCORECARD_GENERATED", {"status": "PASS"})

    return audit_id, job_id


def test_intact_chain_verifies(audit_svc, job_with_audit):
    """An untampered chain should verify as valid."""
    audit_id, _ = job_with_audit
    report = audit_svc.verify_chain_integrity(audit_id)
    assert report["valid"] is True


def test_tampered_payload_detected(audit_svc, job_with_audit):
    """Modifying a payload should break the hash chain."""
    audit_id, _ = job_with_audit

    # Tamper: change the payload of the second entry
    db = DatabaseService()
    session = db.get_session()
    from app.models.models import AuditLogEntry
    entry = (
        session.query(AuditLogEntry)
        .filter_by(audit_id=audit_id, sequence_index=1)
        .first()
    )
    assert entry is not None
    entry.payload = {"segments": 999, "tampered": True}
    session.commit()
    session.close()

    report = audit_svc.verify_chain_integrity(audit_id)
    assert report["valid"] is False
    assert report["broken_at"] == 1
    assert "Tampered" in report["details"]


def test_tampered_link_detected(audit_svc, job_with_audit):
    """Modifying the previous_hash link should be detected."""
    audit_id, _ = job_with_audit

    db = DatabaseService()
    session = db.get_session()
    from app.models.models import AuditLogEntry
    entry = (
        session.query(AuditLogEntry)
        .filter_by(audit_id=audit_id, sequence_index=2)
        .first()
    )
    assert entry is not None
    entry.previous_hash = "FAKE_HASH_VALUE"
    session.commit()
    session.close()

    report = audit_svc.verify_chain_integrity(audit_id)
    assert report["valid"] is False
    assert report["broken_at"] == 2


def test_verify_endpoint_returns_correct_status(audit_svc, job_with_audit):
    """The /verify endpoint should return is_tampered=False for a clean chain."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.main import app

    with patch("app.main.init_db"):
        client = TestClient(app)

    audit_id, _ = job_with_audit
    response = client.get(f"/api/v1/audit/{audit_id}/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["audit_id"] == audit_id
    assert data["is_tampered"] is False
    assert data["valid"] is True
