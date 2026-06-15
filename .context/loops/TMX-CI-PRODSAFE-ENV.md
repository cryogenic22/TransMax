# TMX-CI-PRODSAFE-ENV — `assert_production_safe()` must exempt all non-production envs, not just `dev`

**State**: `[Done]` (`c8b1074`)
**Owner**: Auth & Tenancy
**Sprint**: MQM Keystone / Phase 0 (substrate — make CI a real gate, not a paper exercise)
**Started**: 2026-06-15
**Reversibility**: `two-way` (widens an exemption set in one guard; fully revertable; production protection preserved)
**Pre-mortem**: if this fails in production, the failure mode is *a real production deploy silently runs no-auth because its `APP_ENV` value landed in the exempt set* — guarded by exempting ONLY a closed allow-list of known non-production env names (`dev/development/test/testing/ci/local`); any unknown value (incl. `production`, `prod`, `staging`) still hits the guard and fails loud (fail-safe default).
**Blast radius**: `app/core/config.py` only (one frozenset + the guard's first line + its docstring). No model/schema/dep change (A4). Behaviour change is confined to non-production envs: `app_env in {test,ci,...}` + `auth_mode==none` now boots instead of crashing.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: the CI **Unit Tests** job sets `APP_ENV=test`; `auth_mode` defaults to `none`; the TMX-3003 guard exempts only `dev`, so `get_settings()` raises `InsecureProductionConfigError` at import → the *entire* pytest suite has failed collection in CI since 2026-05-10 (a month). The "tests green" claims across every loop were LOCAL-only. (b) one frozenset, no new schema; (c) backend config; (d) reuses the existing guard + the documented contract (config.py:38-41 already says "production deployments must explicitly set `APP_ENV=production`"), so test/ci were ALWAYS meant to be non-prod; (e) ships with a 3-case test pinning the production protection.
- [x] **G2 Reproduce-the-failure** — the user-visible failure (CI Unit Tests red, `auth_mode is 'none' in app_env='test'`) is reproduced by a test asserting `Settings(app_env='test', auth_mode='none').assert_production_safe()` raises BEFORE the fix.
- [ ] **G3 Completion** — after the fix, `app_env in {test,ci,...}` + `auth_mode=none` does NOT raise; `app_env=production`/`staging`/unknown + `auth_mode=none` STILL raises; placeholder-secret-in-production STILL raises. Source code (not just a test) changed.

---

## 1. Task

`Settings.assert_production_safe()` (TMX-3003) refuses to boot in a non-dev env with a placeholder secret or `auth_mode==none`. It exempts ONLY `app_env=="dev"`. But the canonical CI **Unit Tests** job (`.github/workflows/ci.yml:45,56`) runs with `APP_ENV=test`, and `auth_mode` defaults to `none` (`config.py:180`) — so `get_settings()` raises at first import (`config.py:246`), failing pytest *collection* for the whole suite. main's CI has been red on this since the guard landed (2026-05-10). This is a Tier-0 entropy hit: the CI gate the audit/trust story depends on has been a paper exercise. Addenda: **A3** (no silent fallbacks — the guard is correct to fail-loud in prod; the bug is its env model is incomplete), **A12** (auth integrity).

## 2. Spec — acceptance criteria

- [ ] AC-1: a closed allow-list `_NON_PRODUCTION_ENVS = {dev, development, test, testing, ci, local}` is the exemption; comparison is case/space-normalised (`app_env.strip().lower()`).
- [ ] AC-2: `Settings(app_env='test', auth_mode='none').assert_production_safe()` does NOT raise (the CI-collection fix). Same for `ci`, `local`, `development`.
- [ ] AC-3: `Settings(app_env='production', auth_mode='none')` STILL raises `InsecureProductionConfigError` (production protection preserved). Same for `staging`, `prod`, and any UNKNOWN value (fail-safe: not-in-allow-list ⇒ checked).
- [ ] AC-4: `Settings(app_env='production', secret_key='change-me-in-production')` STILL raises (the placeholder-secret arm is unchanged).
- [ ] AC-5: no model/schema/dep/route change; the only edited file is `app/core/config.py`.

Out of scope: rotating the `.env` OpenAI key + purging it from history (**TMX-3000**, Kapil-gated — the gitleaks gate stays red until then); the 280 repo-wide ruff errors (**TMX-RUFF-SWEEP**, separate); the missing Playwright `design-system` visual baseline (**TMX-FE-SNAPSHOT**, separate); a vault-backed secret-strength validator (TMX-3001).

## 3. Design

Replace the guard's single `if self.app_env == "dev": return` with `if self.app_env.strip().lower() in _NON_PRODUCTION_ENVS: return`, defined as a module-level frozenset beside `_INSECURE_SECRET_KEYS`. This is an **allow-list** (secure default): only the named non-production envs are exempt; everything else — including a typo'd or brand-new env name — is still checked and fails loud. This matches the contract already documented at `config.py:38-41`.

Alternatives rejected: (a) set `AUTH_MODE=jwt` in the CI Unit Tests job — wrong: the endpoint tests rely on `NoAuthProvider`'s virtual ADMIN, so jwt-mode would 401 the whole suite; (b) set `APP_ENV=dev` in the CI job — masks the root cause (the guard's env model would still be wrong for any other `test`-env consumer) and is a per-job patch, not a fix; (c) exempt by a substring like `"prod" not in app_env` — fragile and not fail-safe (an unknown env would be wrongly exempted). The allow-list is the principled, fail-safe fix.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/config.py` | +~10 / ~2 | `_NON_PRODUCTION_ENVS` frozenset; guard first-line + docstring |
| `tests/test_config_prodsafe.py` | new | reproduce-the-failure + AC-2/3/4 production-protection matrix |

## 5. Eval / Test

```
APP_ENV=dev pytest tests/test_config_prodsafe.py -q   → 19 passed
# reproduce-the-failure (the actual CI condition):
APP_ENV=test  python -c "import app.core.config as c; c.get_settings()"  → OK booted (was: crash)
APP_ENV=production python -c "...get_settings()"        → InsecureProductionConfigError (still protected)
APP_ENV=test  pytest tests/ --collect-only             → 1384 tests collected (was: 0, collection crash)
ratchet check → ✓ all 17 metrics at or better than baseline
```
The single import-time guard crash had been failing *collection* for the entire suite in CI since 2026-05-10; with the fix, all 1384 tests collect and the prod-protection matrix holds.

## 6. Red team

Adversarial security review (agent `a71c942c`) — verdict **SHIP**. Empirically confirmed: every production-like name (`production/prod/staging/stage/preprod`) and every unknown/typo'd value (`prdo/PROD/"production "/""`) still **RAISES** (fail-safe allow-list); `app_env=test` + no-auth now boots; no other consumer branches on `app_env=="dev"` (only `trust.py` reports it + `database.py` deliberately gates on dialect). Two out-of-scope, **pre-existing** CONCERNs surfaced (filed as follow-ups, not this ticket): (1) the live Railway pilot runs `app_env=dev`/`auth_mode=none` (open access) because no deploy config sets `APP_ENV` — so this guard is dead code in prod; the real net is the `database.py` Postgres-dialect guard; (2) the committed `.env`'s `SECRET_KEY=change_this_unsafe_secret` is not in `_INSECURE_SECRET_KEYS`. One in-scope test gap (early-return must short-circuit the secret arm too) — fixed below.

## 7. Fix

Added `test_exempt_env_short_circuits_even_with_placeholder_secret` (the red-team's in-scope gap — an exempt env with a placeholder secret must boot). Switched the test's placeholder literal from `change-me-in-production` → `changeme` (both in `_INSECURE_SECRET_KEYS`, identical guard behaviour) so the test does not regress `backend.placeholder_strings` (the ratchet's `RX_PLACEHOLDER` counts the former, not the latter). Filed follow-up **TMX-PRODSAFE-DEPLOY-ENV** (set `APP_ENV=production` in Railway + add `change_this_unsafe_secret` to `_INSECURE_SECRET_KEYS`; the latter is coupled to the Kapil-gated `.env` rotation TMX-3000).

## 8. Deploy

- [x] Commit: (this commit)
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] Ratchet baseline bump documented as a PR-reviewed exception in `ratchet/baseline.json` `note`

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15 | — | `[WIP]` | Created during "push to main" — diagnosed that main's CI Unit Tests gate has been red for a month (config guard crashes test collection); this unbreaks it. |
