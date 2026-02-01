
import pytest
import uuid
import json
import logging
from unittest.mock import patch, MagicMock
from app.services.db_service import DatabaseService
from app.services.audit_service import AuditService
from app.models.database import Document, Segment, DocumentStatus
from app.models.models import TranslationJobQueue
from app.agents.graph import app as workflow_app
from app.core.profile_enums import TranslationArchetype

# Setup Logger
logger = logging.getLogger("test_nfr")

@pytest.fixture
def db_service():
    return DatabaseService()

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
            id=doc_id, name="nfr_test.txt", 
            source_language="en", target_language="ja", 
            status="UPLOADED"
        )
        session.add(doc)
        
        # Create Segment
        # Using a safe text that won't trigger blocks unless we want it to
        seg = Segment(
            id=seg_id, document_id=doc_id, order_index=1,
            source_text="Test input for NFR validation.", 
            status="PENDING"
        )
        session.add(seg)
        
        # Create Job
        job = TranslationJobQueue(
            job_id=job_id, request_id=f"req_{job_id}",
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
    """
    doc_id, job_id, _ = scaffold_job
    audit_id = audit_service.create_audit_trail(job_id)
    
    # We invoke the graph with this audit_id
    inputs = {
        "doc_id": doc_id,
        "target_language": "ja",
        "job_id": job_id,
        "audit_id": audit_id,
        "constraint_pack": {},
        "segments": []
    }
    
    # Mock LLM
    mock_response = MagicMock()
    mock_response.content = "Audited Translation."
    
    with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_response):
        await workflow_app.ainvoke(inputs)
        
    # Verify Integrity
    report = audit_service.verify_chain_integrity(audit_id)
    assert report["valid"] is True, f"Audit Chain Broken: {report}"
    
    # Verify specific events exist (e.g. SCORECARD_GENERATED from graph.py)
    # This requires querying the DB for events
    session = db_service.get_session()
    from app.models.models import AuditLogEntry
    events = session.query(AuditLogEntry.event_type).filter_by(audit_id=audit_id).all()
    event_types = [e[0] for e in events]
    session.close()
    
    assert "SCORECARD_GENERATED" in event_types
    # assert "JOB_STARTED" in event_types (if we logged it)

@pytest.mark.asyncio
async def test_req_nfr_03_termination_on_block(db_service, scaffold_job):
    """
    REQ-NFR-03: Workflow Termination.
    Input with Critical Defect -> BLOCKED state -> Ends.
    """
    doc_id, job_id, seg_id = scaffold_job
    
    # Inject Critical Defect Input into DB Segment
    session = db_service.get_session()
    seg = session.query(Segment).filter_by(id=seg_id).first()
    seg.source_text = "10 mg daily"
    seg.translated_text = "100 mg daily" # CRITICAL NUMERIC ERROR
    # (Pre-populating translation to simulate 'Draft' phase output if we were testing just gates,
    # but to test full graph, we need the LLM to output this.
    # We'll mock the LLM to output the error).
    seg.status = "PENDING"
    session.commit()
    session.close()
    
    mock_bad_response = MagicMock()
    mock_bad_response.content = "100 mg daily" # Will trigger Numeric Fail
    
    inputs = {
        "doc_id": doc_id,
        "target_language": "fr", # Using FR for simple numeric/unit check
        "job_id": job_id,
        "constraint_pack": {},
        "segments": []
    }
    
    with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_bad_response):
        final_state = await workflow_app.ainvoke(inputs)
        
    assert final_state['quality_report']['status'] == "BLOCKED"
    # Ensure no infinite loop (ainvoke returns, so it terminated)

if __name__ == "__main__":
    pytest.main([__file__])
