"""Tests for hash-chained audit trail."""

from transmax_sdk.audit.service import HashChainedAuditTrail, GENESIS_HASH


class TestHashChainIntegrity:
    def test_create_trail(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        assert audit_id
        trail = audit.get_trail(audit_id)
        assert trail.job_id == "job_1"
        assert len(trail.entries) == 0

    def test_log_single_event(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        entry_id = audit.log_event(audit_id, "JOB_STARTED", {"status": "processing"})
        assert entry_id
        trail = audit.get_trail(audit_id)
        assert len(trail.entries) == 1
        assert trail.entries[0].event_type == "JOB_STARTED"
        assert trail.entries[0].previous_hash == GENESIS_HASH

    def test_chain_links_correctly(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "EVENT_1", {"a": 1})
        audit.log_event(audit_id, "EVENT_2", {"b": 2})
        audit.log_event(audit_id, "EVENT_3", {"c": 3})

        trail = audit.get_trail(audit_id)
        assert len(trail.entries) == 3

        # Chain links: each entry's previous_hash == prior entry's hash
        assert trail.entries[0].previous_hash == GENESIS_HASH
        assert trail.entries[1].previous_hash == trail.entries[0].entry_hash
        assert trail.entries[2].previous_hash == trail.entries[1].entry_hash

    def test_chain_integrity_valid(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        for i in range(10):
            audit.log_event(audit_id, f"EVENT_{i}", {"index": i})

        result = audit.verify_integrity(audit_id)
        assert result["valid"] is True

    def test_chain_head_updated(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"x": 1})
        trail = audit.get_trail(audit_id)
        assert trail.chain_head_hash == trail.entries[-1].entry_hash

    def test_empty_chain_valid(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        result = audit.verify_integrity(audit_id)
        assert result["valid"] is True

    def test_sequence_indexes_sequential(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        for i in range(5):
            audit.log_event(audit_id, "E", {"i": i})

        trail = audit.get_trail(audit_id)
        for i, entry in enumerate(trail.entries):
            assert entry.sequence_index == i
