# TMX-AUTH-WALL — Pilot login wall (AUTH_MODE=jwt) + seeded demo account

**State**: `[Done]` — built behind flag; activation is Kapil's env-var flip
**Owner**: Auth & Tenancy
**Sprint**: 2
**Started**: 2026-06-14
**Closed**: 2026-06-14
**Reversibility**: `one-way` WHEN ENABLED (changes live auth). The CODE is two-way / inert: everything ships default-off; flipping the env vars is the one-way act and is Kapil's to perform.
**Pre-mortem**: if wrong in production, either (a) the wall locks everyone out (no seeded account / wrong creds), or (b) it appears on but a gap lets unauth users through. Mitigated: verified end-to-end; seed is idempotent + refuses blank passwords; guard + API both enforce.
**Blast radius**: `app/core/config.py` (4 settings), `app/core/database.py` (startup seed), `app/api/auth.py` (login bug fix), `frontend/components/WorkspaceShell.tsx` (route guard). No behaviour changes while `auth_mode=none`.

**Gates:** G1 — reuses the existing (already-built) JWT provider/login/RBAC/login-page; net-new is only the seed + route guard + a login bug fix. G2 — the login `DetachedInstanceError` reproduced live (verify script) before the fix. G3 — end-to-end verified: jwt login issues a token, unauth → 401, guard redirects.

---

## 1. Task

The live pilot runs `app_env=dev`, `auth_mode=none` — **open access**. Make the JWT login wall *flip-ready*: setting env vars activates a working login + a seeded demo account, with no manual SSH/seed-script run and no content-flash. The auth machinery (login/register/refresh/JWT/RBAC/login page/token storage/401-redirect) already existed; this closes the activation gaps.

## 2. Spec — acceptance criteria

- [x] AC-1: with `AUTH_MODE=jwt`, `SEED_DEMO_ADMIN=true`, `DEMO_ADMIN_PASSWORD` set, a demo admin is created at startup, idempotently.
- [x] AC-2: A3 — never seed a blank/guessable-password account (flag on + no password → log + skip).
- [x] AC-3: JWT login issues a token; `/me` with it returns the user; wrong password → 401; no token → 401.
- [x] AC-4: the workspace redirects unauthenticated visitors to `/login` BEFORE rendering (no flash), and is a no-op in `auth_mode=none`.
- [x] AC-5: everything default-off — `auth_mode=none` behaviour byte-for-byte unchanged.

Out of scope (hardening backlog, separate tickets): rate-limiting, password reset/email-verify, token revocation/blacklist, MFA, httpOnly server cookies (ADR-0003 / Auth0), login audit events.

## 3. Design

Reuse the built JWT stack. Add: (1) flag-gated `_seed_demo_admin()` in `init_db()` (runs under `org_context(DEFAULT_ORG_ID)`, sets `organization_id` explicitly, hashes the password); (2) a client route guard in `WorkspaceShell` using `useAuth()` — `authRequired = auth_mode in (jwt,oidc)`, redirect when `!loading && authRequired && !isAuthenticated`. Fixed a real latent login bug surfaced by the first live test (see §6).

## 4. Code

| File | Change |
|---|---|
| `app/core/config.py` | `seed_demo_admin` / `demo_admin_email` / `demo_admin_name` / `demo_admin_password` settings |
| `app/core/database.py` | `_seed_demo_admin()` + call in `init_db()` (idempotent, A3 blank-pw guard, org-context) |
| `app/api/auth.py` | login: capture user fields before the last_login update; update by id — fixes `DetachedInstanceError` |
| `frontend/components/WorkspaceShell.tsx` | auth route guard + "Redirecting to sign in…" block render |

## 5. Eval / Test

`tests/test_auth_wall_seed.py` (4): seeds when enabled + idempotent + password hashed; refuses blank password; no-op when not jwt; no-op when flag off. Auth suite 29 green; frontend typecheck + lint clean. End-to-end (`uploads/fidelity_fr_demo/verify_auth_wall.py`, gitignored): config=jwt → login 200 (token) → /me 200 → wrong-pw 401 → no-token 401 → seed idempotent (1 row after 2× init_db).

## 6. Red team

- **Found + fixed a real bug**: `/api/auth/login` re-`add`ed a detached User to a second session to set `last_login_at`; commit expired the attributes, then `issue_tokens(user.id, …)` raised `DetachedInstanceError`. Never hit in prod because live runs `auth_mode=none` (login short-circuits). The wall would have 500'd on first login. Fixed by capturing locals + updating by id.
- Guard fails safe: if `/api/auth/config` is unreachable (`config=null`), `authRequired=false` → renders (API 401-redirect still backstops) rather than hard-locking.
- bcrypt `__about__` warning (passlib 1.7.4 + bcrypt 4.x) is cosmetic — hashing/verify work; pin is a follow-up if it ever surfaces an error.

## 7. Fix

Login detached-instance fix above; no other findings.

## 8. Deploy / ACTIVATION RUNBOOK (Kapil)

Code is inert until these are set on the **backend** Railway service:
```
AUTH_MODE=jwt
SECRET_KEY=<openssl rand -base64 32>      # >=32 random bytes
SEED_DEMO_ADMIN=true
DEMO_ADMIN_EMAIL=pilot@<tenant>           # or keep admin@transmax.local
DEMO_ADMIN_PASSWORD=<strong password>     # required; no default
# APP_ENV stays dev OR set production (production additionally hard-fails on a
# placeholder SECRET_KEY / auth_mode=none — desirable for a real pilot).
```
On boot the backend seeds the demo admin. The frontend auto-detects `auth_mode=jwt` via `/api/auth/config` and gates `/workspace/*` → `/login`. To roll back: unset `AUTH_MODE` (→ none). Additional users: `/api/auth/register` (jwt) or `scripts/seed_users.py`.

- [x] Commit: `fc9e6cf` (code pushed; INERT until the flip)
- [ ] Kapil flips the env vars when ready to close open-access
- [ ] Follow-ups: rate-limit `/login`, token revocation, login audit event, bcrypt pin

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-14 | — | `[Done]` | Built behind flag; login bug fixed; verified e2e; default-off. Awaiting Kapil's env-var flip to activate. |
