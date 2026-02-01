import pytest
from app.services.pii_service import PIIService

def test_default_patterns():
    service = PIIService()
    text = "Contact me at test@example.com or 555-123-4567."
    sanitized, meta = service.redact(text)
    
    assert "<EMAIL_REDACTED>" in sanitized
    assert "<PHONE_REDACTED>" in sanitized
    assert "test@example.com" not in sanitized
    assert len(meta) == 2

def test_custom_pattern():
    service = PIIService()
    service.add_pattern("SECRET_CODE", r"XYZ-\d{3}")
    
    text = "The secret is XYZ-123."
    sanitized, meta = service.redact(text)
    
    assert "<SECRET_CODE_REDACTED>" in sanitized
    assert "XYZ-123" not in sanitized

def test_remove_mode():
    service = PIIService()
    text = "Remove email: user@domain.com"
    sanitized, meta = service.redact(text, mode="remove")
    
    assert sanitized == "Remove email: "
    assert meta[0]["original"] == "user@domain.com"
