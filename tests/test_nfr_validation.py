
import pytest
import uuid
import json
import logging
from unittest.mock import patch, MagicMock
from app.services.db_service import DatabaseService
from app.services.audit_service import AuditService
from app.models.database import Document, Segment, DocumentStatus, DEFAULT_ORG_ID
from app.models.models import TranslationJobQueue
from app.agents.graph import app as workflow_app
from app.core.profile_enums import TranslationArchetype

# Setup Logger
logger = logging.getLogger("test_nfr")

@pytest.fixture
def db_service():
    """TMX-3012: enter tenant context for direct DB tests."""
    from app.core.tenant_context import org_context
    service = DatabaseService()
    with org_context(DEFAULT_ORG_ID):
        yield service

@pytest.fixture
def audit_service():
    return AuditService()

@pytest.fixture
def scaffold_job(db_service):
    """
    Creates a valid job execution environment in the DB.
    Returns: (doc_id, job_id, segment_id)
    """
    job_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    seg_id = str(uuid.uuid4())
    
    session = db_service.get_session()
    try:
        # Create Doc
        doc = Document(
            id=doc_id, organization_id=DEFAULT_ORG_ID, name="nfr_test.txt",
            source_language="en", target_language="ja",
            status="UPLOADED"
        )
        session.add(doc)

        # Create Segment
        seg = Segment(
            id=seg_id, organization_id=DEFAULT_ORG_ID, document_id=doc_id, order_index=1,
            source_text="Test input for NFR validation.",
            status="PENDING"
        )
        session.add(seg)

        # Create Job
        job = TranslationJobQueue(
            job_id=job_id, organization_id=DEFAULT_ORG_ID, request_id=f"req_{job_id}",
            source_language="en", target_language="ja",
            status="PROCESSING", request_json={"source": "Test input"}
        )
        session.add(job)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        
    return doc_id, job_id, seg_id

@pytest.mark.asyncio
async def test_req_nfr_01_determinism(db_service, scaffold_job):
    """
    REQ-NFR-01: Deterministic Replay.
    Same inputs + Same Config (mocked LLM) -> Identical Outcome.
    """
    doc_id, job_id, _ = scaffold_job
    
    inputs = {
        "doc_id": doc_id,
        "target_language": "ja",
        "job_id": job_id,
        "audit_id": str(uuid.uuid4()), # New audit trace for run
        "constraint_pack": {"archetype": TranslationArchetype.SAFETY_CRITICAL},
        "segments": []
    }
    
    # Mock LLM to return constant string
    mock_response = MagicMock()
    mock_response.content = "Deterministic Translation output."
    
    # Mock DB Service to prevent SQL transaction aborts affecting the logic test
    mock_db = MagicMock()
    mock_db.get_document_status.return_value = "PROCESSING" # Allow validation to pass
    
    with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_response), \
         patch("app.agents.graph.get_db_service", return_value=mock_db):
        
        # Run 1
        state_1 = await workflow_app.ainvoke(inputs)
        
    # Re-scaffold inputs (logic only)
    inputs_2 = {
        "doc_id": doc_id, 
        "target_language": "ja",
        "job_id": job_id,
        "audit_id": str(uuid.uuid4()),
        "constraint_pack": {"archetype": TranslationArchetype.SAFETY_CRITICAL},
        "segments": []
    }
    
    with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_response), \
         patch("app.agents.graph.get_db_service", return_value=mock_db):
        state_2 = await workflow_app.ainvoke(inputs_2)
        
    # Assert Outputs Match (Safe Access)
    assert state_1.get('final_decision') == state_2.get('final_decision')
    assert state_1.get('quality_report', {}).get('status') == state_2.get('quality_report', {}).get('status')

@pytest.mark.asyncio
async def test_req_nfr_02_audit_integrity(db_service, audit_service, scaffold_job):
    """
    REQ-NFR-02: Audit Chain Integrity.
    Verifies that the audit log was created, populated, and has a valid hash chain.
    The graph creates its own audit trail in validate_request, so we query by job_id after.
    """
    doc_id, job_id, _ = scaffold_job

    # Build a proper JSON response the translation engine can parse
    seg_session = db_service.get_session()
    seg_rows = seg_session.query(Segment).filter_by(document_id=doc_id).all()
    seg_ids = [s.id for s in seg_rows]
    seg_session.close()

    mock_json = json.dumps({
        "segments": [{"id": sid, "target_text": "監査済み翻訳。"} for sid in seg_ids]
    })
    mock_response = MagicMock()
    mock_response.content = mock_json

    inputs = {
        "doc_id": doc_id,
        "target_language": "ja",
        "job_id": job_id,
        "constraint_pack": {},
        "segments": []
    }

    with patch("langchain_openai.ChatOpenAI.ainvoke", return_value=mock_response):
        await workflow_app.ainvoke(inputs)

    # The graph creates its own audit trail — query by job_id to find it
    session = db_service.get_session()
    from app.models.models import AuditRecord, AuditLogEntry
    record = session.query(AuditRecord).filter_by(job_id=job_id).order_by(AuditRecord.created_at.desc()).first()
    assert record is not None, "No audit record found for job"
    actual_audit_id = record.audit_id

    # Verify Integrity
    report = audit_service.verify_chain_integrity(actual_audit_id)
    assert report["valid"] is True, f"Audit Chain Broken: {report}"

    # Verify events exist
    events = session.query(AuditLogEntry.event_type).filter_by(audit_id=actual_audit_id).all()
    event_types = [e[0] for e in events]
    session.close()

    assert "JOB_STARTED" in event_types
    assert "SCORECARD_GENERATED" in event_types

@pytest.mark.asyncio
async def test_req_nfr_03_termination_on_block(db_service, scaffold_job):
    """
    REQ-NFR-03: Workflow Termination.
    Input with Critical Defect -> BLOCKED state -> Ends.
    """
    doc_id, job_id, seg_id = scaffold_job

    # Inject pharma source text
    session = db_service.get_session()
    seg = session.query(Segment).filter_by(id=seg_id).first()
    seg.source_text = "10 mg daily"
    seg.status = "PENDING"
    session.commit()
    session.close()

    # Mock LLM to return proper JSON with a WRONG number (100 instead of 10)
    mock_json = json.dumps({
        "segments": [{"id": seg_id, "target_text": "100 mg par jour"}]
    })
    mock_bad_response = MagicMock()
    mock_bad_response.content = mock_json

    inputs = {
        "doc_id": doc_id,
        "target_language": "fr",
        "job_id": job_id,
        "constraint_pack": {},
        "segments": []
    }

    with patch("langchain_openai.ChatOpenAI.ainvoke", return_value=mock_bad_response):
        final_state = await workflow_app.ainvoke(inputs)

    assert final_state['quality_report']['status'] == "BLOCKED"
    # Ensure no infinite loop (ainvoke returns, so it terminated)

if __name__ == "__main__":
    pytest.main([__file__])
