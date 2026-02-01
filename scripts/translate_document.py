import asyncio
import uuid
import os
import json
from app.services.pdf_service import PDFService
from app.agents.graph import workflow
from app.api.endpoints import ContentBlock  # Re-use the model logic if needed, or just dicts

async def main():
    # 1. Setup Paths
    pdf_path = r"c:\Users\kapil\Documents\transmax\research\02_SmPC_EU_EN_Cardiomel_nefrosartan_v0.2.pdf"
    output_path = r"c:\Users\kapil\Documents\transmax\demo_translation_smpc.txt"
    
    print(f"--- STEP 1: INGESTION ---")
    print(f"Reading: {pdf_path}")
    
    pdf_service = PDFService()
    # Limit to first 3 pages or 15 blocks to save tokens/time for the demo
    # The user asked for 'one of the documents', but a full SmPC is long. 
    # Let's do a representative chunk (Header + Section 4.1-4.3)
    
    try:
        raw_blocks = pdf_service.extract_text(pdf_path)
    except Exception as e:
        print(f"Ingestion Failed: {e}")
        return

    # Optimization: Take first 10 meaningful blocks for the demo
    # (Title, Composition, Indications)
    demo_blocks = raw_blocks[:10] 
    print(f"Extracted {len(raw_blocks)} blocks. Using first {len(demo_blocks)} for demo.")
    
    # 2. Transform to Agent Input
    print(f"\n--- STEP 2: TRANSFORMATION ---")
    content_blocks = []
    for idx, b in enumerate(demo_blocks):
        content_blocks.append({
            "block_id": f"b{idx}",
            "content": b.get("text", ""),
            "type": b.get("type", "text")
        })
        
    input_state = {
        "request_id": str(uuid.uuid4()),
        "source_language": "en",
        "target_language": "fr", # Translating to French
        "domain": "clinical",
        "audience": "physician", # SmPC is for pros
        "content_blocks": content_blocks,
        
        # Init empty placeholders
        "segments": [],
        "constraint_pack": {},
        "draft_segments": [],
        "quality_report": {},
        "iteration_count": 0,
        "final_decision": "PENDING",
        "audit_trail_id": str(uuid.uuid4()),
        "error": None
    }
    
    # 3. Execution (The Brain)
    print(f"\n--- STEP 3: AGENT EXECUTION ---")
    print("Invoking TransMax Agent (this calls OpenAI)...")
    
    app = workflow.compile()
    final_state = await app.ainvoke(input_state)
    
    # 4. Output
    print(f"\n--- STEP 4: OUTPUT ---")
    
    if final_state.get('error'):
        print(f"❌ Translation Failed: {final_state['error']}")
    else:
        print(f"✅ Success! Decision: {final_state.get('final_decision')}")
        
        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"Source Document: {os.path.basename(pdf_path)}\n")
            f.write(f"Target Language: French (fr)\n")
            f.write("-" * 50 + "\n\n")
            
            for seg in final_state.get('draft_segments', []):
                source = next((s['source_text'] for s in final_state['segments'] if s['segment_id'] == seg['segment_id']), "?")
                f.write(f"[SOURCE] {source}\n")
                f.write(f"[TARGET] {seg['target_text']}\n")
                f.write("\n")
                
        print(f"Translated output saved to: {output_path}")
        print("\n--- PREVIEW ---")
        # Print first translation
        if final_state.get('draft_segments'):
             first = final_state['draft_segments'][0]
             print(f"Target: {first['target_text']}")

if __name__ == "__main__":
    asyncio.run(main())
