import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.agents.graph import finalize_job, TransMaxState
from app.models.database import DocumentStatus

@pytest.mark.asyncio
async def test_graph_finalizer_audit_trigger():
    """
    Smoke Test: Verify that completing a job triggers the audit log save.
    This ensures the link between Agent and TMX-020 is active.
    """
    # Mock DB Service used in graph.py
    with patch("app.agents.graph.db_service") as mock_db_service:
        # State simulating a completed job
        state = {
            "doc_id": "doc-smoke-1",
            "job_id": "job-smoke-1",
            "target_language": "fr",
            "quality_report": {"status": "PASS", "violations": []},
            "iteration_count": 0,
            "segments": [],
            "constraint_pack": {}
        }
        
        # Run Finalizer
        new_state = await finalize_job(state)
        
        # Verify Audit Log Save called
        assert mock_db_service.save_audit_log.called
        args = mock_db_service.save_audit_log.call_args
        # args[0] is (job_id, state, audit_id)
        assert args[0][0] == "job-smoke-1" 
        assert args[0][1] == state # State passed
        
        # Verify Document Status updated
        assert mock_db_service.update_document_status.called
        assert mock_db_service.update_document_status.call_args[0][1] == str(DocumentStatus.TRANSLATED)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_graph_finalizer_audit_trigger())
        print("PASS test_graph_finalizer_audit_trigger")
    except Exception as e:
        import traceback
        traceback.print_exc()
