
import sys
import os
import json
import asyncio
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Ad-hoc path setup
# Ad-hoc path setup
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app
print(f"DEBUG: app location: {app.__file__}")
print(f"DEBUG: app path: {app.__path__}")

from app.services.quality_gate import QualityGateService
from app.agents.graph import draft_translate, run_quality_gates, TransMaxState

# Create Output Directory
OUTPUT_DIR = "testbackend/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def params(n):
    return f"param_{n}"

class MockDBSession:
    def __init__(self):
        self.segments = {} # id -> obj
        self.docs = {}
        self.committed = False
    
    def query(self, model):
        self.current_model = model
        return self
        
    def filter(self, condition):
        # Very basic mock filtering, assumes id check
        return self
        
    def first(self):
        # Return a mock object that can hold attributes
        return MagicMock(translated_text=None, status="PENDING")
        
    def commit(self):
        self.committed = True
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def report(name, result):
    print(f"[{'PASS' if result else 'FAIL'}] {name}")

async def test_quality_gates():
    print("\n--- Testing Quality Gates ---")
    service = QualityGateService()
    
    # Test 1: Numbers
    print("Test 1: Number Mismatch")
    violations = service.check_numbers("Dose is 20 mg", "La dose est 200 mg")
    if violations and violations[0]['type'] == 'number_mismatch':
        report("Number Check (Mismatch)", True)
    else:
        report("Number Check (Mismatch)", False)
        print(f"   Got: {violations}")

    # Test 2: Units
    print("Test 2: Unit Mismatch")
    violations = service.check_units("Take 20 mg", "Prendre 20 g")
    if violations and violations[0]['type'] == 'unit_mismatch':
         report("Unit Check (Mismatch)", True)
    else:
         report("Unit Check (Mismatch)", False)
         print(f"   Got: {violations}")
         
    # Test 3: Negation
    print("Test 3: Negation Flip")
    violations = service.check_negation("Do not take this.", "Prenez ceci.")
    if violations and violations[0]['type'] == 'negation_flip':
         report("Negation Check (Flip)", True)
    else:
         report("Negation Check (Flip)", False)
         print(f"   Got: {violations}")

    # Test 4: Clean
    print("Test 4: Clean Translation")
    violations = service.check_segment("Dose 20 mg", "Dose 20 mg", {})
    if not violations:
        report("Clean Check", True)
    else:
        report("Clean Check", False)
        print(f"   Got: {violations}")
        
    # Write output
    with open(f"{OUTPUT_DIR}/gate_results.json", "w") as f:
        json.dump({"status": "completed"}, f)

@patch("app.agents.graph.get_db_session")
@patch("app.agents.graph.ResilienceService")
async def test_draft_translation_node(MockResilience, MockGetDB):
    print("\n--- Testing Draft Translate Node ---")
    
    # Mock LLM Response
    mock_response = MagicMock()
    mock_response.content = '```json\n{"segments": [{"id": "seg1", "target_text": "Ceci est le texte traduit."}]}\n```'
    
    # Fix async mock
    f = asyncio.Future()
    f.set_result(mock_response)
    MockResilience.resilient_llm_call.return_value = f
    
    # Mock DB
    mock_db = MockDBSession()
    mock_seg = MagicMock()
    mock_db.query = MagicMock(return_value=MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_seg)))))
    MockGetDB.return_value.__enter__.return_value = mock_db
    
    # State
    state: TransMaxState = {
        "doc_id": "doc1",
        "target_language": "fr",
        "segments": [{"segment_id": "seg1", "source_text": "This is source text.", "order_index": 1}],
        "constraint_pack": {},
        "quality_report": {},
        "iteration_count": 0,
        "error": None
    }
    
    # Run Node
    try:
        new_state = await draft_translate(state)
        print(f"DEBUG: New State: {new_state['segments']}")
    except Exception as e:
        print(f"DEBUG: Exception: {e}")
        return

    # Verify
    if new_state['segments'][0].get('translated_text') == "Ceci est le texte traduit.":
        report("Draft Translate Logic", True)
    else:
        report("Draft Translate Logic", False)
        print(f"   State: {new_state['segments']}")

async def main():
    await test_quality_gates()
    await test_draft_translation_node()

if __name__ == "__main__":
    asyncio.run(main())
