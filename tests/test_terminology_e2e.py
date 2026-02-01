
import pytest
import sys
import os
# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch
import json
import asyncio
from app.agents.graph import app
from app.models.database import Segment, Document, DocumentStatus, SegmentStatus

# Mock DB Session
class InMemorySession:
    def __init__(self):
        self.store = {}
        self.segments = []
        
    def query(self, model):
        self.current_model = model
        return self
        
    def filter(self, condition):
        return self
        
    def order_by(self, *args):
        return self
        
    def first(self):
        if self.current_model == Document:
            return MagicMock(status=DocumentStatus.PROCESSING)
        if self.current_model == Segment:
            # Return a mock segment that we can inspect
            seg = MagicMock()
            seg.id = "seg-1"
            seg.source_text = "Please drink 2 tablets with water."
            seg.order_index = 0
            seg.translated_text = None
            return seg
        return None
        
    def all(self):
        if self.current_model == Segment:
            seg = MagicMock()
            seg.id = "seg-1"
            seg.source_text = "Please drink 2 tablets with water."
            seg.order_index = 0
            return [seg]
        return []
        
    def add(self, obj):
        pass
        
    def commit(self):
        pass
        
    def close(self):
        pass
        
    def close(self):
        pass
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __getattr__(self, name):
        # Universal mock for missing methods
        def method(*args, **kwargs):
            print(f"DEBUG: InMemorySession.{name} called with {args}")
            return MagicMock()
        return method

@pytest.mark.asyncio
async def test_forbidden_term_enforcement():
    """
    E2E Test:
    1. Input: "Please drink 2 tablets"
    2. Constraint: Forbidden "Drink", Reason "Use Take".
    3. Verify LLM produces "Take" (or at least avoids "Drink").
    4. Verify Quality Gate Passes.
    """
    
    # Mock DB Service to return strict constraints
    with patch('app.agents.graph.db_service') as mock_db_service:
            
        # Setup Content
        
        # Constraints: Forbid "Boire"
        mock_db_service.get_constraints.return_value = {
            "glossary": [],
            "forbidden_terms": [
                {"term": "Boire", "severity": "critical", "reason": "Use 'Prendre' for medication."}
            ],
            "tm_matches": []
        }
        
        # Mock Document Status
        mock_db_service.get_document_status.return_value = "PROCESSING"
        
        # Mock Segments
        mock_db_service.get_segments_for_doc.return_value = [
            {
                "segment_id": "seg-1",
                "source_text": "Please drink 2 tablets with water.",
                "order_index": 0,
                "translated_text": None,
                "status": "PENDING"
            }
        ]
        
        inputs = {
            "doc_id": "doc-test-1",
            "target_language": "fr"
        }

        print("Invoking Agent...")
        # Since we are mocking app.agents.graph.db_service, and app is imported from app.agents.graph
        # The mock should apply.
        
        # However, app is compiled at module level. Nodes bind to service instances.
        # If nodes use global variables, patching imports works.
        # graph.py: db_service = DatabaseService()
        # nodes use this global db_service.
        # So patch('app.agents.graph.db_service') works.
        
        final_state = await app.ainvoke(inputs)
        
        print("Final State Quality Report:", final_state.get('quality_report'))
        segments = final_state.get('segments', [])
        if not segments:
            pytest.fail("No segments returned")
            
        translation = segments[0].get('translated_text', '').lower()
        print(f"Translation: {translation}")
        
        # Assertions
        assert "boire" not in translation, "LLM failed to respect forbidden term 'Boire'"
        assert "prendre" in translation or "prenez" in translation, "LLM should have used the preferred term"
        
        # Check Quality Gate Report
        # Should have 0 violations if LLM succeeded
        violations = final_state.get('quality_report', {}).get('violations', [])
        forbidden_violations = [v for v in violations if v['type'] == 'forbidden_term']
        assert len(forbidden_violations) == 0, f"Quality Gate flagged violations: {forbidden_violations}"

if __name__ == "__main__":
    # verification helper
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_forbidden_term_enforcement())
    print("Test Passed!")
