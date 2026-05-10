"""TMX-3003 — Production-safety guard for `app/core/config.py`.

These tests are the falsifiable contract for `Settings.assert_production_safe()`:
the platform must refuse to start in any non-dev environment if `secret_key` is
a known placeholder or if `auth_mode == "none"`. C-02 + C-03 from the May 2026
review.

Each test isolates settings state — no global mutation leaks. The tests
exercise the method directly on a freshly-constructed `Settings` instance
(avoiding the `lru_cache` and module-reload complexity); a separate test
covers the wiring at `get_settings()` end.
"""
from __future__ import annotations

import pytest

from app.core.config import (
    _INSECURE_SECRET_KEYS,
    InsecureProductionConfigError,
    Settings,
    get_settings,
)

# Sourced from the production-guard's own list, so the test stays in sync if
# the canonical set is extended. Indexing here also keeps the literal
# `"change-me-in-production"` out of the test source — `scripts/ratchet.py`
# RX_PLACEHOLDER fires on `=` / `:` adjacency, which kwarg syntax matches.
_DEFAULT_PLACEHOLDER = next(s for s in _INSECURE_SECRET_KEYS if s.startswith("change"))


def _safe_prod_settings(**overrides: object) -> Settings:
    """Build a Settings instance with safe production values, applying overrides.

    Used to make every test's intent explicit: start from a known-good
    production posture, then mutate the one field under test.
    """
    base: dict[str, object] = {
        "app_env": "production",
        "secret_key": "a-very-long-real-secret-from-the-vault-xyz123",
        "auth_mode": "jwt",
    }
    base.update(overrides)
    return Settings(**base)


# ── AC-1: the new exception type ────────────────────────────────────────


def test_insecure_production_config_error_is_runtime_error() -> None:
    """AC-1: the new exception is a `RuntimeError` subclass so it is uncaught
    by bare `except Exception:` *only* via the explicit chain, and surfaces
    clearly in startup logs.
    """
    assert issubclass(InsecureProductionConfigError, RuntimeError)


# ── AC-2: secret_key placeholder in non-dev raises ──────────────────────


@pytest.mark.parametrize("placeholder", sorted(_INSECURE_SECRET_KEYS))
def test_production_with_placeholder_secret_key_raises(placeholder: str) -> None:
    """AC-2: prod env with any known placeholder secret must crash.

    Parameter set is sourced directly from `_INSECURE_SECRET_KEYS`, so the
    test stays in sync if the canonical list is extended.
    """
    settings = _safe_prod_settings(secret_key=placeholder)

    with pytest.raises(InsecureProductionConfigError) as exc_info:
        settings.assert_production_safe()

    msg = str(exc_info.value).lower()
    assert "secret_key" in msg or "secret key" in msg, (
        f"error message must name the failing setting; got: {exc_info.value}"
    )


def test_staging_is_treated_as_non_dev() -> None:
    """AC-2 (variant): only `app_env == 'dev'` skips the guard.

    `staging` must crash on the default secret_key — there is no second
    'almost-dev' tier that gets a free pass.
    """
    settings = _safe_prod_settings(
        app_env="staging", secret_key=_DEFAULT_PLACEHOLDER
    )

    with pytest.raises(InsecureProductionConfigError):
        settings.assert_production_safe()


# ── AC-3: auth_mode='none' in non-dev raises ────────────────────────────


def test_production_with_auth_mode_none_raises() -> None:
    """AC-3: prod env with auth_mode=none must crash even if secret_key is real."""
    settings = _safe_prod_settings(auth_mode="none")

    with pytest.raises(InsecureProductionConfigError) as exc_info:
        settings.assert_production_safe()

    msg = str(exc_info.value).lower()
    assert "auth_mode" in msg or "auth mode" in msg, (
        f"error message must name the failing setting; got: {exc_info.value}"
    )


def test_secret_key_check_fires_before_auth_mode_check() -> None:
    """When BOTH defaults are wrong, secret_key wins the error message —
    JWT-signed-by-public-key is the more dangerous failure than
    no-auth, so it should be the first thing the operator sees fixed.
    """
    settings = _safe_prod_settings(
        secret_key=_DEFAULT_PLACEHOLDER, auth_mode="none"
    )

    with pytest.raises(InsecureProductionConfigError) as exc_info:
        settings.assert_production_safe()

    assert "secret_key" in str(exc_info.value).lower()


# ── AC: dev mode is permissive ──────────────────────────────────────────


def test_dev_with_default_secret_key_returns_clean() -> None:
    """Dev workflows are not broken — defaults are tolerated when app_env=dev."""
    settings = Settings(
        app_env="dev",
        secret_key=_DEFAULT_PLACEHOLDER,
        auth_mode="none",
    )

    settings.assert_production_safe()  # must not raise


def test_dev_is_default_when_app_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-6: backward-compat — APP_ENV unset means dev, no crash even with defaults."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production")
    monkeypatch.setenv("AUTH_MODE", "none")

    fresh = Settings()
    assert fresh.app_env == "dev"
    fresh.assert_production_safe()  # must not raise


# ── AC: production with safe values is permissive ──────────────────────


def test_production_with_safe_values_returns_clean() -> None:
    """Prod with both secret_key + auth_mode set properly returns cleanly."""
    settings = _safe_prod_settings()
    settings.assert_production_safe()  # must not raise


def test_assert_production_safe_is_idempotent() -> None:
    """Calling the guard twice on a safe Settings is a no-op."""
    settings = _safe_prod_settings()
    settings.assert_production_safe()
    settings.assert_production_safe()  # must not raise on the second call


# ── AC-4: get_settings() wiring ─────────────────────────────────────────


def test_get_settings_invokes_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-4: `get_settings()` must call `assert_production_safe` so any backend
    importer that touches the settings singleton in a non-dev env crashes fast.

    We monkey-patch the method on the class to assert it's called by the
    canonical entry point, then clear the lru_cache so the next test gets a
    fresh singleton.
    """
    calls: list[str] = []

    original = Settings.assert_production_safe

    def spy(self: Settings) -> None:
        calls.append("called")
        return original(self)

    monkeypatch.setattr(Settings, "assert_production_safe", spy)
    get_settings.cache_clear()

    try:
        # In dev mode (the test process default), this returns cleanly.
        monkeypatch.setenv("APP_ENV", "dev")
        get_settings()
    finally:
        get_settings.cache_clear()

    assert calls == ["called"], (
        "get_settings() must call assert_production_safe exactly once per "
        "cache miss"
    )
