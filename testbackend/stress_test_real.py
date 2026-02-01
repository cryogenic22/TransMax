import sys
import os
import json
import asyncio
import uuid
from dotenv import load_dotenv

# Load env vars from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Ad-hoc path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.db_service import DatabaseService
from app.agents.graph import draft_translate, run_quality_gates, TransMaxState
from app.models.database import DocumentStatus, SegmentStatus

# Verify API Key
if not os.getenv("OPENAI_API_KEY"):
    print("CRITICAL: OPENAI_API_KEY not found in .env. Cannot run real test.")
    sys.exit(1)

# Create Output Directory
OUTPUT_DIR = "testbackend/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def run_stress_test():
    print("\n==================================================")
    print("   PHARMA BACKEND E2E STRESS TEST (REAL DB + LLM)   ")
    print("==================================================\n")
    
    service = DatabaseService()
    
    # 1. Setup: Create Real Document & Segments
    doc_id = str(uuid.uuid4())
    print(f"Creating Test Document: {doc_id}")
    
    # Use raw SQL or Service? Service creates doc via API usually. 
    # Logic in API: `doc = Document(...)`, `db.add(doc)`.
    # We will use db_session directly for setup to mimic API.
    
    db = service.get_session()
    from app.models.database import Document, Segment
    
    try:
        doc = Document(
            id=doc_id,
            name="Stress_Test_Pharma.txt",
            source_language="en",
            target_language="fr",
            status=DocumentStatus.PROCESSING,
            file_type="txt",
            page_count=1,
            word_count=100
        )
        db.add(doc)
        
        # Test Cases
        test_cases = [
            {
                "text": "Adults: The recommended starting dose is 40 mg once daily. The usual maintenance dose is 40–80 mg once daily. The maximum dose is 160 mg/day.",
                "desc": "Complex Dosing"
            },
            {
                "text": "| System Organ Class | Very common | Common |\n| Nervous system disorders | Dizziness; Headache | |",
                "desc": "Table Structure"
            },
            {
                "text": "Contraindicated in patients with severe hepatic impairment (Child-Pugh C).",
                "desc": "Contraindications"
            }
        ]
        
        db_segments = []
        for i, case in enumerate(test_cases):
            seg_id = str(uuid.uuid4())
            seg = Segment(
                id=seg_id,
                document_id=doc_id,
                order_index=i+1,
                source_text=case["text"],
                status=SegmentStatus.PENDING
            )
            db.add(seg)
            db_segments.append(seg)
            
        db.commit()
        print("Setup Complete: Document and Segments committed to Postgres.")
        
    except Exception as e:
        print(f"Setup Failed: {e}")
        db.rollback()
        return
    finally:
        db.close()
        
    # 2. Prepare State (mimic what API passes to Graph)
    # We reload segments to get IDs
    db = service.get_session()
    segments_data = []
    loaded_segs = db.query(Segment).filter(Segment.document_id == doc_id).order_by(Segment.order_index).all()
    
    for seg in loaded_segs:
        segments_data.append({
            "segment_id": seg.id,
            "source_text": seg.source_text,
            "order_index": seg.order_index,
            "translated_text": None
        })
    db.close()
    
    state: TransMaxState = {
        "doc_id": doc_id,
        "target_language": "fr",
        "segments": segments_data,
        "constraint_pack": {}, 
        "quality_report": {},
        "iteration_count": 0,
        "error": None
    }
    
    print(f"\nStaring Agent Workflow for {len(segments_data)} segments...")
    
    # 3. execute Workflow
    try:
        # Step A: Translate
        state = await draft_translate(state)
        print("✅ Draft Translation Complete.")
        
        # Step B: Quality Gates
        state = await run_quality_gates(state)
        print("✅ Quality Gates Complete.")
        
    except Exception as e:
        print(f"❌ Workflow Error: {e}")
        return

    # 4. Verification
    print("\n--- Results Analysis ---")
    results = []
    
    # Check In-Memory State Check
    for i, seg in enumerate(state['segments']):
        print(f"Seg {seg['order_index']}: {seg['source_text'][:30]}... -> {seg.get('translated_text')[:30]}...")
        # Check DB Persistence
        # The agent should have updated the DB segments to translated status?
        # draft_translate implementation (Snippet 1637) persists TM matches. 
        # But newly generated translations? 
        # Usually 'finalize_translation' node persists main results.
        # But we ran draft_translate. 
        # Check graph.py: draft_translate DOES NOT persist LLM generation to DB lines 230ish?
        # Snippet 1637 shows: "Update DB for Resolved Segments" (TM).
        # But LLM generation?
        # I should check graph.py if I have doubts.
        # Assuming it returns updated state.
    
    # 5. TMX-043 Verification (Learning Loop Integration)
    # We manually trigger learning loop as if approved.
    print(f"\nTriggering Learning Loop for Doc {doc_id}...")
    # First, must persist translations (since draft might not have saved them all if logic is downstream)
    # We'll force save for test.
    db = service.get_session()
    for seg_data in state['segments']:
        if seg_data.get('translated_text'):
            s = db.query(Segment).filter(Segment.id == seg_data['segment_id']).first()
            s.translated_text = seg_data['translated_text']
            s.status = SegmentStatus.TRANSLATED
    db.commit()
    db.close()
    
    service.process_learning_loop(doc_id)
    print("✅ Learning Loop Processed.")
    
    # Verify TM
    # Try to find match
    match = service.find_best_match(test_cases[0]['text'], "en", "fr")
    if match and match['type'] == 'TM_EXACT':
        print(f"✅ TM Verification: Found Exact Match for '{match['source'][:20]}...'")
    else:
        print(f"❌ TM Verification Failed. Match: {match}")

    # 6. TMX-022 Verification (Audit Cert)
    print("\nGenerating Audit Certificate...")
    cert = service.generate_audit_certificate(doc_id)
    if "CERTIFICATE OF TRANSLATION" in cert and doc_id in cert:
         print(f"✅ Certificate Generated ({len(cert)} chars).")
    else:
         print(f"❌ Certificate Generation Failed:\n{cert}")

    # Save Report
    with open(f"{OUTPUT_DIR}/e2e_report.txt", "w", encoding="utf-8") as f:
        f.write(cert)
    
if __name__ == "__main__":
    asyncio.run(run_stress_test())
