"""
FastAPI dependencies for auth & RBAC.

These are the only things endpoints need to import:
- get_current_user: injects AuthenticatedIdentity
- require_permission(Permission): returns a dep that checks permission
- require_role(*roles): returns a dep that checks role membership
"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.providers import AuthenticatedIdentity
from app.auth.permissions import Permission, UserRole, has_permission
from app.auth.factory import get_auth_provider, _get_auth_mode

# auto_error=False so missing tokens don't crash in no-auth mode
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedIdentity:
    """
    Core auth dependency. Behaviour depends on AUTH_MODE:
    - none: returns dev admin user (no token needed)
    - jwt/oidc: validates Bearer token or raises 401
    """
    provider = get_auth_provider()
    token = credentials.credentials if credentials else None
    identity = await provider.authenticate_token(token)

    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity


def require_permission(permission: Permission) -> Callable:
    """
    Returns a FastAPI dependency that checks if the current user
    has the given permission via their role.

    Usage:
        @router.post("/documents", dependencies=[Depends(require_permission(Permission.DOCUMENT_CREATE))])
        async def create_doc(...): ...

    Or as a param:
        async def create_doc(user: AuthenticatedIdentity = Depends(require_permission(Permission.DOCUMENT_CREATE))): ...
    """
    async def _check(user: AuthenticatedIdentity = Depends(get_current_user)) -> AuthenticatedIdentity:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
        return user
    return _check


def require_role(*roles: UserRole) -> Callable:
    """
    Returns a FastAPI dependency that checks role membership.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    async def _check(user: AuthenticatedIdentity = Depends(get_current_user)) -> AuthenticatedIdentity:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role.value} not authorized. Required: {[r.value for r in roles]}",
            )
        return user
    return _check
