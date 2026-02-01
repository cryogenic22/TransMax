
import sys
import os
import uuid
import json
import logging

# Add project root
sys.path.append(os.getcwd())

from app.services.audit_service import AuditService
from app.models.database import SessionLocal 
from app.models.models import AuditLogEntry, TranslationJobQueue # direct access for tampering

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_audit")

def verify_audit_system():
    print("--- Verifying Audit Chain System ---")
    
    audit_svc = AuditService()
    job_id = str(uuid.uuid4())
    
    # 0. Create Dummy Job (Required for FK)
    session = SessionLocal()
    try:
        dummy_job = TranslationJobQueue(
            job_id=job_id,
            request_id=f"req_{job_id}",
            source_language="en",
            target_language="fr",
            request_json={}
        )
        session.add(dummy_job)
        session.commit()
    finally:
        session.close()

    # 1. Create Trail
    print(f"1. Creating Audit Trail for Job {job_id}...")
    audit_id = audit_svc.create_audit_trail(job_id)
    print(f"   -> Audit ID: {audit_id}")
    
    # 2. Config Snapshot
    print("2. Capturing Config Snapshot...")
    audit_svc.capture_config_snapshot(job_id, {"model": "gpt-4", "profile": "EMA_v1"})
    print("   -> Snapshot captured.")
    
    # 3. Log Events
    print("3. Logging Events...")
    e1 = audit_svc.log_event(audit_id, "START", {"user": "kapil"})
    e2 = audit_svc.log_event(audit_id, "PROCESS", {"segments": 5})
    e3 = audit_svc.log_event(audit_id, "FINISH", {"status": "SUCCESS"})
    print(f"   -> Logged 3 events. Last ID: {e3}")
    
    # 4. Verify Integrity (Should Pass)
    print("4. Verifying Integrity (Expect PASS)...")
    check1 = audit_svc.verify_chain_integrity(audit_id)
    if check1["valid"]:
        print("   SUCCESS: Chain is valid.")
    else:
        print(f"   FAILURE: Chain invalid! {check1}")
        return False
        
    # 5. TAMPERING SIMULATION
    print("5. Simulating DB Tampering...")
    session = SessionLocal()
    try:
        # Fetch the middle event (e2) and change payload
        entry = session.query(AuditLogEntry).filter(AuditLogEntry.entry_id == e2).first()
        print(f"   Tampering with event {entry.sequence_index} ({entry.event_type})...")
        
        # Modify payload WITHOUT updating hash (Simulating SQL injection or direct DB edit)
        # Note: In SQLite/Postgres JSON is stored as string often, but SQLAlchemy handles it.
        # We modify the python dict and commit.
        fake_payload = entry.payload.copy()
        fake_payload["segments"] = 999 # Changed 5 to 999
        entry.payload = fake_payload
        
        session.commit()
        print("   Tampering committed.")
    finally:
        session.close()
        
    # 6. Verify Integrity (Should Fail)
    print("6. Verifying Integrity (Expect FAIL)...")
    check2 = audit_svc.verify_chain_integrity(audit_id)
    
    if not check2["valid"]:
        print(f"   SUCCESS: Tampering detected! Broken at index {check2.get('broken_at')}")
        print(f"   Details: {check2.get('details')}")
    else:
        print("   FAILURE: Tampering NOT detected! The system is not secure.")
        return False
        
    return True

if __name__ == "__main__":
    if verify_audit_system():
        print("\n*** AUDIT SYSTEM VERIFIED ***")
        sys.exit(0)
    else:
        print("\n*** VERIFICATION FAILED ***")
        sys.exit(1)
