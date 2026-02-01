from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from datetime import datetime

from app.services.db_service import get_db_service
from app.models.models import TranslationRule, Glossary

router = APIRouter()

# --- Schemas ---

class FeedbackRequest(BaseModel):
    source_text: str
    target_text: str
    corrected_text: Optional[str] = None
    rating: str # "positive", "negative"
    comment: Optional[str] = None
    target_language: str


class TranslationRuleSchema(BaseModel):
    rule_id: str
    source_pattern: str
    target_correction: str
    context_tag: str
    confidence_score: float
    status: str
    origin_event_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class RuleUpdateSchema(BaseModel):
    status: str # ACTIVE, REJECTED

class GlossarySchema(BaseModel):
    glossary_id: str
    version: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Endpoints ---

@router.get("/rules", response_model=List[TranslationRuleSchema])
async def list_rules(
    status: Optional[str] = Query(None, description="Filter by status (e.g. PENDING_APPROVAL)"),
    limit: int = 50
):
    """
    List Translation Rules from the Black Book.
    """
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        query = session.query(TranslationRule)
        if status:
            query = query.filter(TranslationRule.status == status)
        
        rules = query.order_by(TranslationRule.confidence_score.desc()).limit(limit).all()
        return rules
    finally:
        session.close()

@router.patch("/rules/{rule_id}", response_model=TranslationRuleSchema)
async def update_rule_status(rule_id: str, update: RuleUpdateSchema):
    """
    Curator Workflow: Approve or Reject a learned rule.
    """
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        rule = session.query(TranslationRule).filter(TranslationRule.rule_id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        rule.status = update.status
        session.commit()
        session.refresh(rule)
        return rule
    finally:
        session.close()

@router.get("/glossaries", response_model=List[GlossarySchema])
async def list_glossaries():
    """
    List active Agency Glossaries.
    """
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        glossaries = session.query(Glossary).all()
        return glossaries
    finally:
        session.close()

@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Capture user feedback as a proposed rule (Black Book inbox).
    """
    db_service = get_db_service()
    session = db_service.get_session()
    try:
        if feedback.rating == "negative" and feedback.corrected_text:
            # Create a proposed rule
            new_rule = TranslationRule(
                source_pattern=feedback.source_text,
                target_correction=feedback.corrected_text,
                context_tag="feedback_loop",
                confidence_score=1.0, # Human input
                status="PENDING_APPROVAL",
                origin_event_id=f"feedback_{datetime.utcnow().timestamp()}"
            )
            session.add(new_rule)
            session.commit()
            return {"status": "rule_created", "rule_id": new_rule.rule_id}
        
        return {"status": "feedback_recorded"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
