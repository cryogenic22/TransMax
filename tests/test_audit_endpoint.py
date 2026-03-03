"""Tests for the /api/audit/{audit_id} endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.main import app
from app.models.models import AuditRecord, AuditLogEntry


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_init_db():
    with patch("app.main.init_db"):
        yield


def _make_audit_record(audit_id="aud-1", job_id="job-1"):
    rec = MagicMock()
    rec.audit_id = audit_id
    rec.job_id = job_id
    rec.final_decision = "PASS"
    rec.chain_head_hash = "abc123"
    rec.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return rec


def _make_entry(seq, event_type, payload=None):
    e = MagicMock()
    e.sequence_index = seq
    e.event_type = event_type
    e.timestamp = datetime(2025, 1, 1, 0, seq, tzinfo=timezone.utc)
    e.entry_hash = f"hash_{seq}"
    e.payload = payload or {"info": f"step_{seq}"}
    return e


def _build_mock_session(record, entries):
    """Build a mock session that routes query(AuditRecord) vs query(AuditLogEntry)."""
    mock_session = MagicMock()

    record_chain = MagicMock()
    record_chain.filter.return_value.first.return_value = record

    entry_chain = MagicMock()
    entry_chain.filter.return_value.order_by.return_value.all.return_value = entries

    def route_query(model):
        if model is AuditRecord:
            return record_chain
        if model is AuditLogEntry:
            return entry_chain
        return MagicMock()

    mock_session.query.side_effect = route_query
    return mock_session


def test_audit_log_returns_entries():
    """GET /api/audit/{id} should return record + entries + integrity."""
    record = _make_audit_record()
    entries = [_make_entry(0, "JOB_STARTED"), _make_entry(1, "TRANSLATION_COMPLETE")]
    mock_session = _build_mock_session(record, entries)

    with patch.object(__import__("app.services.db_service", fromlist=["DatabaseService"]).DatabaseService,
                      "get_session", return_value=mock_session), \
         patch.object(__import__("app.services.audit_service", fromlist=["AuditService"]).AuditService,
                      "verify_chain_integrity",
                      return_value={"valid": True, "details": "Integrity Verified"}):

        response = client.get("/api/v1/audit/aud-1")

    assert response.status_code == 200
    data = response.json()
    assert data["audit_id"] == "aud-1"
    assert data["job_id"] == "job-1"
    assert data["is_tampered"] is False
    assert len(data["entries"]) == 2
    assert data["entries"][0]["event_type"] == "JOB_STARTED"
    assert data["entries"][1]["event_type"] == "TRANSLATION_COMPLETE"


def test_audit_log_not_found_returns_404():
    """GET /api/audit/{id} should return 404 for unknown audit_id."""
    mock_session = _build_mock_session(None, [])

    with patch.object(__import__("app.services.db_service", fromlist=["DatabaseService"]).DatabaseService,
                      "get_session", return_value=mock_session):
        response = client.get("/api/v1/audit/nonexistent")

    assert response.status_code == 404


def test_audit_log_shows_tampered():
    """GET /api/audit/{id} should flag tampered chains."""
    record = _make_audit_record()
    mock_session = _build_mock_session(record, [])

    with patch.object(__import__("app.services.db_service", fromlist=["DatabaseService"]).DatabaseService,
                      "get_session", return_value=mock_session), \
         patch.object(__import__("app.services.audit_service", fromlist=["AuditService"]).AuditService,
                      "verify_chain_integrity",
                      return_value={"valid": False, "broken_at": 1, "details": "Content Tampered"}):

        response = client.get("/api/v1/audit/aud-1")

    assert response.status_code == 200
    data = response.json()
    assert data["is_tampered"] is True
    assert data["integrity"]["broken_at"] == 1
