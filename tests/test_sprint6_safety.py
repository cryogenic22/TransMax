import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import json
import sys
import os

# Ensure app can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.graph import app as graph_app, TransMaxState
from app.models.database import Segment, DocumentStatus
from app.models.models import TMSegment

# --- Mocks ---
class MockQuery:
    def __init__(self, items=None):
        self.items = items or []
        
    def filter(self, *args, **kwargs):
        return self
        
    def order_by(self, *args, **kwargs):
        return self
        
    def all(self):
        return self.items
        
    def first(self):
        return self.items[0] if self.items else None

class InMemorySession:
    def __init__(self, segments=None):
        self.segments = segments or []
        
    def add(self, obj):
        pass
        
    def commit(self):
        pass
        
    def rollback(self):
        pass
        
    def close(self):
        pass
        
    def query(self, model):
        return MockQuery(self.segments)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def __getattr__(self, name):
        # Universal fallback for missing methods (refresh, delete, etc)
        def method(*args, **kwargs):
            return MagicMock()
        return method

# --- Tests ---

async def test_critical_block_no_refinement():
    """
    Scenario: Critical Number Mismatch.
    Expected: Status BLOCKED immediately. No Refinement Loop.
    """
    print("\n--- Test: Critical Block (Number Mismatch) ---")
    
    # 1. Setup Data: Source "10mg", Translation "20mg" (Critical Error)
    segment = MagicMock(spec=Segment)
    segment.id = "seg-1"
    segment.source_text = "Dose: 10mg"
    segment.translated_text = "Dose: 20mg" # Bad translation
    segment.order_index = 1
    segment.gate_results = {}
    segment.status = "DRAFT"
    
    mock_db = InMemorySession([segment])
    
    # 2. Mock Services
    with patch("app.agents.graph.get_db_session", return_value=mock_db):
        with patch("app.services.db_service.DatabaseService.get_constraints", return_value={"glossary": []}):
            with patch("app.services.db_service.DatabaseService.find_best_match", return_value=None):
                 # Mock LLM for Refinement (Should NOT be called)
                 with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=AsyncMock) as mock_llm:
                    
                     # 3. Initialize State
                     initial_state = {
                         "doc_id": "doc-safety-1",
                         "target_language": "fr",
                         "iteration_count": 0,
                         "segments": [{
                             "segment_id": "seg-1", "source_text": "Dose: 10mg", "translated_text": "Dose: 20mg"
                         }]
                     }
                     
                     from app.agents.graph import run_quality_gates, decide_next_step
                     
                     # Run Gates
                     state_after_gates = await run_quality_gates(initial_state)
                     
                     # Check Report
                     report = state_after_gates['quality_report']
                     print(f"Report Status: {report.get('status')}")
                     assert report['status'] == "BLOCKED"
                     
                     # Check Decision
                     decision = decide_next_step(state_after_gates)
                     print(f"Decision: {decision}")
                     assert decision == "finalize" # Should exit, NOT refine
                     
                     # Ensure Refinement LLM was NOT called
                     mock_llm.assert_not_called()

async def test_refinement_loop_fix():
    """
    Scenario: Non-Critical Missing Term.
    Expected: Status REVIEW_REQUIRED -> Refinement -> Fix -> Status PASS.
    """
    print("\n--- Test: Refinement Loop (Missing Term) ---")
    
    # 1. Setup Data: Source "Take Pill", Translation "Prendre" (Missing "Pill")
    # Glossary: Pill -> Comprimé (Mandatory)
    segment = MagicMock(spec=Segment)
    segment.id = "seg-refine-1"
    segment.source_text = "Take Pill"
    segment.translated_text = "Prendre" # Missing "Comprimé"
    segment.order_index = 1
    
    mock_db = InMemorySession([segment])
    
    glossary = [{"source": "Pill", "target": "Comprimé"}]
    
    with patch("app.agents.graph.get_db_session", return_value=mock_db):
         with patch("app.services.db_service.DatabaseService.get_constraints", return_value={"glossary": glossary}):
              with patch("app.services.db_service.DatabaseService.find_best_match", return_value=None):
                  
                  # Mock LLM used in 'refine_translation'
                  mock_response = MagicMock()
                  # Mocking the output to match FIXER structure
                  mock_response.content = json.dumps({
                      "fixed_segments": [{"segment_id": "seg-refine-1", "target_text": "Prendre Comprimé", "applied_actions": ["Added missing term"]}]
                  })
                  
                  with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=AsyncMock) as mock_llm:
                      mock_llm.return_value = mock_response
                      
                      initial_state = {
                          "doc_id": "doc-refine-1",
                          "target_language": "fr", 
                          "iteration_count": 0,
                          "segments": [{
                              "segment_id": "seg-refine-1", "source_text": "Take Pill", "translated_text": "Prendre",
                              "source_index": 1
                          }],
                          "constraint_pack": {"glossary": glossary}
                      }
                      
                      from app.agents.graph import run_quality_gates, decide_next_step, refine_translation
                      
                      # 1. Run Gates (First Pass)
                      state_1 = await run_quality_gates(initial_state)
                      print(f"Pass 1 Status: {state_1['quality_report']['status']}")
                      assert state_1['quality_report']['status'] == "REVIEW_REQUIRED" 
                      
                      decision_1 = decide_next_step(state_1)
                      assert decision_1 == "refine"
                      
                      # 2. Run Refinement
                      state_2 = await refine_translation(state_1)
                      assert state_2['iteration_count'] == 1
                      assert state_2['segments'][0]['translated_text'] == "Prendre Comprimé"
                      
                      # 3. Run Gates (Second Pass)
                      state_3 = await run_quality_gates(state_2)
                      print(f"Pass 2 Status: {state_3['quality_report']['status']}")
                      assert state_3['quality_report']['status'] == "PASS"
                      
                      decision_2 = decide_next_step(state_3)
                      assert decision_2 == "finalize"


async def test_critical_unit_block():
    """
    Scenario: Critical Unit Mismatch (10mg vs 10g).
    Expected: BLOCKED.
    """
    print("\n--- Test: Critical Unit Mismatch ---")
    
    segment = MagicMock(spec=Segment)
    segment.id = "seg-unit-1"
    segment.source_text = "Dose: 10mg"
    segment.translated_text = "Dose: 10g" # Mismatch
    segment.order_index = 1
    segment.gate_results = {}
    segment.status = "DRAFT"
    
    mock_db = InMemorySession([segment])
    
    with patch("app.agents.graph.get_db_session", return_value=mock_db):
        with patch("app.services.db_service.DatabaseService.get_constraints", return_value={"glossary": []}):
            with patch("app.services.db_service.DatabaseService.find_best_match", return_value=None):
                 with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=AsyncMock) as mock_llm:
                    
                     initial_state = {
                         "doc_id": "doc-unit-1",
                         "target_language": "fr",
                         "iteration_count": 0,
                         "segments": [{
                             "segment_id": "seg-unit-1", "source_text": "Dose: 10mg", "translated_text": "Dose: 10g"
                         }]
                     }
                     
                     from app.agents.graph import run_quality_gates, decide_next_step
                     
                     state = await run_quality_gates(initial_state)
                     
                     report = state['quality_report']
                     print(f"Report Status: {report.get('status')}")
                     
                     # Check if Unit Violation exists
                     violations = report.get('violations', [])
                     unit_vs = [v for v in violations if v['type'] == 'unit_mismatch']
                     assert len(unit_vs) > 0, "Expected unit_mismatch violation"
                     assert report['status'] == "BLOCKED"
                     
                     decision = decide_next_step(state)
                     assert decision == "finalize"

async def test_critical_negation_block():
    """
    Scenario: Negation Flip (Do not -> Do).
    Expected: BLOCKED.
    """
    print("\n--- Test: Critical Negation Flip ---")
    
    segment = MagicMock(spec=Segment)
    segment.id = "seg-neg-1"
    segment.source_text = "Do not chew."
    segment.translated_text = "Chew." # Flip
    segment.order_index = 1
    
    mock_db = InMemorySession([segment])
    
    with patch("app.agents.graph.get_db_session", return_value=mock_db):
         with patch("app.services.db_service.DatabaseService.get_constraints", return_value={"glossary": []}):
            with patch("app.services.db_service.DatabaseService.find_best_match", return_value=None):
                 with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=AsyncMock) as mock_llm:
                    
                     initial_state = {
                         "doc_id": "doc-neg-1",
                         "target_language": "fr",
                         "segments": [{
                             "segment_id": "seg-neg-1", "source_text": "Do not chew.", "translated_text": "Chew."
                         }]
                     }
                     
                     from app.agents.graph import run_quality_gates, decide_next_step
                     state = await run_quality_gates(initial_state)
                     assert state['quality_report']['status'] == "BLOCKED"
                     assert decide_next_step(state) == "finalize"

async def test_critical_pii_block():
    """
    Scenario: PII Token Corruption.
    Expected: BLOCKED.
    """
    print("\n--- Test: Critical PII Integrity ---")
    
    segment = MagicMock(spec=Segment)
    segment.id = "seg-pii-1"
    segment.source_text = "Patient [[PII:NAME:A1]] arrived."
    segment.translated_text = "Patient [[PII:NAME:B2]] arrived." # WRONG TOKEN
    
    mock_db = InMemorySession([segment])
    
    with patch("app.agents.graph.get_db_session", return_value=mock_db):
         with patch("app.services.db_service.DatabaseService.get_constraints", return_value={"glossary": []}):
            with patch("app.services.db_service.DatabaseService.find_best_match", return_value=None):
                 with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=AsyncMock) as mock_llm:
                    
                     initial_state = {
                         "doc_id": "doc-pii-1",
                         "target_language": "fr",
                         "segments": [{
                             "segment_id": "seg-pii-1", "source_text": "Patient [[PII:NAME:A1]] arrived.", "translated_text": "Patient [[PII:NAME:B2]] arrived."
                         }]
                     }
                     
                     from app.agents.graph import run_quality_gates, decide_next_step
                     state = await run_quality_gates(initial_state)
                     
                     violations = state['quality_report']['violations']
                     assert any(v['type'] == 'pii_integrity_fail' for v in violations)
                     assert state['quality_report']['status'] == "BLOCKED"
                     assert decide_next_step(state) == "finalize"

if __name__ == "__main__":
    try:
        print("Starting manual test execution for Sprint 6.5...")
        asyncio.run(test_critical_block_no_refinement())
        print("test_critical_block_no_refinement: PASS")
        asyncio.run(test_refinement_loop_fix())
        print("test_refinement_loop_fix: PASS")
        asyncio.run(test_critical_unit_block())
        print("test_critical_unit_block: PASS")
        asyncio.run(test_critical_negation_block())
        print("test_critical_negation_block: PASS")
        asyncio.run(test_critical_pii_block())
        print("test_critical_pii_block: PASS")
    except Exception as e:
        import traceback
        with open("sprint6_error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        traceback.print_exc()
