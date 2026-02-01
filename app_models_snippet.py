
class TranslationRule(Base):
    """
    TMX-045: Knowledge System Rule.
    Represents a learned translation rule (Nuance).
    """
    __tablename__ = "translation_rules"
    
    rule_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    source_pattern = Column(String, nullable=False, index=True) # Text or Regex
    target_correction = Column(String, nullable=False)
    
    context_tag = Column(String, default="general") # e.g. "pharma", "legal"
    confidence_score = Column(Float, nullable=False) # 0.0 - 1.0 (AI Confidence)
    
    status = Column(String, default="PENDING_APPROVAL") # ACTIVE, PENDING_APPROVAL, REJECTED
    
    origin_event_id = Column(String, nullable=True) # Link to ChangeLog or Audit
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
