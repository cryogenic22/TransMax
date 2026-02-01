
import asyncio
import logging
import uuid
# Mock DB Service again for isolated test if DB is unreachable, 
# but ideally we use the real services if configured. 
# We'll use the InMemory mock pattern for speed/isolation 
# but inject the REAL LearningService logic to test the Agent.

from unittest.mock import MagicMock, patch
from app.services.learning_service import LearningService
from app.services.review_service import ReviewService
from app.services.llm import get_llm

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Mock DB for specific calls used by Services
mock_db = MagicMock()
mock_db.get_session.return_value = MagicMock() # Session mock

async def main():
    print("--- LIVE HITL & LEARNING SIMULATION ---")
    
    # 1. Simulate finding a flagged segment
    # (In real life, fetched from DB)
    segment_id = "seg-123"
    source = "Take 2 pills daily."
    mt_bad = "Prendre 2 pilules quotidiennement." # Literal 'Take'
    
    print(f"Segment: {segment_id}")
    print(f"Source: {source}")
    print(f"MT (Bad): {mt_bad}")
    
    # 2. Human Correction (HITL)
    # User rejects 'Prendre' (Take/Grab) in favor of 'Avaler' (Swallow) for meds.
    human_correction = "Avaler 2 pilules quotidiennement."
    print(f"Human Fix: {human_correction}")
    
    # 3. Submit Review (Triggers Learning)
    # We patch get_db_service inside the services to use our mock
    # logic or a temporary in-memory class.
    
    # Mock LLM for Learning Service to avoid token cost if valid
    # OR Use Real LLM to verify the "Agent" intelligence. 
    # User asked for "Real Code". Let's use Real LLM!
    
    print("\n>>> Submitting Correction & Triggering Learning Agent...")
    
    # We manually invoke the LearningService process (usually async event)
    learner = LearningService()
    
    # Patch DB save_rule to just print instead of SQL error
    with patch("app.services.learning_service.get_db_service") as mock_get_db:
         mock_session = MagicMock()
         mock_get_db.return_value.get_session.return_value = mock_session
         
         await learner.process_learning_event(
             segment_id=segment_id,
             human_correction=human_correction,
             source_text=source,
             mt_text=mt_bad
         )
         
         # Verification
         # Check if db.add was called with a Rule
         if mock_session.add.call_count > 0:
             args = mock_session.add.call_args[0][0] # The Rule object
             print(f"\n✅ SUCCESS: Rule Extracted!")
             print(f"   Pattern: {args.source_pattern}")
             print(f"   Correction: {args.target_correction}")
             print(f"   Confidence: {args.confidence_score}")
             print(f"   Status: {args.status}")
             
             if args.status == "ACTIVE":
                 print("   -> Auto-Approved (High Confidence)")
             else:
                 print("   -> Queued for Review (Low Confidence)")
         else:
             print("\n❌ FAILURE: No rule extracted.")

if __name__ == "__main__":
    asyncio.run(main())
