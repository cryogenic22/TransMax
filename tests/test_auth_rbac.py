"""
Tests for RBAC enforcement — verifies that role-based guards work correctly.
Uses mocked auth to inject different roles and verify 403 responses.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.auth.providers import AuthenticatedIdentity
from app.auth.permissions import UserRole


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
    with patch.dict(
        "os.environ",
        {
            "AUTH_MODE": "jwt",
            "SECRET_KEY": "test-secret-for-rbac-tests",
            "SUPABASE_URL": "http://fake",
            "SUPABASE_KEY": "fake",
            "SUPABASE_SERVICE_KEY": "fake",
            "DATABASE_URL": "sqlite:///test_rbac.db",
        },
    ):
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
    res = client.post(
        "/api/documents",
        files={"file": ("test.txt", b"hello", "text/plain")},
        data={"source_language": "en"},
    )
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_translator_can_access_tools(app):
    """Translators can use tools."""
    client, _ = make_client_with_role(app, UserRole.TRANSLATOR)
    # POST to tools — should not be 403 (may fail on other grounds like missing LLM)
    res = client.post(
        "/api/tools/audit",
        json={
            "source_text": "test",
            "translated_text": "test",
            "target_language": "de",
        },
    )
    assert res.status_code != 403
    app.dependency_overrides.clear()


def test_reviewer_cannot_edit_segments(app):
    """Reviewers lack SEGMENT_EDIT permission."""
    client, _ = make_client_with_role(app, UserRole.REVIEWER)
    res = client.patch(
        "/api/segments/fake-id", json={"translated_text": "edited", "reason": "test"}
    )
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


# --- TMX-RBAC-SWEEP: the newly-gated routers (dashboard / v1.audit / v1.translations) ---

_VALID_JOB = {
    "source_language": "en",
    "target_language": "de",
    "request_id": "rbac-test-1",
    "profile": {
        "archetype": "SAFETY_CRITICAL",
        "tier": "TIER_A",
        "modality": "NARRATIVE",
    },
}


def test_viewer_can_read_swept_reads(app):
    """VIEWER holds the weakest read perms, so the newly-gated reads stay open.

    The guard runs BEFORE the handler, so a passing guard (then a downstream DB
    500) is `!= 403`. `raise_server_exceptions=False` lets that DB error surface
    as a 500 response instead of a raised exception (the operational test DB has
    a stale/dual-layer schema — a pre-existing infra issue, not RBAC).
    """
    make_client_with_role(app, UserRole.VIEWER)  # installs the override on `app`
    client = TestClient(app, raise_server_exceptions=False)
    for path in (
        "/api/dashboard/stats",  # router-level get_current_user
        "/api/v1/audit/fake-id",  # router-level AUDIT_READ
        "/api/v1/translations/",  # DOCUMENT_READ
        "/api/v1/knowledge/rules",  # endpoints.py straggler, KNOWLEDGE_READ
    ):
        res = client.get(path)
        assert res.status_code != 403, f"{path} wrongly 403 for VIEWER"
    app.dependency_overrides.clear()


def test_swept_routes_are_actually_gated(app):
    """Prove every swept route carries a guard chained to get_current_user:
    override it to raise 401 (unauthenticated) and assert the route returns 401
    rather than reaching the handler. This fails if a guard is missing/removed —
    unlike the `!= 403` read test, which can't distinguish allow from no-guard.
    """
    from fastapi import HTTPException

    from app.auth.dependencies import get_current_user

    async def deny_unauthenticated():
        raise HTTPException(status_code=401, detail="no token")

    app.dependency_overrides[get_current_user] = deny_unauthenticated
    client = TestClient(app, raise_server_exceptions=False)
    for path in (
        "/api/dashboard/stats",
        "/api/dashboard/activity",
        "/api/v1/audit/fake-id",  # v1/audit router-level AUDIT_READ
        "/api/v1/audit/verify_v2/org",
        "/api/v1/translations/",
        "/api/v1/translations/fake-id/certificate",
        "/api/v1/knowledge/rules",  # endpoints.py straggler (api_prefix=/api/v1), KNOWLEDGE_READ
    ):
        res = client.get(path)
        assert res.status_code == 401, f"{path} is NOT gated (got {res.status_code})"
    app.dependency_overrides.clear()


def test_swept_reads_are_require_permission_not_just_auth(app, monkeypatch):
    """Positive control: with has_permission forced False, the require_permission
    reads return 403 — proving they carry a real permission guard (not merely
    get_current_user). dashboard is excluded (it's authenticated-read only)."""
    make_client_with_role(app, UserRole.VIEWER)  # valid identity injected
    monkeypatch.setattr(
        "app.auth.dependencies.has_permission", lambda role, perm: False
    )
    client = TestClient(app, raise_server_exceptions=False)
    for path in (
        "/api/v1/audit/fake-id",  # AUDIT_READ
        "/api/v1/translations/",  # DOCUMENT_READ
        "/api/v1/knowledge/rules",  # endpoints.py straggler, KNOWLEDGE_READ
    ):
        res = client.get(path)
        assert (
            res.status_code == 403
        ), f"{path} is not require_permission-gated (got {res.status_code})"
    app.dependency_overrides.clear()


def test_viewer_cannot_use_legacy_translate_verbs(app):
    """The legacy endpoints.py translate verbs now require TRANSLATE_EXECUTE."""
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    res = client.post(
        "/api/v1/translate/quick", json={"text": "hello", "target_language": "de"}
    )
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_viewer_cannot_create_v1_translation_job(app):
    """POST create-job now requires TRANSLATE_EXECUTE — VIEWER is denied."""
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    res = client.post("/api/v1/translations/", json=_VALID_JOB)
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_viewer_cannot_export_certificate(app):
    """The certificate export now requires AUDIT_EXPORT — VIEWER is denied."""
    client, _ = make_client_with_role(app, UserRole.VIEWER)
    res = client.get("/api/v1/translations/fake-id/certificate")
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_translator_can_create_v1_translation_job(app):
    """A role WITH TRANSLATE_EXECUTE passes the guard (may fail downstream, not 403)."""
    make_client_with_role(app, UserRole.TRANSLATOR)  # installs the override on `app`
    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/api/v1/translations/", json=_VALID_JOB)
    assert res.status_code != 403
    app.dependency_overrides.clear()
