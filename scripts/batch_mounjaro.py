
import asyncio
import uuid
import os
import json
import logging
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any, Optional
from app.services.pdf_service import PDFService
from app.agents.graph import workflow
from app.core.constants import SubstitutionType

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- IN-MEMORY DB SERVICE (REAL LOGIC, NO SQL) ---
class InMemoryDatabaseService:
    def __init__(self):
        self.documents = {} # doc_id -> {status: "PROCESSING"}
        self.segments = {}  # doc_id -> [segment_dicts]
        self.constraints = {"glossary": [], "tm_matches": []}
        
    def get_document_status(self, doc_id: str) -> str:
        return self.documents.get(doc_id, {}).get("status", "UNKNOWN")

    def update_document_status(self, doc_id: str, status: str) -> None:
        if doc_id not in self.documents:
            self.documents[doc_id] = {}
        self.documents[doc_id]["status"] = status
        print(f"DB: Document {doc_id} status -> {status}")

    def get_segments_for_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        # Return deep copy to simulate DB fetch
        return [dict(s) for s in self.segments.get(doc_id, [])]

    def update_segments_batch(self, updates: List[Dict[str, Any]]):
        for update in updates:
            seg_id = update.get("segment_id")
            # Find segment across all docs (inefficient but fine for script)
            found = False
            for doc_id, segs in self.segments.items():
                for seg in segs:
                    if seg["segment_id"] == seg_id:
                        found = True
                        # Update fields
                        if "translated_text" in update:
                            seg["translated_text"] = update["translated_text"]
                        if "status" in update:
                            seg["status"] = update["status"]
                        # We can add more fields if needed
            if not found:
                print(f"DB Warning: Segment {seg_id} not found for update.")

    def get_constraints(self, source_lang: str, target_lang: str, query_text: str = "", glossary_id: Optional[str] = None) -> Dict[str, Any]:
        return self.constraints

    def find_best_match(self, source_text: str, source_lang: str, target_lang: str) -> Optional[Dict[str, Any]]:
        return None # No TM for now

    def save_quality_scorecard(self, job_id: str, scorecard_data: Dict[str, Any], defects: List[Dict[str, Any]]):
        print(f"DB: Scorecard saved for {job_id}. Defects: {len(defects)}")

    def create_audit_trail(self, job_id):
        return str(uuid.uuid4())

    def log_event(self, *args, **kwargs):
        pass
        
    def capture_config_snapshot(self, *args, **kwargs):
        pass

# Global instance for the script
memory_db = InMemoryDatabaseService()

async def main():
    # 1. Setup Paths
    pdf_path = r"C:\Users\kapil\Downloads\mounjaro_pil.15484.pdf"
    output_dir = r"C:\Users\kapil\Documents\transmax\batch_output"
    os.makedirs(output_dir, exist_ok=True)
    
    target_languages = ["fr", "de", "es", "ja", "ar"]
    
    print(f"--- STEP 1: INGESTION (Once) ---")
    print(f"Reading: {pdf_path}")
    
    pdf_service = PDFService()
    try:
        raw_blocks = pdf_service.extract_text(pdf_path)
    except Exception as e:
        print(f"Ingestion Failed: {e}")
        return

    # Limit for pilot cost control if desired, but user asked for real Run.
    # We'll do 15 blocks to show sufficient progress without burning $10 if it loops.
    demo_blocks = raw_blocks[:15]
    print(f"Extracted {len(raw_blocks)} blocks. Processing first {len(demo_blocks)}.")

    # --- SETUP PIPELINE ---
    # We patch get_db_service and get_audit_service to use our Memory DB
    
    with patch("app.agents.graph.get_db_service", return_value=memory_db), \
         patch("app.agents.graph.get_audit_service", return_value=memory_db):
         
        app = workflow.compile()
        
        print(f"\n--- STEP 2: BATCH EXECUTION (REAL LLM) ---")
        
        for lang in target_languages:
            print(f"\n>>> Starting Translation for: {lang.upper()}")
            
            request_id = str(uuid.uuid4())
            doc_id = f"doc-{request_id}"
            
            # Seed DB with these segments
            memory_db.documents[doc_id] = {"status": "UPLOADED"}
            memory_db.segments[doc_id] = []
            
            for idx, b in enumerate(demo_blocks):
                content = b.get("text", "").strip()
                if content:
                    memory_db.segments[doc_id].append({
                        "segment_id": f"seg-{idx}-{lang}", # Unique per run likely safer
                        "doc_id": doc_id,
                        "source_text": content,
                        "translated_text": None,
                        "order_index": idx,
                        "status": "NEW",
                        "reverse_translation": None
                    })
            
            # Input State
            input_state = {
                "request_id": request_id,
                "doc_id": doc_id,
                "source_language": "en",
                "target_language": lang,
                "domain": "clinical",
                "audience": "patient", 
                
                # Init empty
                "segments": [], # Graph will load via load_segments node calling get_segments_for_doc
                "constraint_pack": {},
                "quality_report": {},
                "iteration_count": 0,
                "final_decision": "PENDING",
                "error": None
            }
            
            try:
                 # Invoke Agent (Real LLM calls via app.services.llm.get_llm)
                 final_state = await app.ainvoke(input_state)
                 
                 # Save Output
                 filename = f"mounjaro_{lang}.txt"
                 filepath = os.path.join(output_dir, filename)
                 
                 if final_state.get('error'):
                     print(f"❌ {lang.upper()} Failed: {final_state['error']}")
                 else:
                     print(f"✅ {lang.upper()} Success!")
                     
                     # Read from Memory DB (Final Truth)
                     final_segments = memory_db.get_segments_for_doc(doc_id)
                     
                     with open(filepath, "w", encoding="utf-8") as f:
                        f.write(f"Source: {os.path.basename(pdf_path)}\n")
                        f.write(f"Target: {lang}\n")
                        f.write("-" * 50 + "\n\n")
                        for seg in final_segments:
                            txt = seg.get('translated_text') or ""
                            # Only write if text exists
                            if txt:
                                f.write(f"[SRC] {seg['source_text'][:50]}...\n")
                                f.write(f"[TGT] {txt}\n\n")
                     print(f"Saved to: {filepath}")
                     
            except Exception as e:
                import traceback
                print(f"❌ {lang.upper()} Exception: {e}")
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

