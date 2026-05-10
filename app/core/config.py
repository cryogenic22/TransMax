"""TransMax application settings.

TMX-3003: `Settings.assert_production_safe()` refuses to start the platform in
any non-dev environment with placeholder credentials or `auth_mode == "none"`.
This is the C-02 + C-03 hardening from the May 2026 review.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class InsecureProductionConfigError(RuntimeError):
    """Raised when `Settings.assert_production_safe()` finds an insecure default
    in a non-dev environment.

    Subclasses `RuntimeError` (not `Exception` directly) so that startup-path
    `except Exception` handlers do not silently swallow it — operators must see
    the misconfiguration in stderr / journald.
    """


# Known placeholder values for `secret_key`. Anything in this set is rejected
# in non-dev environments. Not exhaustive — a determined operator can still
# bypass with `secret_key="foo"`. The goal here is to catch the *defaults*,
# not to be a full secret-strength validator (TMX-3001 vault is the canonical
# answer for that).
_INSECURE_SECRET_KEYS: frozenset[str] = frozenset({
    "",
    "change-me-in-production",
    "changeme",
    "secret",
    "placeholder",
})


class Settings(BaseSettings):
    # Environment mode — drives production-safety guard. Default `dev` so
    # backward-compat with developer machines + CI is preserved; production
    # deployments must explicitly set `APP_ENV=production` (or `staging`).
    app_env: str = "dev"

    # Application
    app_name: str = "Translation Agent Service"
    app_version: str = "1.0.0"
    debug: bool = True

    # API
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # Supabase (optional — only needed if using Supabase as backend)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""
    database_url: str = "sqlite:///./transmax.db"

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # Translation Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None
    google_application_credentials: Optional[str] = None

    # Default Models
    default_gpt_model: str = "gpt-4-turbo-preview"
    default_claude_model: str = "claude-3-opus-20240229"
    default_translation_provider: str = "openai"

    # Translation Settings
    max_chunk_size: int = 4000
    translation_timeout: int = 300
    enable_back_translation: bool = True
    confidence_threshold: float = 0.85

    # Feature Flags (Epic 4: Surgical Reality)
    enable_real_pdf_parsing: bool = True  # Enabled for demo
    enable_live_llm_inference: bool = True

    # Digitization Service
    digitization_service_url: str = "http://localhost:8000/api/v1"

    # Security
    # No default — empty string is itself flagged by `_INSECURE_SECRET_KEYS`,
    # so the platform refuses to start in non-dev unless `SECRET_KEY` comes
    # from the environment / vault. (TMX-3003 / addendum A3.)
    secret_key: str = ""
    access_token_expire_minutes: int = 30

    # Auth — fully optional, defaults to no-auth for dev/demo
    auth_mode: str = "none"  # "none" | "jwt" | "oidc"
    auth_jwt_algorithm: str = "HS256"

    # OIDC / SSO (only needed when auth_mode="oidc")
    oidc_provider: Optional[str] = None       # "okta" | "microsoft" | "google"
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_issuer_url: Optional[str] = None
    oidc_redirect_uri: Optional[str] = None
    oidc_scopes: str = "openid profile email"
    oidc_role_claim: str = "groups"
    oidc_role_mapping: Optional[str] = None   # JSON: {"OktaAdmins": "admin", ...}

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    def assert_production_safe(self) -> None:
        """Refuse to run in non-dev with placeholder credentials.

        TMX-3003 / addendum A3 (no silent fallbacks in regulated paths).

        Raises:
            InsecureProductionConfigError: when `app_env != "dev"` AND either
                `secret_key` is a known placeholder or `auth_mode == "none"`.
                The error message names the failing setting and gives a one-
                line remediation hint, so the startup log is self-explanatory.
        """
        if self.app_env == "dev":
            return

        if self.secret_key in _INSECURE_SECRET_KEYS:
            raise InsecureProductionConfigError(
                f"secret_key is a placeholder ({self.secret_key!r}) in "
                f"app_env={self.app_env!r}. Set SECRET_KEY to a vault-issued "
                f"value (>= 32 random bytes) before starting the platform."
            )

        if self.auth_mode == "none":
            raise InsecureProductionConfigError(
                f"auth_mode is 'none' in app_env={self.app_env!r}. Set "
                f"AUTH_MODE to 'jwt' or 'oidc' before starting the platform — "
                f"no-auth is a dev-only mode."
            )


@lru_cache()
def get_settings() -> Settings:
    """Return the process-wide `Settings` singleton, refusing to construct one
    that would be unsafe in production.

    The lru_cache means `assert_production_safe()` runs once per process; the
    crash, if it happens, fires at first import in any non-dev deployment.
    """
    instance = Settings()
    instance.assert_production_safe()
    return instance


settings = get_settings()
