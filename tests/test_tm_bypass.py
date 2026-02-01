
import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.graph import compile_constraints, draft_translate, TransMaxState
from app.models.models import TMSegment
from app.models.database import Segment

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
        
        # 1. Setup find_best_match responses
        def side_effect_find(source_text, source_lang, target_lang):
            if source_text == "Hello":
                return {"type": "TM_EXACT", "target": "Bonjour", "score": 1.0}
            return None
        
        mock_db_service.find_best_match.side_effect = side_effect_find
        mock_db_service.get_constraints.return_value = {"glossary": [], "tm_matches": []}
        
        # 2. Run 'compile_constraints'
        state = await compile_constraints(state)
        
        # Assertions on State
        assert state['segments'][0].get('tm_match') is not None
        assert state['segments'][0]['tm_match']['target'] == "Bonjour"
        assert state['segments'][1].get('tm_match') is None
        
        # 3. Request Mocks for LLM
        with patch("app.agents.graph.get_llm") as mock_get_llm:
            mock_llm_obj = MagicMock()
            mock_get_llm.return_value = mock_llm_obj
            
            with patch("app.agents.graph.ResilienceService.resilient_llm_call") as mock_resilience:
                # Mock LLM Response for 'World'
                async def mock_invoke(*args, **kwargs):
                    return MagicMock(content='```json\n{"segments": [{"id": "2", "target_text": "Monde"}]}\n```')
                
                mock_resilience.side_effect = mock_invoke
                # Or just mock the return value if not checking args
                
                # 4. Run 'draft_translate'
                state = await draft_translate(state)
                
                # VERIFY BYPASS: LLM should ONLY receive segment 2
                # We check the arguments passed to llm.ainvoke (inside resilient call)
                # ResilienceService.resilient_llm_call(llm.ainvoke, messages)
                # We need to inspect 'messages'
                
                call_args = mock_resilience.call_args
                # args[0] is function, args[1] is messages
                messages = call_args[0][1] 
                user_msg = messages[1].content
                
                # Crucial Assertions
                assert '"text": "World"' in user_msg
                assert '"text": "Hello"' not in user_msg, "Exact Match Segment leaked to LLM!"
                
                # Verify Final State
                # Segment 1: From TM
                assert state['segments'][0]['translated_text'] == "Bonjour"
                # Segment 2: From LLM
                assert state['segments'][1]['translated_text'] == "Monde"

if __name__ == "__main__":
    asyncio.run(test_graph_tm_bypass())
    test_db_service_exact_match()
    print("Graph TM Bypass Integrity: VERIFIED")

