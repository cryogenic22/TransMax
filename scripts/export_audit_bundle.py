
import sys
import os
import json
import uuid

# Add project root
sys.path.append(os.getcwd())

from app.services.audit_service import AuditService
from app.models.database import SessionLocal 
from app.models.models import TranslationJobQueue

def export_bundle():
    print("--- Exporting Defense Bundle ---")
    audit_svc = AuditService()
    
    # 1. Setup Data
    job_id = str(uuid.uuid4())
    session = SessionLocal()
    try:
        dummy_job = TranslationJobQueue(job_id=job_id, request_id=f"req_{job_id}", source_language="en", target_language="fr", request_json={})
        session.add(dummy_job)
        session.commit()
    finally:
        session.close()
        
    audit_id = audit_svc.create_audit_trail(job_id)
    audit_svc.capture_config_snapshot(job_id, {"frozen_param": "confirmed"})
    audit_svc.log_event(audit_id, "TEST_EVENT", {"data": "secure"})
    
    # 2. Generate Bundle
    print(f"Generating bundle for {audit_id}...")
    bundle = audit_svc.generate_audit_bundle(audit_id)
    
    # 3. Print Summary
    print(f"Bundle ID: {bundle['bundle_id']}")
    print(f"Integrity: {bundle['integrity_status']}")
    print(f"Events: {len(bundle['chain_of_custody'])}")
    print("Config Frozen:", bundle['configuration_frozen'])
    
    # 4. Save to file
    with open("defense_bundle_sample.json", "w") as f:
        json.dump(bundle, f, indent=2)
    print("Saved to defense_bundle_sample.json")

    if bundle['integrity_status'] == "PASS":
        print("*** EXPORT SUCCESS ***")
        sys.exit(0)
    else:
        print("*** EXPORT FAILED (Integrity) ***")
        sys.exit(1)

if __name__ == "__main__":
    export_bundle()
