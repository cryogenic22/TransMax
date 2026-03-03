"""
Tests for auth API endpoints.
Runs against the FastAPI test client in no-auth mode (default).
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with AUTH_MODE=none (default)."""
    # Patch settings before importing app
    with patch.dict("os.environ", {
        "AUTH_MODE": "none",
        "SECRET_KEY": "test-secret-for-tests",
        "SUPABASE_URL": "http://fake",
        "SUPABASE_KEY": "fake",
        "SUPABASE_SERVICE_KEY": "fake",
        "DATABASE_URL": "sqlite:///test_auth.db",
    }):
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
    res = client.post("/api/auth/login", json={
        "email": "anything@example.com",
        "password": ""
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


def test_register_blocked_in_noauth(client):
    """POST /api/auth/register should fail in no-auth mode."""
    res = client.post("/api/auth/register", json={
        "email": "new@example.com",
        "password": "password123",
        "name": "New User"
    })
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
