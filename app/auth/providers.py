"""
Auth providers: NoAuth, JWT, and OIDC.

All providers implement the same AuthProvider ABC and produce
an AuthenticatedIdentity, so the rest of the app is provider-agnostic.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from pydantic import BaseModel
from jose import jwt, JWTError, ExpiredSignatureError

from app.auth.permissions import UserRole


class AuthenticatedIdentity(BaseModel):
    """Unified identity object produced by all auth providers."""
    user_id: str
    email: str
    name: str
    role: UserRole
    auth_provider: str  # "none" | "local" | "okta" | "microsoft" | "google"
    is_active: bool = True


class TokenPair(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthProvider(ABC):
    """Abstract base for all auth backends."""

    @abstractmethod
    async def authenticate_token(self, token: Optional[str]) -> Optional[AuthenticatedIdentity]:
        """Validate a Bearer token and return the identity, or None."""
        ...

    @abstractmethod
    async def issue_tokens(self, user_id: str, email: str, name: str, role: UserRole) -> TokenPair:
        """Issue access + refresh tokens for a user."""
        ...


# ---------------------------------------------------------------------------
# NoAuth — dev/demo mode
# ---------------------------------------------------------------------------

class NoAuthProvider(AuthProvider):
    """Returns a virtual admin user regardless of token. Zero friction."""

    _dev_user = AuthenticatedIdentity(
        user_id="dev-admin-00000000",
        email="admin@transmax.local",
        name="Dev Admin",
        role=UserRole.ADMIN,
        auth_provider="none",
    )

    async def authenticate_token(self, token: Optional[str]) -> Optional[AuthenticatedIdentity]:
        return self._dev_user

    async def issue_tokens(self, user_id: str, email: str, name: str, role: UserRole) -> TokenPair:
        return TokenPair(access_token="dev-token", expires_in=999999)


# ---------------------------------------------------------------------------
# JWT — local email/password auth
# ---------------------------------------------------------------------------

class JWTAuthProvider(AuthProvider):
    """Local JWT auth with HS256 signing."""

    def __init__(self, secret_key: str, algorithm: str = "HS256",
                 access_expire_minutes: int = 30, refresh_expire_days: int = 7):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days

    def _decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except (JWTError, ExpiredSignatureError):
            return None

    async def authenticate_token(self, token: Optional[str]) -> Optional[AuthenticatedIdentity]:
        if not token:
            return None
        payload = self._decode_token(token)
        if not payload:
            return None
        try:
            return AuthenticatedIdentity(
                user_id=payload["sub"],
                email=payload["email"],
                name=payload.get("name", ""),
                role=UserRole(payload.get("role", "viewer")),
                auth_provider=payload.get("provider", "local"),
            )
        except (KeyError, ValueError):
            return None

    async def issue_tokens(self, user_id: str, email: str, name: str, role: UserRole) -> TokenPair:
        now = datetime.now(timezone.utc)
        access_payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "role": role.value,
            "provider": "local",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.access_expire_minutes),
        }
        refresh_payload = {
            "sub": user_id,
            "email": email,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self.refresh_expire_days),
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_expire_minutes * 60,
        )

    async def refresh_access_token(self, refresh_token: str) -> Optional[TokenPair]:
        """Validate refresh token and issue new access token."""
        payload = self._decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        # Look up user to get current role/name
        from app.auth.factory import _get_user_by_id
        user = await _get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            return None
        return await self.issue_tokens(
            user_id=str(user.id),
            email=user.email,
            name=user.name,
            role=UserRole(user.role),
        )


# ---------------------------------------------------------------------------
# OIDC — enterprise SSO (Okta, Microsoft Entra, Google Workspace)
# ---------------------------------------------------------------------------

class OIDCAuthProvider(AuthProvider):
    """
    OpenID Connect provider for enterprise SSO.

    Flow:
    1. /authorize → redirect to IdP
    2. /callback → exchange code, validate ID token, provision user, issue local JWT

    The local JWT is used for subsequent API calls (stateless backend).
    """

    def __init__(self, issuer_url: str, client_id: str, client_secret: str,
                 redirect_uri: str, scopes: str = "openid profile email",
                 role_claim: str = "groups", role_mapping: Optional[Dict[str, str]] = None,
                 jwt_secret: str = "", jwt_algorithm: str = "HS256",
                 access_expire_minutes: int = 30):
        self.issuer_url = issuer_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.role_claim = role_claim
        self.role_mapping = role_mapping or {}
        # We issue local JWTs after OIDC validation
        self._jwt = JWTAuthProvider(jwt_secret, jwt_algorithm, access_expire_minutes)
        self._oidc_config: Optional[Dict] = None
        self._jwks: Optional[Any] = None

    async def _get_oidc_config(self) -> Dict:
        """Fetch and cache the .well-known/openid-configuration."""
        if self._oidc_config:
            return self._oidc_config
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.issuer_url}/.well-known/openid-configuration")
            resp.raise_for_status()
            self._oidc_config = resp.json()
        return self._oidc_config

    async def get_authorization_url(self, state: str) -> str:
        """Build the OIDC authorization redirect URL."""
        config = await self._get_oidc_config()
        auth_endpoint = config["authorization_endpoint"]
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{auth_endpoint}?{qs}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        config = await self._get_oidc_config()
        token_endpoint = config["token_endpoint"]
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_endpoint, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            resp.raise_for_status()
            return resp.json()

    async def validate_id_token(self, id_token: str) -> Dict[str, Any]:
        """Validate the OIDC ID token against provider JWKS."""
        config = await self._get_oidc_config()
        jwks_uri = config["jwks_uri"]
        import httpx
        if not self._jwks:
            async with httpx.AsyncClient() as client:
                resp = await client.get(jwks_uri)
                resp.raise_for_status()
                self._jwks = resp.json()
        # Decode without verification first to get header
        header = jwt.get_unverified_header(id_token)
        # Find matching key
        key = None
        for k in self._jwks.get("keys", []):
            if k["kid"] == header.get("kid"):
                key = k
                break
        if not key:
            raise ValueError("No matching JWKS key found")
        claims = jwt.decode(
            id_token, key, algorithms=[header.get("alg", "RS256")],
            audience=self.client_id, issuer=self.issuer_url,
        )
        return claims

    def _map_role(self, claims: Dict[str, Any]) -> UserRole:
        """Map SSO groups/roles to local UserRole."""
        groups = claims.get(self.role_claim, [])
        if isinstance(groups, str):
            groups = [groups]
        for group in groups:
            if group in self.role_mapping:
                try:
                    return UserRole(self.role_mapping[group])
                except ValueError:
                    continue
        # Default: viewer for unknown SSO users
        return UserRole.VIEWER

    async def authenticate_token(self, token: Optional[str]) -> Optional[AuthenticatedIdentity]:
        """After OIDC flow, we use local JWTs — delegate to JWT provider."""
        return await self._jwt.authenticate_token(token)

    async def issue_tokens(self, user_id: str, email: str, name: str, role: UserRole) -> TokenPair:
        return await self._jwt.issue_tokens(user_id, email, name, role)

    async def handle_callback(self, code: str) -> tuple[AuthenticatedIdentity, TokenPair]:
        """
        Full OIDC callback handling:
        1. Exchange code for tokens
        2. Validate ID token
        3. Auto-provision user in DB
        4. Issue local JWT
        """
        token_response = await self.exchange_code(code)
        id_token = token_response["id_token"]
        claims = await self.validate_id_token(id_token)

        sub = claims["sub"]
        email = claims.get("email", "")
        name = claims.get("name", email.split("@")[0])
        role = self._map_role(claims)

        # Auto-provision user
        from app.auth.factory import _provision_sso_user
        user = await _provision_sso_user(
            external_id=sub,
            email=email,
            name=name,
            role=role,
            provider=self._detect_provider(),
        )

        identity = AuthenticatedIdentity(
            user_id=str(user.id),
            email=user.email,
            name=user.name,
            role=UserRole(user.role),
            auth_provider=user.auth_provider,
        )
        tokens = await self.issue_tokens(str(user.id), user.email, user.name, UserRole(user.role))
        return identity, tokens

    def _detect_provider(self) -> str:
        if "okta" in self.issuer_url.lower():
            return "okta"
        if "microsoftonline" in self.issuer_url.lower() or "login.microsoft" in self.issuer_url.lower():
            return "microsoft"
        if "accounts.google" in self.issuer_url.lower():
            return "google"
        return "oidc"
