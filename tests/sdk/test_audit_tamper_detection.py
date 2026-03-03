"""Tests for audit tamper detection."""

from transmax_sdk.audit.service import HashChainedAuditTrail


class TestAuditTamperDetection:
    def test_tampered_payload_detected(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"dosage": "10mg"})
        audit.log_event(audit_id, "E2", {"dosage": "20mg"})

        # Tamper: modify payload of first entry
        trail = audit.get_trail(audit_id)
        trail.entries[0].payload = {"dosage": "100mg"}  # TAMPERED

        result = audit.verify_integrity(audit_id)
        assert result["valid"] is False
        assert result["broken_at"] == 0

    def test_tampered_hash_detected(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"a": 1})
        audit.log_event(audit_id, "E2", {"b": 2})

        # Tamper: change the hash of first entry
        trail = audit.get_trail(audit_id)
        trail.entries[0].entry_hash = "deadbeef"

        result = audit.verify_integrity(audit_id)
        assert result["valid"] is False

    def test_deleted_entry_detected(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"a": 1})
        audit.log_event(audit_id, "E2", {"b": 2})
        audit.log_event(audit_id, "E3", {"c": 3})

        # Tamper: remove middle entry
        trail = audit.get_trail(audit_id)
        trail.entries.pop(1)

        result = audit.verify_integrity(audit_id)
        assert result["valid"] is False

    def test_inserted_entry_detected(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"a": 1})
        audit.log_event(audit_id, "E2", {"b": 2})

        # Tamper: modify the second entry's previous_hash
        trail = audit.get_trail(audit_id)
        trail.entries[1].previous_hash = "fake_hash"

        result = audit.verify_integrity(audit_id)
        assert result["valid"] is False
