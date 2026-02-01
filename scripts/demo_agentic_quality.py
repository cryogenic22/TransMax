
import sys
import os
import asyncio
import json
import uuid
import logging

# Add project root
sys.path.append(os.getcwd())

from app.agents.graph import app as workflow_app
from app.services.db_service import DatabaseService
from app.models.database import Document, Segment, DocumentStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo_quality")

# Clinical Snippet (SmPC)
SOURCE_TEXT = "Patients with severe renal impairment (creatinine clearance < 30 ml/min) should reduce the dose to 10 mg daily. Do NOT crush or chew the tablet."

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
    
    # Create Job Record (Required for Scorecard/Audit FKs)
    from app.models.models import TranslationJobQueue
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
    session.close() # Close to allow graph services to use their own sessions
    
    # 2. Run Graph
    inputs = {
        "doc_id": doc_id,
        "target_language": target_lang,
        "job_id": job_id,
        "segments": [], # Will be loaded by 'load_segments' node
        "constraint_pack": {}
    }
    
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
    for v in report.get('violations', []):
        print(f" - [{v.get('severity')}] {v.get('message')}")
        
    return final_state

if __name__ == "__main__":
    asyncio.run(run_demo("fr"))
    asyncio.run(run_demo("es"))
