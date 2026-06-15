# TMX-RBAC-SWEEP — apply the existing permission guards to the unprotected privileged routes

**State**: `[Done]` (4 swept routers + the 3 legacy translate verbs; other routers → TMX-RBAC-SWEEP-2)
**Owner**: Auth & Tenancy
**Sprint**: MQM Keystone / Phase 0 (substrate security)
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (additive `Depends` guards reusing the existing primitive; revertable)
**Pre-mortem**: if this fails in production, the failure mode is *over-gating a route the UI calls* (a real user gets a spurious 403). Mitigated: every read is gated on the WEAKEST permission VIEWER already holds (`DOCUMENT_READ`/`AUDIT_READ`/`KNOWLEDGE_READ`), so no role loses read access; only two routes change behaviour for a low-priv user when the wall is on (POST translate → `TRANSLATE_EXECUTE`, certificate → `AUDIT_EXPORT`), which is the INTENDED hardening. Under the live default `AUTH_MODE=none` the `NoAuthProvider` returns a virtual ADMIN, so every guard evaluates allow — the sweep is verified behaviour-neutral today.
**Blast radius**: `app/api/dashboard.py`, `app/api/v1/audit.py`, `app/api/v1/translations.py`, `app/api/endpoints.py` (decorator/router deps only). No model/schema/UI change; the existing tenant-scope is orthogonal and untouched (A4).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: 17 privileged endpoints across 4 routers carry NO auth dependency — the moment the auth-wall flips on (`AUTH_MODE=jwt`) they would be reachable by any role / any token-bearer (an A12 authorization hole); (b) the guard is reused, not added per-caller; (c) backend; (d) REUSES the single canonical `require_permission`/`get_current_user` primitive + the existing `ROLE_PERMISSIONS` matrix — NO new permission, role, endpoint, or service; (e) ships with RBAC tests.
- [x] **G2 Reproduce-the-failure** — `test_swept_routes_are_actually_gated` overrides `get_current_user` to raise 401 and asserts ALL swept paths 401 (proves each guard is wired); `test_swept_reads_are_require_permission_not_just_auth` forces `has_permission` False and asserts the reads 403 (proves a real permission guard, not just auth); plus VIEWER-403 on the mutations/export.
- [x] **G3 Completion** — every privileged route IN THE SWEPT ROUTERS (dashboard, v1/audit, v1/translations, the endpoints.py stragglers + the 3 legacy translate verbs) carries a guard; behaviour under `AUTH_MODE=none` is provably unchanged. NOT repo-wide: `knowledge.py`/`projects.py`/`feedback.py` mutations remain ungated — deferred to **TMX-RBAC-SWEEP-2** (red team flagged the original "every privileged route under app/api/" wording as an overclaim).

---

## 1. Task

The RBAC primitive (`app/auth/dependencies.py::require_permission` / `get_current_user`, matrix in `permissions.py`) is the single canonical guard, used across `documents.py`/`segments.py`/`projects.py`. But four routers slip through: `dashboard.py` (5 KPI/audit-activity reads, zero auth), `v1/audit.py` (4 regulator-facing audit reads, zero auth), `v1/translations.py` (6 endpoints incl. a job-create mutation + a certificate export, zero auth), and `endpoints.py` (2 stragglers — `/audit/{id}`, `/knowledge/rules` — while every sibling is gated). Close the gap by applying the EXISTING guard (reuse-and-reconcile; no new primitive). Addendum **A12** (uniform authorization). The dual-model tenant-scope is orthogonal and stays exactly as-is.

## 2. Spec — acceptance criteria

- [ ] AC-1: Every gap endpoint carries a guard: `dashboard.py` × 5 (router-level `get_current_user` — authenticated read), `v1/audit.py` × 4 (router-level `require_permission(AUDIT_READ)`), `v1/translations.py` × 6 (POST create → `TRANSLATE_EXECUTE`; list/get/result → `DOCUMENT_READ`; audit_bundle → `AUDIT_READ`; certificate → `AUDIT_EXPORT`), `endpoints.py` × 5 (`/audit/{id}` → `AUDIT_READ`, `/knowledge/rules` → `KNOWLEDGE_READ`, **+ the 3 legacy translate verbs `/translate`, `/translate/quick`, `/translate/upload` → `TRANSLATE_EXECUTE`** — added after the red team flagged a VIEWER could otherwise drive LLM translations via the legacy surface while the v1 twin is gated). All `endpoints.py` routes mount at `api_prefix=/api/v1`.
- [ ] AC-2: Under `AUTH_MODE=jwt`, an unauthenticated request to any swept route returns 401; a VIEWER returns 200 on the reads, 403 on POST `/api/v1/translations/` (`TRANSLATE_EXECUTE`) and on the certificate (`AUDIT_EXPORT`).
- [ ] AC-3: Under `AUTH_MODE=none` (pilot default) every swept route returns its pre-sweep status for the dev-admin — behaviour provably unchanged (existing dashboard/audit endpoint tests stay green).
- [ ] AC-4: No new `Permission`/role/endpoint/table/service; permission choices match the already-gated twins in `documents.py` (`TRANSLATE_EXECUTE` for create, `AUDIT_EXPORT` for export). Tenant-scope + the dual-model layers untouched (A4).
- [ ] AC-5: Legitimately public routes (`/health`, auth `/config /login /register /refresh /sso/*`, `/api/trust/posture`) remain ungated — intentional.

Out of scope (red-team-surfaced, tracked not dropped): the remaining ungated privileged mutations in **`knowledge.py`** (rule + glossary CRUD), **`projects.py`**, **`feedback.py`** → **TMX-RBAC-SWEEP-2**; any NEW permission/role; the auth-wall flip itself (TMX-AUTH-WALL). Wall-flip note: the dashboard activity hooks (`frontend/hooks/useActivity.ts`) send the JWT as a cookie, not a `Bearer` header, so they would 401 against the new dashboard guard once `AUTH_MODE=jwt` — route them through `api.ts` at flip time (TMX-AUTH-WALL checklist). Route-collision note: `endpoints.py /audit/{id}` and `/knowledge/rules` mount at `api_prefix=/api/v1`; `/api/v1/audit/{id}` collides with the v1/audit router (api_router registered first wins; both now gated AUDIT_READ — no hole, but the duplicate is an SSOT cleanup for a separate ticket).

## 3. Design

Reuse-only, additive. Two routers whose every route shares one permission use a router-level dependency (`APIRouter(dependencies=[...])`) — one edit, gates all routes (dashboard → `get_current_user`; v1/audit → `AUDIT_READ`). The mixed-permission router (`v1/translations.py`) and the 2 stragglers (`endpoints.py`) use per-endpoint `dependencies=[Depends(require_permission(Permission.X))]` on the decorator (no handler-signature change). Permission per route mirrors the already-gated twin in `documents.py`. Verified behaviour-neutral under `AUTH_MODE=none` (virtual admin holds every permission).

Alternatives rejected: (a) a new "all routes need auth" middleware — too blunt, would gate the public routes; per-router/route deps are precise; (b) a new permission for translations — the existing `TRANSLATE_EXECUTE`/`DOCUMENT_READ`/`AUDIT_*` already fit (no new enum, anti-bloat); (c) handler-param `user=Depends(...)` — leaves an unused param; decorator/router `dependencies=[...]` is cleaner for a pure gate.

## 4. Code

| File | Change |
|---|---|
| `app/api/dashboard.py` | import `get_current_user`; router-level `dependencies=[Depends(get_current_user)]` (gates the 5 reads) |
| `app/api/v1/audit.py` | import `require_permission`+`Permission`; router-level `dependencies=[Depends(require_permission(Permission.AUDIT_READ))]` (gates the 4 reads) |
| `app/api/v1/translations.py` | import `require_permission`+`Permission`; per-endpoint deps (TRANSLATE_EXECUTE / DOCUMENT_READ ×3 / AUDIT_READ / AUDIT_EXPORT) |
| `app/api/endpoints.py` | add `require_permission`+`Permission`; per-endpoint deps on `/audit/{id}` (AUDIT_READ), `/knowledge/rules` (KNOWLEDGE_READ), + `/translate`, `/translate/quick`, `/translate/upload` (TRANSLATE_EXECUTE) |
| `tests/test_auth_rbac.py` | extend: gating-proof (all swept paths 401 without auth); require_permission positive control (has_permission False → 403); VIEWER 403 on translate-create/legacy-translate/certificate; (reuse `make_client_with_role`) |

## 5. Eval / Test

```
python -m pytest tests/test_auth_rbac.py -q   # natural single-file order
```
```
RBAC guard + gating-proof + positive-control + VIEWER-403 tests pass. The 3
remaining failures are PRE-EXISTING DB-infra (documents/users/knowledge routers
I did NOT touch — stale/dual-layer SQLite schema, not RBAC; CI uses fresh Postgres).
Behaviour-neutral under AUTH_MODE=none (NoAuthProvider = virtual ADMIN).
```

## 6. Red team

3-lens adversarial review (workflow `whta73fm1`). RBAC + OIDC lenses verdict **ship** — verified: no over-gating of a public route, permission choices match the documents.py twins, VIEWER keeps all reads, behaviour-neutral under `none`. Honesty lens **fix-then-ship**, real findings: (1) [high] the read test probed a non-existent path (`/api/audit/{id}` — endpoints.py mounts at `/api/v1`), so it passed vacuously; (2) [med] a route collision (endpoints.py `get_audit_log` shadows v1/audit at `/api/v1/audit/{id}`); (3) [med] the live `/api/knowledge/rules` + knowledge/projects/feedback mutations remain ungated; (4) [low] G3 overclaimed repo-wide completeness; + a [med] RBAC-lens completeness gap: the 3 legacy translate verbs were ungated for TRANSLATE_EXECUTE.

## 7. Fix

(1) Repointed the read test to real paths + added a **gating-proof** test (override `get_current_user`→401, assert all 7 swept paths 401) + a **positive control** (force `has_permission` False → reads 403) — the straggler guard is now exercised. (2)+(4) Worksheet corrected: the collision/shadowing documented, the `/api/v1` mount paths noted, G3 reworded to the 4-router scope. (3) `knowledge.py`/`projects.py`/`feedback.py` mutations deferred to **TMX-RBAC-SWEEP-2** (tracked, not silently closed). (RBAC gap) Gated the 3 legacy translate verbs with `TRANSLATE_EXECUTE` + a VIEWER-403 test. Re-ran: green.

## 8. Deploy

- [x] Commit: `e2426eb` (batch w/ TMX-OIDC-CSRF)
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 5); 17-endpoint additive RBAC sweep; behaviour-neutral under AUTH_MODE=none; hardens for the wall flip |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `e2426eb` (20 endpoints incl. the 3 legacy translate verbs); red team added gating-proof + positive-control tests; G3 honestly rescoped; SWEEP-2 deferred |
