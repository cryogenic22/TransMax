"""
Tests for auth providers: NoAuth, JWT, and permission matrix.
"""
import pytest
import asyncio
from app.auth.providers import (
    NoAuthProvider, JWTAuthProvider, AuthenticatedIdentity, TokenPair
)
from app.auth.permissions import (
    UserRole, Permission, ROLE_PERMISSIONS, has_permission
)


# --- NoAuthProvider Tests ---

@pytest.mark.asyncio
async def test_noauth_returns_dev_admin():
    provider = NoAuthProvider()
    identity = await provider.authenticate_token(None)
    assert identity is not None
    assert identity.role == UserRole.ADMIN
    assert identity.auth_provider == "none"
    assert identity.email == "admin@transmax.local"


@pytest.mark.asyncio
async def test_noauth_ignores_any_token():
    provider = NoAuthProvider()
    identity = await provider.authenticate_token("random-garbage-token")
    assert identity is not None
    assert identity.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_noauth_issues_dev_token():
    provider = NoAuthProvider()
    tokens = await provider.issue_tokens("x", "x@x.com", "X", UserRole.ADMIN)
    assert tokens.access_token == "dev-token"


# --- JWTAuthProvider Tests ---

@pytest.mark.asyncio
async def test_jwt_roundtrip():
    provider = JWTAuthProvider(secret_key="test-secret-key-12345", access_expire_minutes=5)
    tokens = await provider.issue_tokens(
        user_id="user-123",
        email="test@example.com",
        name="Test User",
        role=UserRole.TRANSLATOR,
    )
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.expires_in == 300  # 5 * 60

    identity = await provider.authenticate_token(tokens.access_token)
    assert identity is not None
    assert identity.user_id == "user-123"
    assert identity.email == "test@example.com"
    assert identity.name == "Test User"
    assert identity.role == UserRole.TRANSLATOR


@pytest.mark.asyncio
async def test_jwt_invalid_token_returns_none():
    provider = JWTAuthProvider(secret_key="test-secret-key-12345")
    identity = await provider.authenticate_token("invalid.jwt.token")
    assert identity is None


@pytest.mark.asyncio
async def test_jwt_none_token_returns_none():
    provider = JWTAuthProvider(secret_key="test-secret-key-12345")
    identity = await provider.authenticate_token(None)
    assert identity is None


@pytest.mark.asyncio
async def test_jwt_wrong_secret_returns_none():
    provider1 = JWTAuthProvider(secret_key="secret-a")
    provider2 = JWTAuthProvider(secret_key="secret-b")
    tokens = await provider1.issue_tokens("u1", "a@b.com", "A", UserRole.VIEWER)
    identity = await provider2.authenticate_token(tokens.access_token)
    assert identity is None


# --- Permission Matrix Tests ---

def test_admin_has_all_permissions():
    for perm in Permission:
        assert has_permission(UserRole.ADMIN, perm), f"Admin missing {perm}"


def test_viewer_can_read():
    assert has_permission(UserRole.VIEWER, Permission.DOCUMENT_READ)
    assert has_permission(UserRole.VIEWER, Permission.SEGMENT_READ)
    assert has_permission(UserRole.VIEWER, Permission.AUDIT_READ)


def test_viewer_cannot_write():
    assert not has_permission(UserRole.VIEWER, Permission.DOCUMENT_CREATE)
    assert not has_permission(UserRole.VIEWER, Permission.SEGMENT_EDIT)
    assert not has_permission(UserRole.VIEWER, Permission.USERS_MANAGE)


def test_translator_can_translate():
    assert has_permission(UserRole.TRANSLATOR, Permission.TRANSLATE_EXECUTE)
    assert has_permission(UserRole.TRANSLATOR, Permission.SEGMENT_EDIT)
    assert has_permission(UserRole.TRANSLATOR, Permission.DOCUMENT_CREATE)


def test_translator_cannot_approve():
    assert not has_permission(UserRole.TRANSLATOR, Permission.REVIEW_APPROVE)


def test_reviewer_can_approve():
    assert has_permission(UserRole.REVIEWER, Permission.REVIEW_APPROVE)
    assert has_permission(UserRole.REVIEWER, Permission.REVIEW_REJECT)


def test_reviewer_cannot_edit_segments():
    assert not has_permission(UserRole.REVIEWER, Permission.SEGMENT_EDIT)


def test_curator_can_manage_knowledge():
    assert has_permission(UserRole.CURATOR, Permission.KNOWLEDGE_MANAGE)
    assert not has_permission(UserRole.CURATOR, Permission.USERS_MANAGE)


def test_project_manager_broad_access():
    pm = UserRole.PROJECT_MANAGER
    assert has_permission(pm, Permission.DOCUMENT_CREATE)
    assert has_permission(pm, Permission.TRANSLATE_EXECUTE)
    assert has_permission(pm, Permission.REVIEW_APPROVE)
    assert has_permission(pm, Permission.KNOWLEDGE_MANAGE)
    assert not has_permission(pm, Permission.USERS_MANAGE)
    assert not has_permission(pm, Permission.SYSTEM_ADMIN)


def test_all_roles_have_permissions_defined():
    for role in UserRole:
        assert role in ROLE_PERMISSIONS, f"Missing permissions for {role}"
