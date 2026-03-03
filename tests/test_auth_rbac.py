"""
Tests for RBAC enforcement — verifies that role-based guards work correctly.
Uses mocked auth to inject different roles and verify 403 responses.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.auth.providers import AuthenticatedIdentity
from app.auth.permissions import UserRole, Permission


def make_user(role: UserRole) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        user_id=f"test-{role.value}",
        email=f"{role.value}@test.com",
        name=f"Test {role.value}",
        role=role,
        auth_provider="test",
    )


@pytest.fixture
def app():
    with patch.dict("os.environ", {
        "AUTH_MODE": "jwt",
        "SECRET_KEY": "test-secret-for-rbac-tests",
        "SUPABASE_URL": "http://fake",
        "SUPABASE_KEY": "fake",
        "SUPABASE_SERVICE_KEY": "fake",
        "DATABASE_URL": "sqlite:///test_rbac.db",
    }):
        from app.core.config import get_settings
        get_settings.cache_clear()
        from app.main import app
        yield app
        get_settings.cache_clear()


def make_client_with_role(app, role: UserRole):
    """Create a test client that injects a specific role."""
    from app.auth.dependencies import get_current_user

    user = make_user(role)

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    return client, user


def test_viewer_can_list_documents(app):
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    res = client.get("/api/documents")
    # Should not be 403 — viewers can read
    assert res.status_code != 403
    app.dependency_overrides.clear()


def test_viewer_cannot_create_document(app):
    """Viewers lack DOCUMENT_CREATE permission."""
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    # POST to create document — should get 403
    res = client.post("/api/documents",
                      files={"file": ("test.txt", b"hello", "text/plain")},
                      data={"source_language": "en"})
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_translator_can_access_tools(app):
    """Translators can use tools."""
    client, _ = make_client_with_role(app, UserRole.TRANSLATOR)
    # POST to tools — should not be 403 (may fail on other grounds like missing LLM)
    res = client.post("/api/tools/audit", json={
        "source_text": "test", "translated_text": "test", "target_language": "de"
    })
    assert res.status_code != 403
    app.dependency_overrides.clear()


def test_reviewer_cannot_edit_segments(app):
    """Reviewers lack SEGMENT_EDIT permission."""
    client, _ = make_client_with_role(app, UserRole.REVIEWER)
    res = client.patch("/api/segments/fake-id", json={
        "translated_text": "edited", "reason": "test"
    })
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_curator_cannot_delete_documents(app):
    """Curators lack DOCUMENT_DELETE permission."""
    client, _ = make_client_with_role(app, UserRole.CURATOR)
    res = client.delete("/api/documents/fake-id")
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_admin_can_access_users(app):
    """Admins can list users."""
    client, _ = make_client_with_role(app, UserRole.ADMIN)
    res = client.get("/api/auth/users")
    assert res.status_code != 403
    app.dependency_overrides.clear()


def test_viewer_cannot_manage_users(app):
    """Viewers lack USERS_MANAGE permission."""
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    res = client.patch("/api/auth/users/fake-id/role", json={"role": "admin"})
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_curator_can_manage_knowledge(app):
    """Curators have KNOWLEDGE_MANAGE permission."""
    client, _ = make_client_with_role(app, UserRole.CURATOR)
    res = client.patch("/api/knowledge/rules/fake-id", json={"status": "ACTIVE"})
    # Should not be 403 (may be 404 or 500, but not permission denied)
    assert res.status_code != 403
    app.dependency_overrides.clear()
