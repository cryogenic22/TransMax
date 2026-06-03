
from typing import List, Dict, Any, Optional
import logging
import uuid
from datetime import datetime

# Import DB Service (interface)
from app.services.db_service import get_db_service
from app.models.database import SegmentStatus

logger = logging.getLogger(__name__)

class ReviewService:
    """
    Manages the Human-in-the-Loop (HITL) workflow.
    Allows fetching blocked/flagged segments and submitting corrections.
    """
    
    def get_pending_reviews(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all segments for a job that require review or are blocked.
        """
        db = get_db_service()
        # In a real impl, we'd query by Job ID -> Doc IDs -> Segments.
        # For our flat schema, we might iterate Docs in the Job.
        # Assuming we can filter segments by document_id associated with Job.
        
        # For now, simplistic fetch: Get blocked segments for doc.
        # We need to look up doc_id from job_id.
        # TODO(TMX-AUDIT-DB-DOCID-LOOKUP): Add get_doc_id_from_job(job_id) to DB service.
        # Fallback: Assume the frontend passes doc_id for now or we query Job table.
        
        # We return a mocked structure if the DB query is complex, 
        # but the goal is LIVE. So let's try to query via DB service if possible.
        # Extending db_service might be needed.
        pass
        
    def get_flagged_segments(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves segments with BLOCKED or REVIEW_REQUIRED status or warnings.
        """
        db = get_db_service()
        all_segments = db.get_segments_for_doc(doc_id)
        
        flagged = []
        for seg in all_segments:
            status = seg.get('status')
            # Check status enum string
            if status in ["BLOCKED", "REVIEW_REQUIRED"] or \
               (isinstance(status, str) and status in ["BLOCKED", "REVIEW_REQUIRED"]):
                flagged.append(seg)
                continue
                
            # Or checks defects?
            # Ideally we check the QualityGate results attached to the segment?
            # DB Service get_segments_for_doc might not return gate_results unless we join.
            # We'll stick to Status for Sprint 1 of HITL.
            
        return flagged

    async def submit_correction(self, segment_id: str, corrected_text: str, user_id: str = "human_reviewer") -> bool:
        """
        Applies a human correction to a segment.
        1. Updates Segment text.
        2. Sets Status to TRANSLATED (Approved).
        3. Logs Change.
        4. Triggers Learning (Async).
        """
        db = get_db_service()
        
        logger.info(f"Review: Correction submitted for {segment_id} by {user_id}")
        
        # 1. Fetch original for logs and learning
        original_segment = None
        # We need a method to get single segment. Extending db logic here or using direct query if exposed.
        # Assuming db.get_segment(id) exists or we iterate.
        # For now, let's assume we can fetch it. If not, we query via session.
        session = db.get_session()
        try:
            from app.models.database import Segment
            segment = session.query(Segment).filter_by(segment_id=segment_id).first()
            if not segment:
                logger.error(f"Segment {segment_id} not found.")
                return False
                
            original_source = segment.source_text
            original_mt = segment.translated_text or "" # Might be empty if blocked before translation?
            
            # Update DB (Using Service or Session)
            # Using service update batch for consistency
            updates = [{
                "segment_id": segment_id,
                "translated_text": corrected_text,
                "status": "TRANSLATED", # Approved
                "translation_source": "human_correction"
            }]
            db.update_segments_batch(updates)
            
            # Log Change (Audit)
            db.log_segment_change(
                segment_id=segment_id,
                original=original_mt, 
                new=corrected_text,
                reason="HITL Correction",
                user_id=user_id
            )
            
            # TRIGGER LEARNING (The "Black Book" Bridge)
            try:
                from app.services.learning_service import LearningService
                
                # We interpret "different text" as a signal to learn.
                if original_mt and original_mt != corrected_text:
                    learning_service = LearningService()
                    await learning_service.process_learning_event(
                        segment_id=segment_id,
                        human_correction=corrected_text,
                        source_text=original_source,
                        mt_text=original_mt
                    )
                else:
                    logger.info("Learning skipped: No change or missing original MT.")

            except Exception as e:
                logger.warning(f"Learning Loop failed: {e}")

            return True
            
        except Exception as e:
            logger.error(f"Correction failed: {e}")
            return False
        finally:
            session.close()

