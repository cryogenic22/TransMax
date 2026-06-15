# TMX-LOGIN-AUDIT — structured audit of login / register / refresh / SSO (success + failure)

**State**: `[Done]`
**Owner**: Auth & Tenancy
**Sprint**: MQM Keystone / Phase 0 (substrate security + audit-by-default)
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (additive structured audit-log lines via one helper; revertable)
**Pre-mortem**: if this fails in production, the failure mode is *a credential leaks into the audit log* — guarded by logging only the actor identifier / attempted email + outcome + provider, NEVER the password or token (A3 — no secret in the log).
**Blast radius**: `app/api/auth.py` only (one `_audit_auth_event` helper + calls at the auth-flow outcome points). No model/schema/dep change (A4). Behaviour-neutral — adds log lines, changes no response or status code.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: login/register/refresh/SSO emit NO audit today — a regulated system must record access events (Part 11 / Annex 11 §3; a failed-login record is the brute-force signal); only role-change is audited (TMX-AUTH-AUDIT); (b) one helper, <5 schemas; (c) backend; (d) reuses the exact TMX-AUTH-AUDIT structured-log pattern (`ACCESS_CHANGE`) — one consistent `AUTH_EVENT` schema, no new sink, no new dep; (e) ships with caplog tests.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield audit-emission; not a bug).
- [x] **G3 Completion** — each auth-flow outcome (login success/failure, register success/failure, refresh success/failure, SSO callback success/failure) emits one structured `AUTH_EVENT` line; the A3 no-secret contract is tested with a real password value; responses unchanged.

---

## 1. Task

The reviewer/compliance surface claims an audit trail, but the auth boundary is a hole: `login`, `register`, `refresh`, and the SSO `callback` record nothing (only `update_user_role` audits, via TMX-AUTH-AUDIT). A pharma CSV team expects access records (who authenticated, when, success/failure, via which provider) — both for Part-11 access control and for security (failed-login = the brute-force signal). Emit one structured `AUTH_EVENT` line per outcome, via a single helper, following the established `ACCESS_CHANGE` structured-log pattern. Addenda: **A1** (audit-by-default), **A12** (auth integrity), **A3** (never log the password/token). The immutable job-less chain remains the deferred follow-up (**TMX-AUTH-AUDIT-CHAIN**, one-way).

## 2. Spec — acceptance criteria

- [ ] AC-1: `_audit_auth_event(action, outcome, *, actor=None, provider=None, detail=None)` emits ONE structured line `AUTH_EVENT action=… outcome=… actor=… provider=… detail=… at=<iso utc>` and never raises (audit must not break the flow, A3 fail-safe for the side-channel).
- [ ] AC-2: `login` emits `action=login outcome=success` (with the resolved actor + provider) on success and `outcome=failure detail=invalid_credentials|account_deactivated` on each failure path — BEFORE the 401/403 is raised. The attempted email is the actor; the password is NEVER logged.
- [ ] AC-3: `register` emits `action=register outcome=success` after the user is created, and `outcome=failure detail=email_already_registered` on the duplicate-registration 409 (a probing/enumeration security signal — added after red team).
- [ ] AC-4: `refresh` emits `action=refresh outcome=success` on success and `outcome=failure detail=invalid_refresh_token` on the invalid path.
- [ ] AC-5: `sso_callback` emits `action=sso_login outcome=success provider=<okta|microsoft|google>` on success and `outcome=failure detail=state_mismatch|exchange_failed` on the CSRF-reject + the exchange-failure paths.
- [ ] AC-6: No password, refresh token, access token, or `code`/`state` value appears in any emitted line (A3). Responses + status codes are byte-identical.

Out of scope: the immutable job-less audit chain (**TMX-AUTH-AUDIT-CHAIN**, one-way); rate-limiting / lockout on failed logins (a separate hardening); refactoring the existing `ACCESS_CHANGE` line (works; leave it).

## 3. Design

One private `_audit_auth_event` helper in `auth.py` wraps `logger.info` with the consistent `AUTH_EVENT` key=value schema (parseable by a log pipeline, same shape as `ACCESS_CHANGE`) and a broad-except so an audit hiccup never breaks auth (A3 — the side-channel is best-effort, the flow is load-bearing). Call it at every outcome point. Behaviour-neutral: it only logs.

Alternatives rejected: (a) emit to the v1/v2 audit chain — both are job-scoped (no job for a login); the job-less chain is one-way + deferred; structured-log is the established two-way interim (TMX-AUTH-AUDIT precedent); (b) a generic FastAPI middleware logging every request — too coarse (no outcome/reason, logs non-auth routes); endpoint-level emission carries the semantic outcome; (c) logging the full request — would leak the password/token (A3).

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/api/auth.py` | +~12 helper + ~8 call sites | `_audit_auth_event` + emits in login (succ/fail×2), register, refresh (succ/fail), sso_callback (succ/fail×2) |
| `tests/test_login_audit.py` | new | caplog: login(none)→success line; SSO success→sso_login line; refresh→line; no password/token in any line |

## 5. Eval / Test

```
python -m pytest tests/test_login_audit.py tests/test_auth_endpoints.py -q
```
```
test_login_audit (helper schema + no-secret + fail-safe; login/refresh none-mode
wiring) + the SSO-success audit assertion in test_auth_endpoints all pass. The 1
failure (test_noauth_documents) is the pre-existing transmax.db schema-staleness
fixture issue, not this loop. ruff clean.
```

## 6. Red team

Single thorough adversarial review (agent `a6d96114`) — verdict **ship**, no critical/high/medium defects. Verified across all 12 call sites: **no secret leak** (actor is always an email/user_id, provider a literal/name, detail a fixed string — no password/token/code/state); the **fail-safe concern is genuinely defended** (every `actor=identity.email` site is a provider that cannot return None — `NoAuthProvider` — or is already `if identity else None`-guarded, so no AttributeError escapes the helper's try/except); behaviour-neutral; worksheet defers the immutable chain honestly. Nits: the register-409 (duplicate-registration) wasn't audited; the A3 test's `"token" not in line` was brittle.

## 7. Fix

Added the `register` 409 failure audit (`detail=email_already_registered` — a probing/enumeration signal). Tightened the A3 test to send a REAL password value and assert it's absent from the audit trail (not a brittle substring). Re-ran: green.

## 8. Deploy

- [x] Commit: `c6ad4bc`
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 6); extends TMX-AUTH-AUDIT structured-log to login/register/refresh/SSO; immutable chain deferred to TMX-AUTH-AUDIT-CHAIN |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `c6ad4bc`; red team verdict ship (no secret leak, fail-safe holds); register-409 audit + A3 real-password test added |
