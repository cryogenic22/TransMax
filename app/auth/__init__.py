"""
TransMax Auth Module - Fully detachable authentication & RBAC.

This module is designed as an optional plugin:
- AUTH_MODE=none (default): Zero auth, virtual admin user, no DB tables created
- AUTH_MODE=jwt: Local email/password auth with JWT tokens
- AUTH_MODE=oidc: Enterprise SSO via OpenID Connect (Okta, Microsoft Entra, Google)

All three modes produce the same AuthenticatedIdentity, so the rest of the app
doesn't care which mode is active.
"""
from app.auth.permissions import UserRole, Permission, ROLE_PERMISSIONS, has_permission
from app.auth.dependencies import get_current_user, require_permission, require_role

__all__ = [
    "UserRole",
    "Permission",
    "ROLE_PERMISSIONS",
    "has_permission",
    "get_current_user",
    "require_permission",
    "require_role",
]
