# TMX-OIDC-CSRF — verify the OAuth `state` on the OIDC callback (close the CSRF gap)

**State**: `[Done]`
**Owner**: Auth & Tenancy
**Sprint**: MQM Keystone / Phase 0 (substrate security)
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (additive state verification on an off-by-default path; revertable)
**Pre-mortem**: if this fails in production, the failure mode is *a forged OIDC callback logs a victim into an attacker-chosen identity (login CSRF)* — which is exactly what this loop closes. The fix itself can only fail safe: a missing/mismatched cookie raises 400 BEFORE any code exchange (A3 fail-loud); a legitimate same-origin flow always sets+returns the cookie, so only forged/replayed callbacks are rejected.
**Blast radius**: `app/api/auth.py` only (the two SSO endpoints). No model/schema/dep change (A4). Entirely behind `AUTH_MODE=oidc` (default `none`) — zero effect on the live `none`/`jwt` paths.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: removes a real CSRF failure mode (robustness axis); the `state` is generated + embedded at authorize (providers.py:206) but NEVER verified at callback — only the persist+compare halves are missing; (b) <5 callers; (c) backend; (d) reuses the existing `state=uuid4()` + the `AUTH_MODE=oidc` gate + the SameSite=Lax OAuth-cookie convention the frontend already documents; (e) ships with tests.
- [x] **G2 Reproduce-the-failure** — `test_oidc_callback_mismatched_state_rejected` / `_no_cookie_` / `_no_state_query_` assert the forged callback is rejected 400 AND `handle_callback.assert_not_awaited()` (no code exchange). Red team additionally verified empty-string state and empty cookie both reject (no `empty==empty` bypass).
- [x] **G3 Completion** — `test_oidc_callback_matching_state_proceeds` returns tokens + clears the cookie; mismatch/absence → 400; `test_sso_blocked_in_noauth` + the existing none/jwt paths unchanged.

---

## 1. Task

`OIDCAuthProvider.get_authorization_url(state)` embeds a `state` in the IdP redirect, and `sso_authorize` mints `state=uuid4()` (auth.py:266) — but `sso_callback` (auth.py:271) accepts a `state` query param and **never compares it to anything**; it calls `handle_callback(code)` with only the code. The `state` CSRF round-trip is half-built: issued, never verified. Close it with the standard **cookie double-submit** (the only defense compatible with the frontend's full-page `window.location` navigation to `/authorize`): set the state in a short-lived HttpOnly/SameSite=Lax/Secure cookie at authorize; require + compare it at callback; reject loud on mismatch. Addenda: **A12** (authn/z integrity), **A3** (fail-loud, no silent pass-through), **A1** (structured warning on rejection).

## 2. Spec — acceptance criteria

- [ ] AC-1: `GET /sso/{provider}/authorize` (AUTH_MODE=oidc) sets an HttpOnly, SameSite=Lax, Secure `oidc_state` cookie (path-scoped to `/api/auth/sso`, short max-age) whose value equals the `state` in the authorization URL + the JSON `state`.
- [ ] AC-2: `GET /sso/{provider}/callback` raises HTTP 400 (BEFORE any code exchange — `handle_callback` not invoked) when the `oidc_state` cookie is absent.
- [ ] AC-3: callback raises 400 when the `state` query param is absent (in oidc mode), and when query `state != oidc_state` cookie.
- [ ] AC-4: callback with query `state == oidc_state` cookie proceeds to `handle_callback`, returns tokens, and clears the `oidc_state` cookie.
- [ ] AC-5: fully gated by `AUTH_MODE=oidc` — the `none`/`jwt` paths + `test_sso_blocked_in_noauth` are unchanged (the mode check still fires first, so absent `state` in non-oidc mode is still the existing 400, not a 422). No new dependency, no model change (A4).
- [ ] AC-6: a rejected callback emits a structured WARNING (provider + mismatch flag, no token/PII).

Out of scope: nonce/PKCE (separate hardening); server-side state store (the cookie double-submit is stateless + sufficient); turning OIDC on (that's a Kapil/ops decision — this lands BEFORE any OIDC go-live).

## 3. Design

Cookie double-submit at the HTTP boundary in `auth.py` (the compare lives where the cookie lives → `providers.py`/`handle_callback` stay untouched, blast radius = one source file). `sso_authorize` injects `response: Response`, sets the `oidc_state` cookie, still returns the JSON for back-compat. `sso_callback` injects `response: Response` + `oidc_state: str = Cookie(None)`; after the existing mode/provider gates, it rejects loud (400) if `state` query or the cookie is absent or they differ, BEFORE the code exchange; on success it clears the cookie then proceeds. `state` stays Optional in the signature (validated inside) so the existing `AUTH_MODE=none` mode-check 400 still fires first (a required Query param would 422 before the mode check). `Secure=True` stays (OIDC is prod/HTTPS only) — tests pass the cookie explicitly rather than relying on the http TestClient jar.

Alternatives rejected: (a) required `state` query param — 422s before the mode check, breaking `test_sso_blocked_in_noauth`; validate inside instead; (b) server-side state store — needs shared state, contradicts the stateless-backend design; cookie double-submit is the standard stateless defense; (c) verifying state inside `handle_callback` — the cookie lives at the HTTP layer, so the compare belongs in the endpoint.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/api/auth.py` | ~12 import + 254-295 | `Response`/`Cookie` import + `_OIDC_STATE_COOKIE`; `sso_authorize` sets the cookie; `sso_callback` verifies + clears it (fail-loud) |
| `tests/test_auth_endpoints.py` | +~5 tests | oidc-mode fixture; authorize sets cookie; callback match→proceeds / mismatch→400 / no-cookie→400 / no-state→400 |

## 5. Eval / Test

```
python -m pytest tests/test_auth_endpoints.py -q   # natural single-file order
```
```
12 passed (5 new OIDC-CSRF + existing) — authorize sets the HttpOnly/Secure/
SameSite=Lax oidc_state cookie; callback match→200+tokens / mismatch→400 /
no-cookie→400 / no-state→400, handle_callback not awaited on reject. The 1
failure (test_noauth_documents) is the pre-existing transmax.db schema-staleness
fixture issue, not this loop. Also autofixed 6 pre-existing unused imports in auth.py.
```

## 6. Red team

3-lens adversarial review (workflow `whta73fm1`). OIDC lens verdict **ship**, zero real defects — empirically verified: no empty-string bypass (the `not state or not oidc_state` clauses short-circuit before the equality), the 400 raises BEFORE `handle_callback` (no token exchange on a forged callback), SameSite=Lax is correct for the IdP top-level redirect, the cookie path is an RFC-6265 prefix of the callback, the WARNING log carries no state/code/token/PII, and the none/jwt paths are unchanged. One nit: the success-path `delete_cookie` omitted the Secure/HttpOnly attrs (a non-Secure clear may not overwrite a Secure cookie).

## 7. Fix

`delete_cookie` now passes `httponly=True, secure=True, samesite="lax"` to match the set cookie so the clear reliably overwrites it. (Harmless even before: the IdP code is single-use + `state` is a fresh uuid4 per authorize.) The raw-Cookie-header test stand-in is a deliberate substitute for the HTTPS jar (the Secure attr is asserted at `/authorize`) — coverage limitation, not a defect. Re-ran: green.

## 8. Deploy

- [x] Commit: `e2426eb` (batch w/ TMX-RBAC-SWEEP)
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 5); real CSRF gap in wired OIDC code; cookie double-submit; ships dark behind AUTH_MODE=oidc |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `e2426eb`; red team verified no bypass / no exchange-on-mismatch; delete_cookie attrs matched |
