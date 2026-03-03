"""Tests for audit bundle export."""

from transmax_sdk.audit.service import HashChainedAuditTrail


class TestAuditBundleExport:
    def test_bundle_contains_required_fields(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "JOB_STARTED", {"status": "init"})
        audit.log_event(audit_id, "TRANSLATION_COMPLETE", {"segments": 5})

        bundle = audit.export_bundle(audit_id)
        assert "bundle_id" in bundle
        assert "generated_at" in bundle
        assert "integrity_status" in bundle
        assert "context" in bundle
        assert "chain_of_custody" in bundle

    def test_bundle_integrity_pass(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "E1", {"a": 1})

        bundle = audit.export_bundle(audit_id)
        assert bundle["integrity_status"] == "PASS"

    def test_bundle_includes_config_snapshot(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.capture_config(audit_id, {"model": "gpt-4o", "version": "1.0"})
        audit.log_event(audit_id, "E1", {"a": 1})

        bundle = audit.export_bundle(audit_id)
        assert bundle["configuration_frozen"] is not None
        assert bundle["configuration_frozen"]["model"] == "gpt-4o"

    def test_bundle_chain_of_custody_ordered(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        audit.log_event(audit_id, "STEP_1", {"i": 1})
        audit.log_event(audit_id, "STEP_2", {"i": 2})
        audit.log_event(audit_id, "STEP_3", {"i": 3})

        bundle = audit.export_bundle(audit_id)
        chain = bundle["chain_of_custody"]
        assert len(chain) == 3
        for i, entry in enumerate(chain):
            assert entry["sequence"] == i

    def test_bundle_context_contains_job_id(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_42")
        bundle = audit.export_bundle(audit_id)
        assert bundle["context"]["job_id"] == "job_42"
        assert bundle["context"]["audit_id"] == audit_id

    def test_reviewer_action_logged(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        entry_id = audit.log_reviewer_action(
            audit_id, "APPROVE", "reviewer_1", "All looks good"
        )
        assert entry_id

        trail = audit.get_trail(audit_id)
        assert trail.entries[-1].event_type == "REVIEW_ACKNOWLEDGED"
        assert trail.entries[-1].payload["action"] == "APPROVE"

    def test_invalid_reviewer_action_raises(self):
        audit = HashChainedAuditTrail()
        audit_id = audit.create_trail("job_1")
        try:
            audit.log_reviewer_action(audit_id, "INVALID", "user", "reason")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
