
import sys
import os
import asyncio
import json
import uuid
import logging
from datetime import datetime

# Add project root
sys.path.append(os.getcwd())

from app.agents.graph import app as workflow_app
from app.services.db_service import DatabaseService
from app.models.database import Document, Segment, DocumentStatus, SegmentStatus
from app.models.models import TranslationJobQueue

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo_quality_ar_ja")

# Clinical Snippet (SmPC)
# Designed to test:
# 1. JA: "Do not drink" -> Should fail variant check if naive "飲まない".
# 2. AR: Numbers "10 mg" -> Should pass number check (supports Western/Hindi).
SOURCE_TEXT = "Patients with severe renal impairment (creatinine clearance < 30 ml/min) should reduce the dose to 10 mg daily. Do not drink alcohol while taking this medication."

async def run_demo(target_lang: str):
    print(f"\n========================================")
    print(f"Running Agentic Demo: EN -> {target_lang.upper()}")
    print(f"Source: {SOURCE_TEXT}")
    print(f"========================================")
    
    db = DatabaseService()
    session = db.get_session()
    
    # 1. Setup Data
    job_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    
    # Create Doc
    doc = Document(
        id=doc_id, 
        name=f"test_quality_{target_lang}.txt", 
        source_language="en", 
        target_language=target_lang,
        status="UPLOADED"
    )
    session.add(doc)
    
    # Create Segment
    seg = Segment(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        order_index=1,
        source_text=SOURCE_TEXT,
        status="PENDING"
    )
    session.add(seg)
    
    # Create Job Record
    job = TranslationJobQueue(
        job_id=job_id,
        request_id=f"req_{job_id}",
        source_language="en",
        target_language=target_lang,
        status="PROCESSING",
        request_json={"source": SOURCE_TEXT}
    )
    session.add(job)
    
    session.commit()
    session.close() 
    
    # 2. Run Graph
    inputs = {
        "doc_id": doc_id,
        "target_language": target_lang,
        "job_id": job_id,
        "segments": [],
        "constraint_pack": {}
    }
    
    # Use try-except to catch any latent graph errors but show results
    try:
        final_state = await workflow_app.ainvoke(inputs)
        
        # 3. Analyze Results
        print("\n--- AGENTIC RESULT ---")
        segments = final_state.get('segments', [])
        for s in segments:
            print(f"Target ({target_lang}): {s.get('translated_text')}")
            print(f"Reverse   : {s.get('reverse_translation')}")
            
        report = final_state.get('quality_report', {})
        print(f"\n--- QUALITY SCORECARD ---")
        print(f"Status: {report.get('status')}")
        print(f"Drift Score: {report.get('scorecard', {}).get('drift_score')}")
        print(f"Violations: {len(report.get('violations', []))}")
        print(f"Raw Report: {report}")
        for v in report.get('violations', []):
            print(f" - [{v.get('severity')}] {v.get('message')}")
            
    except Exception as e:
        logger.error(f"Graph Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # print("Starting Arabic Evaluation...")
    # asyncio.run(run_demo("ar"))
    print("\nStarting Japanese Evaluation...")
    asyncio.run(run_demo("ja"))
