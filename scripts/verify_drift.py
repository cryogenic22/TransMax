
import sys
import os
import uuid
import logging

# Add project root
sys.path.append(os.getcwd())

from app.services.db_service import DatabaseService
from app.services.quality_gate import QualityGateService
from app.models.models import TranslationJobQueue, QualityScorecard

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_drift")

def verify_drift_system():
    print("--- Verifying Semantic Drift Operationalization ---")
    
    db_svc = DatabaseService()
    gate_svc = QualityGateService()
    
    # 1. Setup Job & Initial Scorecard
    job_id = str(uuid.uuid4())
    print(f"1. Setup Job {job_id}")
    
    session = db_svc.get_session()
    try:
        # Create Job
        dummy_job = TranslationJobQueue(job_id=job_id, request_id=f"req_{job_id}", source_language="en", target_language="fr", request_json={})
        session.add(dummy_job)
        
        # Create Scorecard directly (skipping Gate logic for isolation)
        sc = QualityScorecard(
            scorecard_id=str(uuid.uuid4()),
            job_id=job_id,
            critical_defect_count=0,
            major_defect_count=0,
            minor_defect_count=0,
            status="PASS",
            semantic_drift_score=0 # Initial
        )
        session.add(sc)
        session.commit()
    finally:
        session.close()

    # 2. Test Drift Calculation (Mocking API Key absence usually results in 0.0)
    print("2. Testing Drift Calculation...")
    source = "Take 10 mg daily."
    back_trans = "Prendre 10 mg par jour." # Similar
    
    # We anticipate 0.0 if no API key, or non-zero if key exists.
    # We just want to ensure it runs without error.
    score = gate_svc.calculate_semantic_drift(source, back_trans)
    print(f"   -> Calculated Drift Score: {score}")

    # 3. Test Persistence Update
    print("3. Testing Persistence Update...")
    fake_score = 85 # Simulate a calculated score
    db_svc.update_quality_scorecard_metric(job_id, {"drift_score": fake_score})
    
    # 4. Verify DB
    session = db_svc.get_session()
    try:
        sc = session.query(QualityScorecard).filter(QualityScorecard.job_id == job_id).first()
        if not sc:
            print("FAIL: Scorecard not found.")
            sys.exit(1)
            
        print(f"   -> DB Drift Score: {sc.semantic_drift_score}")
        
        if sc.semantic_drift_score != fake_score:
            print(f"FAIL: Expected {fake_score}, got {sc.semantic_drift_score}")
            sys.exit(1)
            
    finally:
        session.close()

    print("*** DRIFT SYSTEM VERIFIED ***")

if __name__ == "__main__":
    verify_drift_system()
