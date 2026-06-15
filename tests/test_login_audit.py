"""TMX-LOGIN-AUDIT — structured AUTH_EVENT audit lines for the auth flows.

The helper tests pin the schema + the A3 no-secret contract + fail-safe; the
none-mode login/refresh tests prove the wiring (no DB dependency — NoAuthProvider
issues a dev token without touching the DB).
"""

import logging

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.api.auth import _audit_auth_event


def test_helper_emits_structured_line_without_secret(caplog):
    with caplog.at_level(logging.INFO, logger="app.api.auth"):
        _audit_auth_event(
            "login",
            "failure",
            actor="a@b.com",
            provider="local",
            detail="invalid_credentials",
        )
    line = next(
        r.getMessage() for r in caplog.records if "AUTH_EVENT" in r.getMessage()
    )
    assert "action=login" in line and "outcome=failure" in line
    assert "actor=a@b.com" in line and "provider=local" in line
    assert "detail=invalid_credentials" in line
    assert "password" not in line.lower() and "token" not in line.lower()


def test_helper_never_raises_on_bad_args():
    # The audit side-channel must never break auth, even on odd input.
    _audit_auth_event(None, None)
    _audit_auth_event("x", "y", actor=object())


@pytest.fixture
def client():
    with patch.dict(
        "os.environ",
        {
            "AUTH_MODE": "none",
            "SECRET_KEY": "test-secret-for-tests",
            "DATABASE_URL": "sqlite:///test_auth.db",
        },
    ):
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.main import app

        yield TestClient(app)
        get_settings.cache_clear()


def _auth_lines(caplog):
    return [r.getMessage() for r in caplog.records if "AUTH_EVENT" in r.getMessage()]


def test_login_emits_success_audit(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.api.auth"):
        res = client.post(
            "/api/auth/login", json={"email": "x@y.com", "password": "s3cr3t-pw-value"}
        )
    assert res.status_code == 200
    lines = _auth_lines(caplog)
    assert any("action=login" in m and "outcome=success" in m for m in lines)
    # A3: the actual request password must never appear in the audit trail.
    assert all("s3cr3t-pw-value" not in m for m in lines)


def test_refresh_emits_success_audit(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.api.auth"):
        res = client.post("/api/auth/refresh", json={"refresh_token": "anything"})
    assert res.status_code == 200
    lines = _auth_lines(caplog)
    assert any("action=refresh" in m and "outcome=success" in m for m in lines)
