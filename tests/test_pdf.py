import pytest
from unittest.mock import MagicMock, patch
import io
from app.services.pdf_ingestion import PDFIngestionService

@pytest.fixture
def pdf_service():
    return PDFIngestionService()

def test_extract_content_file_not_found(pdf_service):
    with pytest.raises(FileNotFoundError):
        pdf_service.extract_content("non_existent.pdf")

def test_extract_from_bytes_success(pdf_service):
    # Mock pypdf.PdfReader
    with patch("pypdf.PdfReader") as MockReader:
        # Check extraction logic
        mock_instance = MockReader.return_value
        
        # Mock pages
        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1 Content"
        
        page2 = MagicMock()
        page2.extract_text.return_value = "   " # Empty/whitespace
        
        page3 = MagicMock()
        page3.extract_text.return_value = "Page 3 Content"
        
        mock_instance.pages = [page1, page2, page3]
        
        # Execute
        dummy_bytes = b"%PDF-1.4..."
        blocks = pdf_service.extract_from_bytes(dummy_bytes, "test.pdf")
        
        # Verify
        assert len(blocks) == 2 # Page 2 skipped because empty
        
        assert blocks[0]["content"] == "Page 1 Content"
        assert blocks[0]["metadata"]["page_number"] == 1
        
        assert blocks[1]["content"] == "Page 3 Content"
        assert blocks[1]["metadata"]["page_number"] == 3

def test_extract_content_file_success(pdf_service):
    with patch("pypdf.PdfReader") as MockReader:
        with patch("os.path.exists", return_value=True):
             mock_instance = MockReader.return_value
             page1 = MagicMock()
             page1.extract_text.return_value = "File Content"
             mock_instance.pages = [page1]
             
             blocks = pdf_service.extract_content("real.pdf")
             
             assert len(blocks) == 1
             assert blocks[0]["content"] == "File Content"
             assert blocks[0]["metadata"]["source_file"] == "real.pdf"
