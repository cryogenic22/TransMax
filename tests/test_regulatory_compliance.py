
import pytest
import json
import os
from typing import List, Dict, Any
from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory, DefectSeverity

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "data", "regulatory_corpus_v1.json")

def load_regulatory_corpus() -> List[Dict[str, Any]]:
    """Loads the immutable regulatory corpus."""
    if not os.path.exists(CORPUS_PATH):
        raise FileNotFoundError(f"Regulatory Corpus not found at {CORPUS_PATH}")
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def quality_gate_service():
    return QualityGateService()

@pytest.mark.parametrize("case", load_regulatory_corpus())
def test_regulatory_case(quality_gate_service, case):
    """
    Executes a test case from the Regulatory Control Corpus.
    Enforces that the system behaves exactly as the corpus mandates.
    """
    print(f"\nRunning Case: {case['id']} - {case['description']}")
    
    # 1. Execute Logic
    defects = quality_gate_service.check_segment(
        source_text=case['source_text'],
        target_text=case['target_text'],
        constraints={}, # Empty for now, unless corpus adds constraint setup
        target_lang=case['target_language']
    )
    
    # 2. Assert Pass/Fail Outcome
    expected_result = case['expected_result']
    actual_result = "PASS" if not defects else "FAIL"
    
    # NOTE: "FAIL" in corpus implies ANY defect found. 
    # In reality, minor defects might be acceptable, but for this strict corpus, empty defects = PASS.
    assert actual_result == expected_result, \
        f"Outcome Mismatch for {case['id']}. Expected {expected_result}, Got {actual_result}. Defects: {defects}"

    # 3. Assert Defect Details (if expected)
    expected_defects = case.get('expected_defects', [])
    
    if expected_defects:
        assert len(defects) >= len(expected_defects), \
            f"Fewer defects found than expected for {case['id']}. Found: {defects}"
            
        for expected in expected_defects:
            found = False
            for d in defects:
                # Check Category
                if d['category'] != expected['category']:
                    continue
                # Check Severity
                if d['severity'] != expected['severity']:
                    continue
                # Check Message Content
                if expected.get('message_contains') and expected['message_contains'] not in d['message']:
                    continue
                found = True
                break
            
            assert found, \
                f"Expected defect not found in {case['id']}: {expected}. Actual: {defects}"

if __name__ == "__main__":
    pytest.main([__file__])
