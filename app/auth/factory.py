"""
Auth provider factory — singleton that reads AUTH_MODE from config.

Also contains DB helper functions for user provisioning (used by providers).
"""
import json
from typing import Optional
from functools import lru_cache

from app.auth.providers import AuthProvider, NoAuthProvider, JWTAuthProvider, OIDCAuthProvider
from app.auth.permissions import UserRole


def _get_auth_mode() -> str:
    """Read auth_mode from settings, defaulting to 'none'."""
    from app.core.config import settings
    return getattr(settings, "auth_mode", "none")


@lru_cache()
def get_auth_provider() -> AuthProvider:
    """
    Singleton factory — returns the correct provider based on AUTH_MODE.

    - none: NoAuthProvider (dev/demo, zero friction)
    - jwt: JWTAuthProvider (local email/password)
    - oidc: OIDCAuthProvider (enterprise SSO)
    """
    mode = _get_auth_mode()

    if mode == "none":
        return NoAuthProvider()

    from app.core.config import settings

    if mode == "jwt":
        return JWTAuthProvider(
            secret_key=settings.secret_key,
            algorithm=getattr(settings, "auth_jwt_algorithm", "HS256"),
            access_expire_minutes=settings.access_token_expire_minutes,
        )

    if mode == "oidc":
        role_mapping = {}
        raw = getattr(settings, "oidc_role_mapping", None)
        if raw:
            try:
                role_mapping = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return OIDCAuthProvider(
            issuer_url=getattr(settings, "oidc_issuer_url", ""),
            client_id=getattr(settings, "oidc_client_id", ""),
            client_secret=getattr(settings, "oidc_client_secret", ""),
            redirect_uri=getattr(settings, "oidc_redirect_uri", ""),
            scopes=getattr(settings, "oidc_scopes", "openid profile email"),
            role_claim=getattr(settings, "oidc_role_claim", "groups"),
            role_mapping=role_mapping,
            jwt_secret=settings.secret_key,
            jwt_algorithm=getattr(settings, "auth_jwt_algorithm", "HS256"),
            access_expire_minutes=settings.access_token_expire_minutes,
        )

    # Fallback to no-auth for unknown modes
    return NoAuthProvider()


# ---------------------------------------------------------------------------
# DB helpers used by providers (avoids circular imports)
# ---------------------------------------------------------------------------

async def _get_user_by_id(user_id: str):
    """Fetch User model by ID. Returns None if not found or auth module tables don't exist."""
    try:
        from app.core.database import SessionLocal
        from app.models.auth import User
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()
    except Exception:
        return None


async def _get_user_by_email(email: str):
    """Fetch User model by email."""
    try:
        from app.core.database import SessionLocal
        from app.models.auth import User
        db = SessionLocal()
        try:
            return db.query(User).filter(User.email == email).first()
        finally:
            db.close()
    except Exception:
        return None


async def _provision_sso_user(external_id: str, email: str, name: str,
                               role: UserRole, provider: str):
    """Create or update a user from SSO login."""
    from app.core.database import SessionLocal
    from app.models.auth import User
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id, User.auth_provider == provider).first()
        if user:
            user.email = email
            user.name = name
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(user)
            return user
        # Create new user
        from app.models.database import DEFAULT_ORG_ID
        user = User(
            # TMX-3012 will replace with session-context injection (or
            # TMX-3013 onboarding will resolve from the IdP claims).
            organization_id=DEFAULT_ORG_ID,
            email=email,
            name=name,
            role=role.value,
            auth_provider=provider,
            external_id=external_id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()
