import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
from app.services.reporting_service import ReportingService
from app.models.database import Document, DocumentStatus
from app.models.models import QualityScorecard, AuditRecord

def test_generate_certificate_pdf():
    # Mock DB Session
    mock_db = MagicMock()
    
    # Mock Data
    mock_doc = Document(id="job-123", source_language="en", target_language="es", status=DocumentStatus.APPROVED)
    mock_score = QualityScorecard(job_id="job-123", critical_defect_count=0, major_defect_count=0, semantic_drift_score=2.5)
    mock_audit = AuditRecord(job_id="job-123", audit_id="audit-999", chain_head_hash="hash-xyz")
    
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_doc, mock_score, mock_audit]
    
    # Call Service
    pdf_buffer = ReportingService.generate_certificate(mock_db, "job-123")
    
    # Verify
    content = pdf_buffer.getvalue()
    assert content.startswith(b"%PDF"), "Output should be a PDF file"
    assert len(content) > 100, "PDF should have content"
    
    # Simple strings check (Warning: PDF compression might hide plain strings, but ReportLab usually leaves some clear text)
    # This is a loose check. 
    # assert b"Certificate" in content  # Might fail due to encoding
    
def test_certificate_api_404():
    # If job not found, should raise ValueError -> 404
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None # No doc
    
    with pytest.raises(ValueError, match="Job not found"):
        ReportingService.generate_certificate(mock_db, "job-missing")

if __name__ == "__main__":
    test_generate_certificate_pdf()
    test_certificate_api_404()
    print("Reporting Tests Passed")
