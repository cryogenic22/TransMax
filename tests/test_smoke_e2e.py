import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.agents.graph import finalize_job, TransMaxState, get_db_service, get_audit_service
from app.models.database import DocumentStatus

@pytest.mark.asyncio
async def test_graph_finalizer_audit_trigger():
    """
    Smoke Test: Verify that completing a job triggers document status update.
    """
    mock_db_svc = MagicMock()

    with patch("app.agents.graph.get_db_service", return_value=mock_db_svc):
        state = {
            "doc_id": "doc-smoke-1",
            "job_id": "job-smoke-1",
            "audit_id": "audit-smoke-1",
            "target_language": "fr",
            "quality_report": {"status": "PASS", "violations": []},
            "iteration_count": 0,
            "segments": [],
            "constraint_pack": {}
        }

        new_state = await finalize_job(state)

        # Verify Document Status updated
        assert mock_db_svc.update_document_status.called
        call_args = mock_db_svc.update_document_status.call_args[0]
        assert call_args[0] == "doc-smoke-1"
        assert call_args[1] == DocumentStatus.TRANSLATED.value

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_graph_finalizer_audit_trigger())
    print("PASS")
