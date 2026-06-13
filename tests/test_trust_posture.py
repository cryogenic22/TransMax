"""TMX-TRUST-POSTURE — the posture endpoint is real + honest (A1/A3)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_posture_returns_real_controls():
    r = client.get("/api/trust/posture")
    assert r.status_code == 200
    data = r.json()
    by_key = {c["key"]: c for c in data["controls"]}
    assert {"auth", "audit_chain", "pii", "llm_supplier",
            "data_residency", "encryption_at_rest"} <= set(by_key)


def test_posture_is_honest_not_fabricated():
    body = client.get("/api/trust/posture").text
    # the old fabricated panel's invented specifics must be gone
    for fake in ("US-EAST-2", "AES-256", "NER_V2", "NO_STORE", "14,203"):
        assert fake not in body


def test_infra_controls_not_faked_verified():
    by_key = {c["key"]: c for c in client.get("/api/trust/posture").json()["controls"]}
    # we cannot assert these from the app layer -> must be unverified, not green
    assert by_key["encryption_at_rest"]["verified"] is False
    assert by_key["data_residency"]["verified"] is False
    # ones we genuinely can assert
    assert by_key["audit_chain"]["verified"] is True
    assert by_key["pii"]["verified"] is True
