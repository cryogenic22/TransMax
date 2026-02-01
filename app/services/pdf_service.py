from typing import List, Dict, Any
import os

class PDFService:
    """
    Service for ingesting and processing PDF documents.
    Prioritizes 'unstructured' library for better layout preservation.
    """
    
    
    def extract_text(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts text from a PDF file, returning a list of granular content blocks (sentences/paragraphs).
        """
        from app.core.config import settings
        
        if not settings.enable_real_pdf_parsing:
            # Mock Behavior (Safe Mode)
            return [
                {"type": "Title", "text": "Protocol Header (Mock)", "element_id": "mock-1"},
                {"type": "Sentence", "text": "This is a simulated extraction loop.", "element_id": "mock-2"},
                {"type": "Sentence", "text": "Real PDF parsing is currently disabled via feature flag.", "element_id": "mock-3"}
            ]

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
            
        raw_blocks = []
        try:
            # Try using unstructured first
            from unstructured.partition.pdf import partition_pdf
            elements = partition_pdf(filename=file_path, strategy="fast")
            
            for el in elements:
                raw_blocks.append({
                    "type": str(type(el).__name__),
                    "text": str(el),
                    "element_id": el.id if hasattr(el, 'id') else None
                })
            
        except (ImportError, Exception) as e:
            print(f"Extraction fallback (unstructured failed: {e})")
            raw_blocks = self._extract_pypdf(file_path)

        # Refine blocks: Split large text into sentences/semantic units
        refined_blocks = []
        for block in raw_blocks:
            text = block["text"].strip()
            if not text:
                continue
            
            # If it's a title or very short, keep as is
            if block.get("type", "") == "Title" or len(text) < 50:
                refined_blocks.append(block)
                continue
                
            # Otherwise, split into sentences
            sentences = self._split_sentences(text)
            for seg_text in sentences:
                refined_blocks.append({
                    "type": "Sentence",
                    "text": seg_text,
                    "element_id": block.get("element_id") # Share ID or generate new
                })
                
        return refined_blocks

    def _extract_pypdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Fallback extraction using pypdf.
        """
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            blocks = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    for para in text.split('\n\n'):
                        if para.strip():
                            blocks.append({
                                "type": "UnstructuredText",
                                "text": para.strip(),
                                "page": i + 1
                            })
            return blocks
        except Exception as e:
            raise RuntimeError(f"Failed to extract PDF with fallback: {e}")

    def _split_sentences(self, text: str) -> List[str]:
        """
        Splits text into sentences using simple heuristics (Regex).
        Handles common abbreviations (e.g., Dr., mg., etc.) naively.
        """
        import re
        
        # 1. Replace newlines with spaces to handle wrap-around
        text = text.replace("\n", " ")
        
        # 2. Split by punctuation (.!?) followed by space or end of string
        # Lookbehind could be used to avoid splitting on 'No.' or 'mg.'
        # For now, simple split is better than huge blocks
        
        # Split on .!? followed by a space and an uppercase letter (heuristic)
        # re.split returns the delimiters too if captured in (), need to flatten
        
        pattern = r'(?<=[.!?])\s+(?=[A-Z0-9])'
        segments = re.split(pattern, text)
        
        return [s.strip() for s in segments if s.strip()]

