from typing import List, Dict, Any
import pypdf
import os

class PDFIngestionService:
    """
    Service for ingesting PDF documents and extracting text content.
    """
    
    def extract_content(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts text from a PDF file.
        Returns a list of content blocks (pages/paragraphs).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
            
        blocks = []
        
        try:
            reader = pypdf.PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    blocks.append({
                        "block_id": f"p{i+1}",
                        "type": "pdf_page_text",
                        "content": text.strip(),
                        "metadata": {
                            "page_number": i + 1,
                            "source_file": os.path.basename(file_path)
                        }
                    })
        except Exception as e:
            print(f"Error extracting PDF content: {e}")
            raise e
            
        return blocks

    def extract_from_bytes(self, file_bytes: bytes, filename: str = "unknown.pdf") -> List[Dict[str, Any]]:
        """
        Extracts text from PDF bytes/stream.
        """
        import io
        stream = io.BytesIO(file_bytes)
        blocks = []
        
        try:
            reader = pypdf.PdfReader(stream)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                     blocks.append({
                        "block_id": f"p{i+1}",
                        "type": "pdf_page_text",
                        "content": text.strip(),
                        "metadata": {
                            "page_number": i + 1,
                            "source_file": filename
                        }
                    })
        except Exception as e:
            raise e
            
        return blocks
