"""
Tests for Module B: Black Book v2 Enterprise Knowledge.
Covers rule CRUD, import/export, testing sandbox, analytics, and glossary management.
"""
import pytest
import json
import io
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with no-auth mode."""
    import os
    os.environ["AUTH_MODE"] = "none"
    from app.main import app
    return TestClient(app)


# ── Rule CRUD ────────────────────────────────────────────────────────

class TestRuleCRUD:
    def test_create_rule(self, client):
        resp = client.post("/api/knowledge/rules", json={
            "source_pattern": "adverse event",
            "target_correction": "événement indésirable",
            "context_tag": "pharma",
            "domain": "pharma",
            "source_language": "en",
            "target_language": "fr",
            "is_strict": True,
            "priority": 10,
            "description": "Standard pharma terminology",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_pattern"] == "adverse event"
        assert data["is_strict"] is True
        assert data["status"] == "ACTIVE"
        assert data["domain"] == "pharma"

    def test_list_rules(self, client):
        resp = client.get("/api/knowledge/rules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_rules_filter_domain(self, client):
        # Create a rule first
        client.post("/api/knowledge/rules", json={
            "source_pattern": "test_domain_filter",
            "target_correction": "test",
            "domain": "legal",
        })
        resp = client.get("/api/knowledge/rules?domain=legal")
        assert resp.status_code == 200

    def test_update_rule(self, client):
        # Create
        create_resp = client.post("/api/knowledge/rules", json={
            "source_pattern": "to_update",
            "target_correction": "original",
        })
        rule_id = create_resp.json()["rule_id"]

        # Update
        resp = client.patch(f"/api/knowledge/rules/{rule_id}", json={
            "target_correction": "updated_correction",
            "priority": 99,
        })
        assert resp.status_code == 200
        assert resp.json()["target_correction"] == "updated_correction"
        assert resp.json()["priority"] == 99

    def test_delete_rule(self, client):
        create_resp = client.post("/api/knowledge/rules", json={
            "source_pattern": "to_delete",
            "target_correction": "delete_me",
        })
        rule_id = create_resp.json()["rule_id"]

        resp = client.delete(f"/api/knowledge/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_update_nonexistent_rule(self, client):
        resp = client.patch("/api/knowledge/rules/nonexistent-id", json={"status": "ACTIVE"})
        assert resp.status_code == 404

    def test_create_regex_rule(self, client):
        resp = client.post("/api/knowledge/rules", json={
            "source_pattern": r"\b\d+\s*mg\b",
            "target_correction": "Keep dosage unchanged",
            "is_regex": True,
            "domain": "pharma",
        })
        assert resp.status_code == 200
        assert resp.json()["is_regex"] is True

    def test_create_invalid_regex_rejected(self, client):
        resp = client.post("/api/knowledge/rules", json={
            "source_pattern": "[invalid(regex",
            "target_correction": "test",
            "is_regex": True,
        })
        assert resp.status_code == 400


# ── Rule Testing Sandbox ─────────────────────────────────────────────

class TestRuleSandbox:
    def test_literal_match_fires(self, client):
        resp = client.post("/api/knowledge/rules/test", json={
            "source_pattern": "adverse event",
            "target_correction": "événement indésirable",
            "is_regex": False,
            "test_source": "The patient reported an adverse event during the trial.",
            "test_target": "Le patient a signalé un problème pendant l'essai.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["would_fire"] is True
        assert len(data["source_matches"]) == 1
        assert data["target_has_correction"] is False

    def test_literal_match_passes(self, client):
        resp = client.post("/api/knowledge/rules/test", json={
            "source_pattern": "adverse event",
            "target_correction": "événement indésirable",
            "is_regex": False,
            "test_source": "The patient reported an adverse event.",
            "test_target": "Le patient a signalé un événement indésirable.",
        })
        data = resp.json()
        assert data["would_fire"] is False
        assert data["target_has_correction"] is True

    def test_regex_match(self, client):
        resp = client.post("/api/knowledge/rules/test", json={
            "source_pattern": r"\b\d+\s*mg\b",
            "target_correction": "mg",
            "is_regex": True,
            "test_source": "Take 500 mg twice daily.",
            "test_target": "Prendre 500 mg deux fois par jour.",
        })
        data = resp.json()
        assert data["would_fire"] is False  # target has "mg"
        assert len(data["source_matches"]) == 1

    def test_invalid_regex_in_test(self, client):
        resp = client.post("/api/knowledge/rules/test", json={
            "source_pattern": "[bad(regex",
            "target_correction": "test",
            "is_regex": True,
            "test_source": "test",
            "test_target": "test",
        })
        assert resp.status_code == 400


# ── Import / Export ──────────────────────────────────────────────────

class TestImportExport:
    def test_export_json(self, client):
        # Create a rule first
        client.post("/api/knowledge/rules", json={
            "source_pattern": "export_test",
            "target_correction": "test_export",
            "domain": "pharma",
        })
        resp = client.get("/api/knowledge/rules/export?format=json")
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data, list)

    def test_export_csv(self, client):
        resp = client.get("/api/knowledge/rules/export?format=csv")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "source_pattern" in content  # Header row

    def test_import_csv(self, client):
        csv_content = "source_pattern,target_correction,context_tag,domain,is_regex,is_strict,priority,description\n"
        csv_content += "test import,importation test,pharma,pharma,false,false,5,Test import rule\n"
        csv_content += "another rule,autre règle,pharma,pharma,false,true,10,\n"

        files = {"file": ("rules.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post("/api/knowledge/rules/import", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 0

    def test_import_json(self, client):
        rules = [
            {"source_pattern": "json import", "target_correction": "importation json", "domain": "legal"},
        ]
        content = json.dumps(rules)
        files = {"file": ("rules.json", io.BytesIO(content.encode()), "application/json")}
        resp = client.post("/api/knowledge/rules/import", files=files)
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1

    def test_import_skips_empty(self, client):
        csv_content = "source_pattern,target_correction\n,\nempty,\n"
        files = {"file": ("rules.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post("/api/knowledge/rules/import", files=files)
        assert resp.status_code == 200
        assert resp.json()["skipped"] >= 1


# ── Analytics ────────────────────────────────────────────────────────

class TestRuleAnalytics:
    def test_get_analytics(self, client):
        resp = client.get("/api/knowledge/rules/analytics")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_report_false_positive(self, client):
        # Create rule
        create_resp = client.post("/api/knowledge/rules", json={
            "source_pattern": "fp_test",
            "target_correction": "test",
        })
        rule_id = create_resp.json()["rule_id"]

        # Report false positive
        resp = client.post(f"/api/knowledge/rules/{rule_id}/report-false-positive")
        assert resp.status_code == 200
        assert resp.json()["false_positive_count"] == 1

        # Report again
        resp = client.post(f"/api/knowledge/rules/{rule_id}/report-false-positive")
        assert resp.json()["false_positive_count"] == 2

    def test_report_fp_nonexistent(self, client):
        resp = client.post("/api/knowledge/rules/nonexistent/report-false-positive")
        assert resp.status_code == 404


# ── Feedback ─────────────────────────────────────────────────────────

class TestFeedback:
    def test_negative_feedback_creates_rule(self, client):
        resp = client.post("/api/knowledge/feedback", json={
            "source_text": "adverse reaction",
            "target_text": "réaction adverse",
            "corrected_text": "effet indésirable",
            "rating": "negative",
            "target_language": "fr",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "rule_created"

    def test_positive_feedback_no_rule(self, client):
        resp = client.post("/api/knowledge/feedback", json={
            "source_text": "test",
            "target_text": "test",
            "rating": "positive",
            "target_language": "fr",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "feedback_recorded"


# ── Model Schema Tests ───────────────────────────────────────────────

class TestTranslationRuleModel:
    def test_new_fields_exist(self):
        from app.models.models import TranslationRule
        # Verify all new Black Book v2 columns exist
        columns = {c.name for c in TranslationRule.__table__.columns}
        assert "source_language" in columns
        assert "target_language" in columns
        assert "project_id" in columns
        assert "domain" in columns
        assert "is_regex" in columns
        assert "is_strict" in columns
        assert "priority" in columns
        assert "description" in columns
        assert "fire_count" in columns
        assert "last_fired_at" in columns
        assert "false_positive_count" in columns
        assert "created_by" in columns
