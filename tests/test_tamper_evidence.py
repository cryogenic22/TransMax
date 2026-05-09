import uuid
import json
import pytest
import hashlib
from app.services.db_service import DatabaseService
from app.models.models import AuditRecord

def test_tamper_evidence_lifecycle():
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    service = DatabaseService()

    request_data = {
         "request_id": f"req_{uuid.uuid4()}",
         "source_language": "en",
         "target_language": "fr"
    }

    # TMX-3012: tenant context required for every DB op below.
    with org_context(DEFAULT_ORG_ID):
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
        result = service.verify_audit_integrity(real_audit_id)
        assert result["hash_valid"] is True
        assert result["index_integrity"] is True

        # 3. Simulate Tampering: JSON Payload Modification
        db = service.get_session()
        try:
            record = db.query(AuditRecord).filter(AuditRecord.audit_id == real_audit_id).first()

            tampered_payload = dict(record.full_payload)
            tampered_payload["final_decision"] = "REJECTED"

            record.full_payload = tampered_payload
            db.commit()
        finally:
            db.close()

        # Verify again -> Should FAIL hash check
        result_tampered = service.verify_audit_integrity(real_audit_id)
        assert result_tampered["hash_valid"] is False

        # 4. Simulate Hash Spoofing
        db = service.get_session()
        try:
            record = db.query(AuditRecord).filter(AuditRecord.audit_id == real_audit_id).first()

            bad_json = json.dumps(record.full_payload, sort_keys=True)
            new_sig = hashlib.sha256(bad_json.encode()).hexdigest()
            record.hash_signature = new_sig
            db.commit()
        finally:
            db.close()

        # Hash is valid now, but index integrity should fail
        result_spoofed = service.verify_audit_integrity(real_audit_id)
        assert result_spoofed["hash_valid"] is True
        assert result_spoofed["index_integrity"] is False

if __name__ == "__main__":
    try:
        test_tamper_evidence_lifecycle()
        print("PASS test_tamper_evidence_lifecycle")
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
