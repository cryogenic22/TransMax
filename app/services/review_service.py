
from typing import List, Dict, Any
import logging

# Import DB Service (interface)
from app.services.db_service import get_db_service

logger = logging.getLogger(__name__)

class ReviewService:
    """
    Manages the Human-in-the-Loop (HITL) workflow.
    Allows fetching blocked/flagged segments and submitting corrections.
    """
    
    def get_pending_reviews(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all segments for a job that require review or are blocked.

        TMX-AUDIT-DB-DOCID-LOOKUP: the reviewer/job surface uses ``Document.id``
        as its identifier (see ``db_service.get_doc_id_from_job``). Resolve the
        identifier to a doc id, then delegate to ``get_flagged_segments`` —
        the single source of truth for "which segments need a human". A3: a
        missing document is surfaced as a WARNING + an empty list, never a
        silent ``None``.
        """
        db = get_db_service()
        doc_id = db.get_doc_id_from_job(job_id)
        if doc_id is None:
            logger.warning(
                "get_pending_reviews: no document resolves to job/identifier %s "
                "(returning empty review queue)", job_id
            )
            return []
        return self.get_flagged_segments(doc_id)
        
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

