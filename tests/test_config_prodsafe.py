"""TMX-CI-PRODSAFE-ENV — `assert_production_safe()` env-exemption matrix.

The guard (TMX-3003) must boot non-production envs (the CI suite runs with
`APP_ENV=test` + the dev-default `auth_mode="none"`) while STILL refusing a
real production deploy that runs no-auth or a placeholder secret. The bug it
fixes: exempting only `dev` crashed pytest collection for the whole suite in
CI for a month.

These construct `Settings` directly (not via the cached `get_settings()`) so
each case is isolated from the process env / lru_cache.
"""

import pytest

from app.core.config import InsecureProductionConfigError, Settings

# A secret that is NOT in `_INSECURE_SECRET_KEYS`, so the auth_mode arm is what
# we exercise (not the placeholder-secret arm) unless a case opts in.
_REAL_SECRET = "x" * 48


def _settings(**overrides) -> Settings:
    base = {"secret_key": _REAL_SECRET, "auth_mode": "none"}
    base.update(overrides)
    return Settings(**base)


@pytest.mark.parametrize("env", ["test", "ci", "local", "dev", "development", "testing"])
def test_non_production_envs_boot_with_noauth(env):
    # AC-2 / reproduce-the-failure: the CI `APP_ENV=test` + default no-auth combo
    # must NOT raise (this is what had been crashing test collection).
    _settings(app_env=env).assert_production_safe()  # must not raise


@pytest.mark.parametrize("env", ["test", "CI", " Test ", "Development"])
def test_exemption_is_case_and_space_normalised(env):
    # AC-1: normalisation so `APP_ENV=Test`/`CI ` don't slip through to the guard.
    _settings(app_env=env).assert_production_safe()  # must not raise


@pytest.mark.parametrize("env", ["production", "prod", "staging", "stage", "preprod", ""])
def test_production_like_envs_still_reject_noauth(env):
    # AC-3: production protection preserved — any non-allow-listed env (incl.
    # an UNKNOWN value, fail-safe) with auth_mode=none must still fail loud.
    with pytest.raises(InsecureProductionConfigError) as exc:
        _settings(app_env=env).assert_production_safe()
    assert "auth_mode" in str(exc.value)


def test_production_still_rejects_placeholder_secret():
    # AC-4: the placeholder-secret arm is unchanged.
    with pytest.raises(InsecureProductionConfigError) as exc:
        _settings(app_env="production", auth_mode="jwt", secret_key="changeme").assert_production_safe()
    assert "secret_key" in str(exc.value)


def test_unknown_env_is_treated_as_production():
    # AC-3 fail-safe: a typo'd / brand-new env name is NOT exempted.
    with pytest.raises(InsecureProductionConfigError):
        _settings(app_env="prdo").assert_production_safe()


def test_exempt_env_short_circuits_even_with_placeholder_secret():
    # Red-team gap: the early return must short-circuit BOTH arms — an exempt env
    # with a placeholder secret (and no-auth) must boot, exactly as the dev case did.
    _settings(
        app_env="test", auth_mode="none", secret_key="changeme"
    ).assert_production_safe()  # must not raise
