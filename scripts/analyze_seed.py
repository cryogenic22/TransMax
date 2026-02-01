from app.services.pdf_service import PDFService
import json

def analyze_pdf(path):
    print(f"\nAnalyzing: {path}")
    service = PDFService()
    try:
        blocks = service.extract_text(path)
        print(f"Total Blocks: {len(blocks)}")
        
        # Analyze block types
        types = {}
        for b in blocks:
            t = b.get('type', 'Unknown')
            types[t] = types.get(t, 0) + 1
            
        print("Block Types:", json.dumps(types, indent=2))
        
        # Show first few blocks to gauge content quality
        print("\n--- First 3 Blocks ---")
        for b in blocks[:3]:
            print(f"[{b.get('type')}] {b.get('text')[:100]}...")
            
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

if __name__ == "__main__":
    files = [
        r"c:\Users\kapil\Documents\transmax\research\02_SmPC_EU_EN_Cardiomel_nefrosartan_v0.2.pdf",
        r"c:\Users\kapil\Documents\transmax\research\03_PIL_Local_EN_Cardiomel_nefrosartan_v0.2.pdf"
    ]
    
    for f in files:
        analyze_pdf(f)
