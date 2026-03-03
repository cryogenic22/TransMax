
import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch, AsyncMock
import json
import asyncio
from app.agents.graph import TransMaxState
from app.models.database import Segment, Document, DocumentStatus, SegmentStatus

@pytest.mark.asyncio
async def test_forbidden_term_enforcement():
    """
    E2E Test:
    1. Input: "Please drink 2 tablets"
    2. Constraint: Forbidden "Boire"
    3. Verify Quality Gate detects forbidden term if present.
    """
    mock_db_svc = MagicMock()
    mock_audit_svc = MagicMock()

    mock_db_svc.get_constraints.return_value = {
        "glossary": [],
        "forbidden_terms": [
            {"term": "Boire", "severity": "critical", "reason": "Use 'Prendre' for medication."}
        ],
        "tm_matches": []
    }
    mock_db_svc.get_document_status.return_value = "PROCESSING"
    mock_db_svc.get_document_metadata.return_value = {"source_language": "en"}
    mock_db_svc.get_segments_for_doc.return_value = [
        {
            "segment_id": "seg-1",
            "source_text": "Please drink 2 tablets with water.",
            "order_index": 0,
            "translated_text": None,
            "status": "PENDING"
        }
    ]
    mock_db_svc.find_best_match.return_value = None
    mock_db_svc.update_segments_batch.return_value = None
    mock_db_svc.update_document_status.return_value = None
    mock_db_svc.save_quality_scorecard.return_value = None

    mock_audit_svc.create_audit_trail.return_value = "audit-test-1"
    mock_audit_svc.capture_config_snapshot.return_value = None
    mock_audit_svc.log_event.return_value = None

    # Mock LLM to return translation with forbidden term
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "segments": [{"segment_id": "seg-1", "target_text": "Veuillez boire 2 comprimés avec de l'eau."}]
    })

    with patch("app.agents.graph.get_db_service", return_value=mock_db_svc):
        with patch("app.agents.graph.get_audit_service", return_value=mock_audit_svc):
            # Run just the quality gates to test forbidden term detection
            from app.agents.graph import run_quality_gates

            state = {
                "doc_id": "doc-test-1",
                "target_language": "fr",
                "source_language": "en",
                "iteration_count": 0,
                "segments": [{
                    "segment_id": "seg-1",
                    "source_text": "Please drink 2 tablets with water.",
                    "translated_text": "Veuillez boire 2 comprimés avec de l'eau.",
                }],
                "constraint_pack": {
                    "glossary": [],
                    "forbidden_terms": [
                        {"term": "boire", "severity": "critical", "reason": "Use 'prendre'."}
                    ],
                    "tm_matches": []
                }
            }

            final_state = await run_quality_gates(state)

            violations = final_state.get('quality_report', {}).get('violations', [])
            forbidden_violations = [v for v in violations if v['category'] == 'TERMINOLOGY' and 'Forbidden' in v['message']]
            assert len(forbidden_violations) >= 1, f"Expected forbidden term violation. Got: {violations}"

if __name__ == "__main__":
    asyncio.run(test_forbidden_term_enforcement())
    print("Test Passed!")
