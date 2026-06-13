"""
TransMax Auth API Router.

Endpoints for login, registration, SSO, user management.
All endpoints are aware of AUTH_MODE and behave accordingly.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.providers import AuthenticatedIdentity, TokenPair
from app.auth.permissions import UserRole, Permission
from app.auth.dependencies import get_current_user, require_permission, require_role
from app.auth.factory import get_auth_provider, _get_auth_mode, _get_user_by_email
from app.auth.password import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# --- Request/Response Schemas ---

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: Optional[str] = None  # Admin can set role; otherwise defaults to viewer

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    auth_provider: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

class RoleUpdateRequest(BaseModel):
    role: str

class AuthConfigResponse(BaseModel):
    auth_mode: str
    sso_providers: List[str]
    registration_enabled: bool


# --- Public Endpoints ---

@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config():
    """Public endpoint — returns auth configuration for frontend."""
    mode = _get_auth_mode()
    sso_providers = []
    if mode == "oidc":
        from app.core.config import settings
        provider = getattr(settings, "oidc_provider", None)
        if provider:
            sso_providers = [provider]
    return AuthConfigResponse(
        auth_mode=mode,
        sso_providers=sso_providers,
        registration_enabled=(mode == "jwt"),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Local JWT login. Only available when AUTH_MODE=jwt."""
    mode = _get_auth_mode()
    if mode == "none":
        # In no-auth mode, return a dev token
        provider = get_auth_provider()
        identity = await provider.authenticate_token(None)
        tokens = await provider.issue_tokens(identity.user_id, identity.email, identity.name, identity.role)
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user=identity.model_dump(),
        )

    if mode != "jwt":
        raise HTTPException(status_code=400, detail="Login endpoint not available in OIDC mode. Use SSO.")

    user = await _get_user_by_email(request.email)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # _get_user_by_email returns a DETACHED instance; capture the fields now,
    # while the loaded attributes are still cached, BEFORE touching another
    # session (a second-session add+commit would expire them and the later
    # issue_tokens access would raise DetachedInstanceError).
    user_id, user_email = str(user.id), user.email
    user_name, user_role = user.name, user.role
    user_provider, user_active = user.auth_provider, user.is_active

    # Update last_login by id — no reliance on the detached instance.
    from app.core.database import SessionLocal
    from app.models.auth import User
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == user_id).update(
            {"last_login_at": datetime.now(timezone.utc)}
        )
        db.commit()
    finally:
        db.close()

    provider = get_auth_provider()
    tokens = await provider.issue_tokens(user_id, user_email, user_name, UserRole(user_role))
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user={
            "user_id": user_id,
            "email": user_email,
            "name": user_name,
            "role": user_role,
            "auth_provider": user_provider,
            "is_active": user_active,
        },
    )


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new local user. Only available when AUTH_MODE=jwt."""
    mode = _get_auth_mode()
    if mode != "jwt":
        raise HTTPException(status_code=400, detail="Registration only available in JWT mode")

    existing = await _get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    from app.core.database import SessionLocal
    from app.models.auth import User

    role = request.role if request.role and request.role in [r.value for r in UserRole] else UserRole.VIEWER.value

    db = SessionLocal()
    try:
        # TMX-3012c: organization_id auto-injected from request-scoped tenant
        # context. TMX-3013 will resolve org from IdP claims.
        user = User(
            email=request.email,
            name=request.name,
            hashed_password=hash_password(request.password),
            role=role,
            auth_provider="local",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    provider = get_auth_provider()
    tokens = await provider.issue_tokens(str(user.id), user.email, user.name, UserRole(user.role))
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user={
            "user_id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "auth_provider": user.auth_provider,
            "is_active": user.is_active,
        },
    )


@router.get("/me")
async def get_current_user_info(user: AuthenticatedIdentity = Depends(get_current_user)):
    """Get the current authenticated user's info."""
    return user.model_dump()


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh an access token using a refresh token."""
    mode = _get_auth_mode()
    if mode == "none":
        provider = get_auth_provider()
        identity = await provider.authenticate_token(None)
        tokens = await provider.issue_tokens(identity.user_id, identity.email, identity.name, identity.role)
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user=identity.model_dump(),
        )

    provider = get_auth_provider()
    from app.auth.providers import JWTAuthProvider
    if not isinstance(provider, JWTAuthProvider):
        # OIDC uses JWT internally
        from app.auth.providers import OIDCAuthProvider
        if isinstance(provider, OIDCAuthProvider):
            provider = provider._jwt
        else:
            raise HTTPException(status_code=400, detail="Token refresh not supported in this mode")

    tokens = await provider.refresh_access_token(request.refresh_token)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Get user info for response
    identity = await provider.authenticate_token(tokens.access_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=identity.model_dump() if identity else {},
    )


# --- SSO Endpoints ---

@router.get("/sso/{provider}/authorize")
async def sso_authorize(provider: str):
    """Redirect to SSO provider's authorization page."""
    mode = _get_auth_mode()
    if mode != "oidc":
        raise HTTPException(status_code=400, detail="SSO not enabled. Set AUTH_MODE=oidc")

    auth_provider = get_auth_provider()
    from app.auth.providers import OIDCAuthProvider
    if not isinstance(auth_provider, OIDCAuthProvider):
        raise HTTPException(status_code=500, detail="OIDC provider not configured")

    state = str(uuid.uuid4())
    url = await auth_provider.get_authorization_url(state)
    return {"authorization_url": url, "state": state}


@router.get("/sso/{provider}/callback")
async def sso_callback(provider: str, code: str, state: Optional[str] = None):
    """OIDC callback — exchange code, provision user, return tokens."""
    mode = _get_auth_mode()
    if mode != "oidc":
        raise HTTPException(status_code=400, detail="SSO not enabled")

    auth_provider = get_auth_provider()
    from app.auth.providers import OIDCAuthProvider
    if not isinstance(auth_provider, OIDCAuthProvider):
        raise HTTPException(status_code=500, detail="OIDC provider not configured")

    try:
        identity, tokens = await auth_provider.handle_callback(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SSO authentication failed: {str(e)}")

    # Return tokens — frontend will store them
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=identity.model_dump(),
    )


# --- Admin: User Management ---

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    user: AuthenticatedIdentity = Depends(require_permission(Permission.USERS_READ)),
):
    """List all users. Requires USERS_READ permission."""
    mode = _get_auth_mode()
    if mode == "none":
        return []

    from app.core.database import SessionLocal
    from app.models.auth import User

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return [
            UserResponse(
                id=str(u.id), email=u.email, name=u.name, role=u.role,
                auth_provider=u.auth_provider, is_active=u.is_active,
                created_at=u.created_at, last_login_at=u.last_login_at,
            )
            for u in users
        ]
    finally:
        db.close()


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: RoleUpdateRequest,
    user: AuthenticatedIdentity = Depends(require_permission(Permission.USERS_MANAGE)),
):
    """Change a user's role. Requires USERS_MANAGE permission."""
    mode = _get_auth_mode()
    if mode == "none":
        raise HTTPException(status_code=400, detail="User management not available in no-auth mode")

    if request.role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")

    from app.core.database import SessionLocal
    from app.models.auth import User

    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        target.role = request.role
        target.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"message": f"User {target.email} role updated to {request.role}"}
    finally:
        db.close()
