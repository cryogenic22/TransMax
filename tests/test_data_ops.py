import os
import sys
import uuid
import pytest
from app.services.db_service import DatabaseService
from app.core.constants import SubstitutionType

# Ensure we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def db_service():
    service = DatabaseService()
    # Ensure tables exist
    return service

def test_glossary_ops(db_service):
    """
    TMX-042: Verify Glossary Creation and Term Insertion.
    """
    glossary_id = f"test_gloss_ops_{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    
    # 1. Create Glossary
    db_service.create_glossary(glossary_id, version, {"author": "unittest"})
    
    # 2. Add Terms
    db_service.add_glossary_term(glossary_id, version, {
        "term_id": "term1",
        "source_text": "Validation",
        "target_text": "Validation_FR",
        "is_forbidden": False
    })
    
    db_service.add_glossary_term(glossary_id, version, {
        "term_id": "term2",
        "source_text": "ForbiddenX",
        "target_text": "InterditX",
        "is_forbidden": True
    })
    
    # 3. Verify via get_constraints
    # Need to pass glossary_id to get_constraints
    constraints = db_service.get_constraints("en", "fr", glossary_id=glossary_id)
    
    # Check Glossary
    gloss_terms = constraints.get("glossary", [])
    found_term = next((t for t in gloss_terms if t["source"] == "Validation"), None)
    assert found_term is not None
    assert found_term["target"] == "Validation_FR"
    
    # Check Forbidden
    forbidden = constraints.get("forbidden_terms", [])
    found_forbidden = next((t for t in forbidden if "InterditX" in t["term"] or "ForbiddenX" in t["term"]), None)
    # Logic in get_constraints: if forbidden, uses target_text or source_text.
    # Here target="InterditX".
    assert found_forbidden is not None
    assert found_forbidden["term"] == "InterditX"

def test_tm_ops(db_service):
    """
    TMX-041: Verify TM Insertion and Retrieval.
    """
    source_text = f"Unique Source {uuid.uuid4().hex}"
    target_text = "Target Translation"
    
    # 1. Add Segment
    segment_hash = db_service.add_tm_segment(source_text, target_text, "en", "fr")
    assert segment_hash is not None
    
    # 2. Add Duplicate (Idempotency check - upsert)
    hash2 = db_service.add_tm_segment(source_text, target_text, "en", "fr")
    # Should probably be different segment_hash if logic generates new UUID every time?
    # Logic: segment_hash = str(uuid.uuid4()).
    # So it adds a NEW segment entry (versioning).
    assert hash2 != segment_hash
    
    # 3. Verify Exact Match Retrieval
    match = db_service.find_best_match(source_text, "en", "fr")
    assert match is not None
    assert match['type'] == SubstitutionType.TM_EXACT.value
    assert match['target'] == target_text
    assert match['score'] == 1.0

if __name__ == "__main__":
    svc = DatabaseService()
    try:
        test_glossary_ops(svc)
        print("PASS test_glossary_ops")
        test_tm_ops(svc)
        print("PASS test_tm_ops")
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
