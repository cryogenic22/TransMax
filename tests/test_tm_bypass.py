
import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.graph import compile_constraints
from app.models.models import TMSegment

# --- Rigorous Mock DB ---
class MockQuery:
    def __init__(self, data):
        self.data = data
        
    def filter(self, *args):
        # Extremely basic logical filtering simulation
        # In this test, we know exactly what queries are made.
        # find_best_match queries TMSegment by source/source_lang/target_lang
        
        # We assume args[0] might be a comparison expression.
        # This is hard to mock generically. We will just return self for now
        # and impl 'first' to return specific things based on context.
        return self
        
    def order_by(self, *args):
        return self
        
    def first(self):
        # We need context. 
        # But wait, db_service.find_best_match uses: 
        # db.query(TMSegment).filter(TMSegment.source_text == source_text, ...).first()
        
        # We can mock the 'db_service.find_best_match' directly?
        # That tests the GRAPH logic, but not the DB logic.
        # Given "Detailed rigor", we should test the DB logic too.
        # But testing SQLAlchemy filter expressions with a mock is insane.
        
        # Approach: Mock the DB Session's query() to return a "Smart Mock" 
        # that knows what to return based on what was passed to filter logic?
        # Too complex.
        
        # Better: Mock 'db_service.find_best_match' to test GRAPH logic.
        # And Mock 'db_service.get_session' to returns a session that can be inspected.
        return None

# We will test GRAPH logic and DB logic separately for rigor.

# TEST 1: DB Service Logic
from app.services.db_service import DatabaseService

def test_db_service_exact_match():
    service = DatabaseService()
    
    # Mock Session
    mock_session = MagicMock()
    service.get_session = MagicMock(return_value=mock_session)
    
    # Mock Query Return for Exact Match
    mock_tm = TMSegment(source_text="Hello", target_text="Bonjour")
    mock_session.query.return_value.filter.return_value.first.return_value = mock_tm
    
    match = service.find_best_match("Hello", "en", "fr")
    
    assert match is not None
    assert match['type'] == 'TM_EXACT'
    assert match['target'] == 'Bonjour'
    assert match['score'] == 1.0

# TEST 2: Graph Logic (The Pipeline Integrity)
@pytest.mark.asyncio
async def test_graph_tm_bypass():
    # Setup State
    state = {
        "target_language": "fr",
        "segments": [
            {"segment_id": "1", "source_text": "Hello", "translated_text": None}, # Should match
            {"segment_id": "2", "source_text": "World", "translated_text": None}  # Should NOT match
        ],
        "constraint_pack": {}
    }
    
    # Mock DB Service behaviors
    # Patch the getter, so get_db_service() returns our mock
    with patch("app.agents.graph.get_db_service") as mock_get_db:
        mock_db_service = MagicMock()
        mock_get_db.return_value = mock_db_service
        
        # 1. Setup find_exact_matches_batch response (batch replaces per-segment calls)
        mock_db_service.find_exact_matches_batch.return_value = {
            "1": {"type": "TM_EXACT", "target": "Bonjour", "score": 1.0}
        }
        mock_db_service.get_constraints.return_value = {"glossary": [], "tm_matches": []}
        
        # 2. Run 'compile_constraints'
        state = await compile_constraints(state)
        
        # Assertions on State
        assert state['segments'][0].get('tm_match') is not None
        assert state['segments'][0]['tm_match']['target'] == "Bonjour"
        assert state['segments'][1].get('tm_match') is None

    # TMX-GRAPH-DEADCODE: TM-bypass is now verified against the LIVE production
    # engine (translation_engine._separate_tm_matches), not the retired
    # draft_translate node. The engine pre-fills TM-exact segments and routes
    # only the rest to the LLM, so an exact match never reaches a model.
    from app.agents.nodes.translation_engine import TranslationEngine

    engine = TranslationEngine()
    units = engine._prepare_segment_units(state['segments'])
    tm_units, llm_units = engine._separate_tm_matches(units)

    tm_ids = {u.segment_id for u in tm_units}
    llm_ids = {u.segment_id for u in llm_units}

    # Segment 1 (TM exact) bypasses the LLM: pre-filled, in tm_units, NOT in llm.
    assert "1" in tm_ids, "TM exact match should bypass the LLM"
    assert "1" not in llm_ids, "Exact Match Segment leaked to LLM!"
    seg1 = next(u for u in tm_units if u.segment_id == "1")
    assert seg1.translated_text == "Bonjour"

    # Segment 2 (no match) must be routed to the LLM.
    assert "2" in llm_ids, "Non-matched segment must go to the LLM"

if __name__ == "__main__":
    asyncio.run(test_graph_tm_bypass())
    test_db_service_exact_match()
    print("Graph TM Bypass Integrity: VERIFIED")

