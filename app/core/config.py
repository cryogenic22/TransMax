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

    # Per-job LLM budget (TMX-BUDGET-1). Opt-in: None ⇒ unbounded (no behaviour
    # change). When set, the engine stops spending once a job's accumulated
    # token/cost consumption exceeds the limit — unspent segments are BLOCKED
    # (A3 fail-loud) and a BUDGET_EXCEEDED audit event is recorded (A1).
    max_tokens_per_job: Optional[int] = None
    max_cost_usd_per_job: Optional[float] = None

    # TMX-MQM-5 / ADR-0007: MQM-2.0 engine rollout (strangler-fig).
    #  - `mqm_shadow_enabled` runs the pure MQM engine ALONGSIDE the legacy
    #    deterministic verdict and logs a shadow comparison. It changes NO
    #    verdict — it only collects the distribution diff that review condition
    #    4 requires before any cutover. Safe to leave on (observational).
    #  - `mqm_engine_enabled` is the future cutover flag (default OFF; flipped
    #    per-tenant only after the shadow diff is signed off — TMX-MQM-5b).
    #  - `mqm_default_profile` is the content-type metric profile used until
    #    content→profile resolution lands (TMX-MQM-5c).
    mqm_shadow_enabled: bool = True
    mqm_engine_enabled: bool = False
    mqm_default_profile: str = "smpc_pil"
    # TMX-MQM-4: run the independent judge in SHADOW (an extra LLM call per job
    # that emits §5.7 annotations + a judge-only MQM score to the audit chain,
    # changing no verdict). Default OFF because of the per-job cost; turn on for
    # the pilot tenant to collect judge-vs-gate data before the cutover.
    mqm_judge_shadow_enabled: bool = False
    # TMX-MQM-ENSEMBLE-RUN: run the judge N times in SHADOW and combine with the
    # most-severe + disagreement-escalation aggregator (no averaging). Default
    # OFF (N× the per-job judge cost). `mqm_ensemble_size` is the judge count
    # (>=2). NOTE: with `enable_llm_router` off, all judges share one model — the
    # emitted `single_lineage` flag + inter-judge κ keep that honest (it is
    # self-consistency, not independent corroboration, until routing flips).
    mqm_ensemble_shadow_enabled: bool = False
    mqm_ensemble_size: int = 2

    # TMX-MQM-CAPTURE: when a reviewer overrides an MT segment, feed the change
    # into the learning bridge as a PROPOSED Black-Book candidate (the gold
    # signal for Phase-2 judge calibration). Default on; turn off to avoid the
    # per-override rule-extraction LLM call.
    enable_hitl_learning_capture: bool = True

    # TMX-ORCH-CHECKPOINT (Loop A): the stuck-PROCESSING job sweeper. A worker
    # killed mid-run (deploy/OOM/crash) leaves a Document orphaned in
    # `processing` forever. The sweeper (scripts/stuck_job_sweeper.py) flips such
    # docs to IN_REVIEW with a JOB_SWEPT_STUCK audit event. Default OFF: the
    # script refuses to MUTATE unless this is True (--dry-run previews regardless),
    # so it is safe to schedule before a tenant opts in. Timeout is generous
    # (4× the translate timeout) so a slow-but-alive early-stage job is never swept.
    stuck_job_sweep_enabled: bool = False
    stuck_job_timeout_seconds: int = 1200

    # TMX-QRD-WIRE: enforce authority QRD format rules (date format + mandatory
    # section headers, per app/core/regulatory_profiles.py) in the live gate when
    # a job is tagged with a `regulatory_profile`. Default OFF: it can flip a
    # verdict (a non-standard header → STRUCTURE_ERROR MAJOR → REVIEW_REQUIRED; a
    # wrong date format → FORMATTING_ERROR MINOR → lower confidence band), so a
    # deployment opts in. NB: this is a GLOBAL (process-wide) rollout flag like
    # mqm_engine_enabled — true per-tenant keying is a follow-up. Flag off ⇒ the
    # gate runs ZERO QRD checks (byte-identical).
    enable_qrd_checks: bool = False

    # Feature Flags (Epic 4: Surgical Reality)
    enable_real_pdf_parsing: bool = True  # Enabled for demo
    enable_live_llm_inference: bool = True

    # TMX-PARSE-1 (ADR-0005): pluggable document-parser backend. Default
    # "pypdf" keeps current behaviour; "docling" enables layout/table/reading-
    # order recovery; "azure"/"google" are cloud connectors. The live upload
    # route still calls the legacy PDFService until TMX-PARSE-2 wires the
    # registry behind this flag.
    parser_backend: str = "pypdf"  # pypdf | docling | azure | google
    parser_ocr_enabled: bool = False  # OCR off = fast for born-digital PDFs
    # Export backend (ADR-0006). docx = fidelity round-trip (default, prefer the
    # editable source); pdf_overlay = fitz redact+reinsert for fixed-layout PDFs;
    # pdf_render = Tier-2 re-typeset (not yet built). Flag-gated; default-off path
    # for pdf_overlay until the AGPL (PyMuPDF) licence review lands.
    export_backend: str = "docx"  # docx | pdf_overlay | pdf_render
    # Optional dir of Unicode TTFs the pdf_overlay backend embeds (DejaVu*). Empty
    # = auto-locate (repo-bundled assets, then matplotlib's DejaVu in dev).
    export_font_dir: str = ""
    # Cloud-connector credentials (fail-loud if a cloud backend is selected
    # without these — never a silent fallback to a worse parser, A3).
    azure_docintel_endpoint: str = ""
    azure_docintel_key: str = ""
    google_docai_processor: str = ""  # projects/.../locations/.../processors/...

    # TMX-ROUTER-2: opt-in LLM router. When False (default) every task uses
    # default_gpt_model (current behaviour). When True, get_llm(task, ...)
    # selects a model per task/complexity via app/core/model_registry. Keep OFF
    # until the model registry matches the models the deployment's key can use.
    enable_llm_router: bool = False

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

    # TMX-AUTH-WALL: seed a demo admin at startup so flipping AUTH_MODE=jwt is a
    # config change, not a manual SSH + seed-script run. Off by default; only
    # seeds when ALL of: auth_mode=jwt, seed_demo_admin=true, and a non-empty
    # demo_admin_password (A3 — never seed a blank/guessable-password account).
    seed_demo_admin: bool = False
    demo_admin_email: str = "admin@transmax.local"
    demo_admin_name: str = "TransMax Admin"
    demo_admin_password: str = ""

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
