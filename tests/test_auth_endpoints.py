"""
Tests for auth API endpoints.
Runs against the FastAPI test client in no-auth mode (default).
"""

import logging

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with AUTH_MODE=none (default)."""
    # Patch settings before importing app
    with patch.dict(
        "os.environ",
        {
            "AUTH_MODE": "none",
            "SECRET_KEY": "test-secret-for-tests",
            "SUPABASE_URL": "http://fake",
            "SUPABASE_KEY": "fake",
            "SUPABASE_SERVICE_KEY": "fake",
            "DATABASE_URL": "sqlite:///test_auth.db",
        },
    ):
        # Clear cached settings
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.main import app

        yield TestClient(app)

        get_settings.cache_clear()


def test_auth_config_returns_none_mode(client):
    """GET /api/auth/config should return auth_mode=none."""
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert data["auth_mode"] == "none"
    assert data["sso_providers"] == []


def test_auth_me_works_in_noauth(client):
    """GET /api/auth/me should return dev admin in no-auth mode."""
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "admin@transmax.local"
    assert data["role"] == "admin"
    assert data["auth_provider"] == "none"


def test_login_noauth_returns_dev_token(client):
    """POST /api/auth/login should work in no-auth mode."""
    res = client.post(
        "/api/auth/login", json={"email": "anything@example.com", "password": ""}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


def test_register_blocked_in_noauth(client):
    """POST /api/auth/register should fail in no-auth mode."""
    res = client.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "password": "password123",
            "name": "New User",
        },
    )
    assert res.status_code == 400


def test_users_list_empty_in_noauth(client):
    """GET /api/auth/users should return empty in no-auth mode."""
    res = client.get("/api/auth/users")
    assert res.status_code == 200
    assert res.json() == []


def test_noauth_documents_endpoint_accessible(client):
    """Existing endpoints should remain accessible in no-auth mode."""
    res = client.get("/api/documents")
    # May return 200 or 500 depending on DB state, but NOT 401
    assert res.status_code != 401


def test_health_check_no_auth_required(client):
    """Health check should never require auth."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_sso_blocked_in_noauth(client):
    """SSO endpoints should fail gracefully in no-auth mode."""
    res = client.get("/api/auth/sso/okta/authorize")
    assert res.status_code == 400


# --- TMX-OIDC-CSRF: OAuth state verification on the callback ---


@pytest.fixture
def oidc_client(monkeypatch):
    """Test client in AUTH_MODE=oidc with a mocked OIDC provider (no network)."""
    with patch.dict(
        "os.environ",
        {
            "AUTH_MODE": "oidc",
            "SECRET_KEY": "test-secret-for-tests",
            "DATABASE_URL": "sqlite:///test_auth.db",
        },
    ):
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.main import app
        import app.api.auth as auth_mod
        from app.auth.permissions import UserRole
        from app.auth.providers import (
            AuthenticatedIdentity,
            OIDCAuthProvider,
            TokenPair,
        )

        # A real OIDCAuthProvider so the endpoint's isinstance check passes, but
        # its network-touching methods are mocked.
        prov = OIDCAuthProvider(
            issuer_url="https://idp.example",
            client_id="cid",
            client_secret="sec",
            redirect_uri="https://app.example/api/auth/sso/okta/callback",
            jwt_secret="jwt-secret",
        )
        prov.get_authorization_url = AsyncMock(
            return_value="https://idp.example/auth?state=x"
        )
        identity = AuthenticatedIdentity(
            user_id="u1",
            email="u@example.com",
            name="U",
            role=UserRole.VIEWER,
            auth_provider="okta",
        )
        tokens = TokenPair(access_token="at", refresh_token="rt", expires_in=1800)
        prov.handle_callback = AsyncMock(return_value=(identity, tokens))
        # _get_auth_mode reads the module-level settings singleton (not get_settings),
        # so flip it + the provider at the auth.py import boundary.
        monkeypatch.setattr(auth_mod, "_get_auth_mode", lambda: "oidc")
        monkeypatch.setattr(auth_mod, "get_auth_provider", lambda: prov)

        get_settings.cache_clear()
        yield TestClient(app), prov
        get_settings.cache_clear()


def test_oidc_authorize_sets_state_cookie(oidc_client):
    c, _ = oidc_client
    res = c.get("/api/auth/sso/okta/authorize")
    assert res.status_code == 200
    state = res.json()["state"]
    sc = res.headers.get("set-cookie", "").lower()
    assert f"oidc_state={state}".lower() in sc
    assert "httponly" in sc and "secure" in sc and "samesite=lax" in sc


def test_oidc_callback_matching_state_proceeds(oidc_client, caplog):
    c, prov = oidc_client
    with caplog.at_level(logging.INFO, logger="app.api.auth"):
        res = c.get(
            "/api/auth/sso/okta/callback",
            params={"code": "abc", "state": "s1"},
            headers={"Cookie": "oidc_state=s1"},
        )
    assert res.status_code == 200
    assert res.json()["access_token"] == "at"
    prov.handle_callback.assert_awaited_once()
    # TMX-LOGIN-AUDIT: a successful SSO login is audited.
    lines = [r.getMessage() for r in caplog.records if "AUTH_EVENT" in r.getMessage()]
    assert any("action=sso_login" in m and "outcome=success" in m for m in lines)


def test_oidc_callback_mismatched_state_rejected(oidc_client):
    c, prov = oidc_client
    res = c.get(
        "/api/auth/sso/okta/callback",
        params={"code": "abc", "state": "s1"},
        headers={"Cookie": "oidc_state=DIFFERENT"},
    )
    assert res.status_code == 400
    prov.handle_callback.assert_not_awaited()  # rejected before any code exchange


def test_oidc_callback_no_cookie_rejected(oidc_client):
    c, prov = oidc_client
    res = c.get("/api/auth/sso/okta/callback", params={"code": "abc", "state": "s1"})
    assert res.status_code == 400
    prov.handle_callback.assert_not_awaited()


def test_oidc_callback_no_state_query_rejected(oidc_client):
    c, prov = oidc_client
    res = c.get(
        "/api/auth/sso/okta/callback",
        params={"code": "abc"},
        headers={"Cookie": "oidc_state=s1"},
    )
    assert res.status_code == 400
    prov.handle_callback.assert_not_awaited()
