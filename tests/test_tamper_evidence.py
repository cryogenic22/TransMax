import uuid
import json
import pytest
import hashlib
from app.services.db_service import DatabaseService
from app.models.models import AuditRecord

# Helper to get DB session if needed, but we used DatabaseService methods so far.
# We might need direct DB access to perform "Tampering" (bypassing service).

def test_tamper_evidence_lifecycle():
    service = DatabaseService()
    
    # 1. Create a legitimate Audit Record
    job_id = f"job_tamper_{uuid.uuid4().hex}"
    audit_id = f"audit_tamper_{uuid.uuid4().hex}"
    
    # Needs a job to link to? 
    # save_audit_log tries to find the job.
    # We should create a job first using service.create_job.
    service.create_job({
        "request_id": f"req_{job_id}",
        "source_language": "en",
        "target_language": "fr"
    })
    
    # Manually hack the job_id in DB to match what we expect? 
    # Or just capture the job_id returned by create_job.
    # create_job returns job_id.
    
    request_data = {
         "request_id": f"req_{uuid.uuid4()}",
         "source_language": "en", 
         "target_language": "fr"
    }
    real_job_id = service.create_job(request_data)
    real_audit_id = str(uuid.uuid4())
    
    state = {
        "final_decision": "APPROVED",
        "quality_report": {"violations": []},
        "versions": {"model": "v1", "prompts": "v1"},
        "iteration_count": 0
    }
    
    service.save_audit_log(real_job_id, state, real_audit_id)
    
    # 2. Verify Integrity (Should Pass)
    # NOTE: method doesn't exist yet, this will fail/error.
    result = service.verify_audit_integrity(real_audit_id)
    assert result["hash_valid"] is True
    assert result["index_integrity"] is True
    
    # 3. Simulate Tampering: JSON Payload Modification
    # We need to reach into DB and modify row.
    db = service.get_session()
    try:
        record = db.query(AuditRecord).filter(AuditRecord.audit_id == real_audit_id).first()
        original_payload = record.full_payload
        
        # Attack! Change decision in the SIGNED payload
        tampered_payload = dict(original_payload)
        tampered_payload["final_decision"] = "REJECTED" # Was APPROVED
        
        record.full_payload = tampered_payload
        # Do NOT update hash_signature (simulating simple attack)
        db.commit()
    finally:
        db.close()
        
    # Verify again -> Should FAIL hash check
    result_tampered = service.verify_audit_integrity(real_audit_id)
    assert result_tampered["hash_valid"] is False
    
    # 4. Simulate Tampering: Hash Spoofing (Smart Attack)
    # Attacker expects us to check hash, so they recompute hash.
    db = service.get_session()
    try:
        record = db.query(AuditRecord).filter(AuditRecord.audit_id == real_audit_id).first()
        
        # Re-sign the bad logic
        bad_json = json.dumps(record.full_payload, sort_keys=True)
        new_sig = hashlib.sha256(bad_json.encode()).hexdigest()
        
        record.hash_signature = new_sig
        db.commit()
    finally:
        db.close()
        
    # Verify again -> Hash is Valid, BUT...
    # TMX-021 requirement: "Index Drift" check.
    # Wait, if I updated the payload, the 'final_decision' column might differ if I didn't update it.
    # In step 3 I updated `full_payload` so it says "REJECTED".
    # But the column `final_decision` (which was set during creation) is still "APPROVED".
    # So verify should detect Index Drift.
    
    result_spoofed = service.verify_audit_integrity(real_audit_id)
    assert result_spoofed["hash_valid"] is True # The hash matches the payload
    assert result_spoofed["index_integrity"] is False # But columns mismatch payload
    
    # 5. Restore Integrity
    # ...
    
if __name__ == "__main__":
    try:
        test_tamper_evidence_lifecycle()
        print("PASS test_tamper_evidence_lifecycle")
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
