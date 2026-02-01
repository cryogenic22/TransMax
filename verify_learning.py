
import asyncio
import os
import sys
import uuid
import json
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from app.services.review_service import ReviewService
from app.models.database import Segment, SegmentStatus

# Mock classes
class MockResponse:
    def __init__(self, content):
        self.content = content

class MockRule:
    def __init__(self, source_pattern, target_correction, confidence_score, status):
        self.source_pattern = source_pattern
        self.target_correction = target_correction
        self.confidence_score = confidence_score
        self.status = status

async def test_learning_loop():
    print("Starting Mocked Learning Loop Verification...")
    
    # 1. Setup Data
    seg_id = str(uuid.uuid4())
    original_text = "Take two Advil."
    original_mt = "Nimm zwei Advil."
    corrected_text = "Nimm zwei Ibuprofen."
    
    # 2. Mock Database Service
    with patch("app.services.review_service.get_db_service") as mock_get_db, \
         patch("app.services.learning_service.get_db_service") as mock_learn_db:
         
        # Mock Session
        mock_session = MagicMock()
        mock_get_db.return_value.get_session.return_value = mock_session
        mock_learn_db.return_value.get_session.return_value = mock_session
        
        # Mock Segment Query Result
        mock_segment = MagicMock()
        mock_segment.segment_id = seg_id
        mock_segment.source_text = original_text
        mock_segment.translated_text = original_mt
        
        # Configure query chain: session.query().filter_by().first()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_segment
        
        # 3. Mock LLM Response
        mock_llm_response = json.dumps({
            "rule_extracted": True,
            "source_pattern": "Advil",
            "target_correction": "Ibuprofen",
            "explanation": "Use generic name.",
            "confidence": 0.95
        })
        
        with patch("app.services.resilience.ResilienceService.resilient_llm_call", new_callable=MagicMock) as mock_llm_call:
            # properly mock awaitable
            f = asyncio.Future()
            f.set_result(MockResponse(mock_llm_response))
            mock_llm_call.return_value = f
            
            # 4. Run Correction
            print("Submitting Correction...")
            review_service = ReviewService()
            success = await review_service.submit_correction(
                segment_id=seg_id,
                corrected_text=corrected_text,
                user_id="verifier_bot"
            )
            
            if success:
                print("✅ Correction logic succeeded.")
            else:
                print("❌ Correction logic failed.")
                return

            # 5. Verify DB Interactions for Rule Creation
            # We check if session.add() was called with a TranslationRule object
            # The LearningService calls _save_rule which does db.add(rule)
            
            print("Verifying Rule Persistence...")
            
            # Find the call to session.add
            added_objects = [call.args[0] for call in mock_session.add.call_args_list]
            
            rule_found = False
            for obj in added_objects:
                # We can't isinstance easily because of imports, check attributes
                if hasattr(obj, 'source_pattern') and hasattr(obj, 'target_correction'):
                    print(f"✅ Rule Added: {obj.source_pattern} -> {obj.target_correction}")
                    print(f"   Status: {obj.status}")
                    
                    assert obj.source_pattern == "Advil"
                    assert obj.target_correction == "Ibuprofen"
                    assert obj.status == "ACTIVE" # High confidence
                    rule_found = True
                    break
            
            if not rule_found:
                 print("❌ Rule NOT added to session.")
            else:
                 print("✅ Learning Loop Verified Successfully.")

if __name__ == "__main__":
    asyncio.run(test_learning_loop())
