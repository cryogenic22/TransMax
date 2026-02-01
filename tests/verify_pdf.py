import os
import sys
from app.services.pdf_service import PDFService

def test_ingestion():
    pdf_path = os.path.abspath("test_sample.pdf")
    
    if not os.path.exists(pdf_path):
        print("Error: test_sample.pdf not found. Run generate_pdf.py first.")
        sys.exit(1)
        
    print(f"Testing ingestion for: {pdf_path}")
    
    service = PDFService()
    try:
        blocks = service.extract_text(pdf_path)
        print(f"Extracted {len(blocks)} blocks.")
        
        has_title = False
        has_text = False
        
        for b in blocks:
            print(f"[{b['type']}] {b['text'][:50]}...")
            if "TransMax Test Document" in b['text']:
                has_title = True
            if "sample paragraph" in b['text']:
                has_text = True
                
        if has_title and has_text:
            print("SUCCESS: Title and body text detected.")
        else:
            print("FAILED: Expected content missing.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_ingestion()
