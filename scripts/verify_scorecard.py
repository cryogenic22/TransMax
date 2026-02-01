
import sys
import os
import uuid
import logging

# Add project root
sys.path.append(os.getcwd())

from app.services.db_service import DatabaseService
from app.services.quality_gate import QualityGateService
from app.services.audit_service import AuditService
from app.core.defect_taxonomy import DefectSeverity, DefectCategory
from app.models.models import TranslationJobQueue, QualityScorecard, ScorecardEntry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_scorecard")

def verify_scorecard_system():
    print("--- Verifying Quality Scorecard & Risk Control ---")
    
    db_svc = DatabaseService()
    audit_svc = AuditService()
    gate_svc = QualityGateService()
    
    # 1. Setup Job & Audit
    job_id = str(uuid.uuid4())
    
    # Create Dummy Job (for FK)
    session = db_svc.get_session()
    try:
        dummy_job = TranslationJobQueue(job_id=job_id, request_id=f"req_{job_id}", source_language="en", target_language="fr", request_json={})
        session.add(dummy_job)
        session.commit()
    finally:
        session.close()

    audit_id = audit_svc.create_audit_trail(job_id)

    # 2. Simulate Segments with Critical Defect
    print("2. Simulating Segments with CRITICAL Defect...")
    # "Take 10 mg daily" -> "Prendre 10 daily" (Missing Unit 'mg')
    source_text = "Take 10 mg daily"
    target_text = "Prendre 10 daily" 
    
    defects = gate_svc.check_segment(source_text, target_text, constraints={}, target_lang="fr")
    
    
    # Verify Detection
    critical_defects = [d for d in defects if d['severity'] == DefectSeverity.CRITICAL.value]
    if not critical_defects:
        print("FAIL: Quality Gate did not detect Critical Unit defects.")
        sys.exit(1)
    
    print(f"   -> Detected {len(critical_defects)} Critical Defects: {[d['message'] for d in critical_defects]}")
    
    # 3. Simulate Graph Logic: Save Scorecard
    print("3. Saving Scorecard...")
    
    # Convert dataclasses to dicts for serialization (simulating service boundary)
    # Update: check_segment now returns serialized dicts, so we just use them.
    # We might want to inject a segment_id if missing for the test
    for d in defects:
        if not d.get("segment_id"):
            d["segment_id"] = "seg_test_1"
            
    defects_serialized = defects
    
    scorecard_data = {
        "status": "BLOCKED", # Logic determined it is blocked
        "drift_score": 15,
        "pass_rate": 0
    }
    
    scorecard_id = db_svc.save_quality_scorecard(job_id, scorecard_data, defects_serialized)
    
    # 4. Verify Persistence
    print("4. Verifying Persistence...")
    session = db_svc.get_session()
    try:
        sc = session.query(QualityScorecard).filter(QualityScorecard.scorecard_id == scorecard_id).first()
        if not sc:
            print("FAIL: Scorecard not found in DB.")
            sys.exit(1)
            
        print(f"   Scorecard Status: {sc.status}")
        print(f"   Critical Count: {sc.critical_defect_count}")
        
        if sc.status != "BLOCKED":
            print("FAIL: Status should be BLOCKED.")
            sys.exit(1)
            
        if sc.critical_defect_count != 1:
            print("FAIL: Critical count mismatch.")
            sys.exit(1)
            
        # Verify Entries
        entries = session.query(ScorecardEntry).filter(ScorecardEntry.scorecard_id == scorecard_id).all()
        print(f"   Entries Found: {len(entries)}")
        if len(entries) != 1:
             print("FAIL: Entry count mismatch.")
             sys.exit(1)
             
        entry = entries[0]
        if entry.severity != DefectSeverity.CRITICAL.value:
            print("FAIL: Entry severity mismatch.")
            sys.exit(1)

    finally:
        session.close()
        
    print("*** QUALITY CONTROL VERIFIED ***")

if __name__ == "__main__":
    verify_scorecard_system()
