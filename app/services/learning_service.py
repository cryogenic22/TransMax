
from typing import Dict, Any, Optional
import logging
import uuid
import json
from datetime import datetime

from app.models.models import TranslationRule
from app.services.db_service import get_db_service
from app.services.llm import get_llm
from app.services.resilience import ResilienceService
from app.services.json_parser import RobustParser

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

LEARNING_SYSTEM_PROMPT = """
You are the TransMax Knowledge System Agent. 
Your goal is to extract a generalized translation rule from a human correction.

INPUT:
- Source Text: The original source.
- Machine Translation: The AI's initial output.
- Human Correction: The text provided by the human expert.

TASK:
1. Compare the Machine Translation and Human Correction.
2. Identify the specific phrase or term that was changed.
3. Formulate a RULE that enforces this correction in future.
   - The rule should be strictly "When source is X, target must be Y".
   - It should be generalized enough to be useful (e.g. "Take" context) but specific enough not to break other things.
4. Assign a CONFIDENCE SCORE (0.0 to 1.0) based on how clear and unambiguous this correction is.
   - 1.0: Pure Terminology fix (e.g. "Advil" -> "Ibuprofen").
   - 0.8: Stylistic preference but clear pattern.
   - 0.5: Context-dependent or unclear why it changed.

OUTPUT JSON:
{
    "rule_extracted": true/false,
    "source_pattern": "string",
    "target_correction": "string",
    "explanation": "why this rule exists",
    "confidence": float
}
"""

class LearningService:
    """
    Manages the learning loop ("Black Book").
    """
    
    async def process_learning_event(self, segment_id: str, human_correction: str, source_text: str, mt_text: str):
        """
        Analyzes a correction and potentially creates a new Knowledge Rule.
        """
        logger.info(f"Learning: Analyzing correction for {segment_id}")
        
        # 1. Calls Core Learning Agent
        try:
            llm = get_llm()
            user_content = f"""
            Source Text: {source_text}
            Machine Translation: {mt_text}
            Human Correction: {human_correction}
            """
            
            messages = [
                SystemMessage(content=LEARNING_SYSTEM_PROMPT),
                HumanMessage(content=user_content)
            ]
            
            response = await ResilienceService.resilient_llm_call(llm.ainvoke, messages)
            data = RobustParser.parse(response.content)
            
            if not data.get("rule_extracted"):
                logger.info("Learning: No clear rule extracted.")
                return
            
            # 2. Decision Logic (Confidence Threshold)
            confidence = data.get("confidence", 0.0)
            status = "PENDING_APPROVAL"
            
            # Auto-approve High Confidence rules (The "Autonomous Update")
            if confidence >= 0.90:
                status = "ACTIVE"
                logger.info(f"Learning: Auto-approving High Confidence Rule ({confidence})")
            else:
                logger.info(f"Learning: Queuing Low Confidence Rule ({confidence}) for Board Review")
                
            # 3. Persist Rule to Black Book
            self._save_rule(
                source_pattern=data.get("source_pattern"),
                target_correction=data.get("target_correction"),
                confidence=confidence,
                status=status,
                origin_id=segment_id
            )
            
        except Exception as e:
            logger.error(f"Learning Agent failed: {e}")
            
    def _save_rule(self, source_pattern, target_correction, confidence, status, origin_id):
        db_service = get_db_service()
        db = db_service.get_session()
        try:
            from app.models.database import DEFAULT_ORG_ID
            rule = TranslationRule(
                rule_id=str(uuid.uuid4()),
                # TMX-3012 will replace with session-context injection.
                organization_id=DEFAULT_ORG_ID,
                source_pattern=source_pattern,
                target_correction=target_correction,
                confidence_score=confidence,
                status=status,
                origin_event_id=origin_id,
                context_tag="learned_from_hitl"
            )
            db.add(rule)
            db.commit()
            logger.info(f"Black Book Updated: Rule {rule.rule_id} status={status}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save rule: {e}")
        finally:
            db.close()
