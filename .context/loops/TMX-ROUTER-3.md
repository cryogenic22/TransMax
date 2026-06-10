# TMX-ROUTER-3 — Per-tenant routing policy (table + audited CRUD)

**State**: `[Done]` — `1cd4ab2` on origin/main  ·  **Owner**: Agent & AI + Auth  ·  **Sprint**: 2  ·  Loop 7/10 (2026-06-04 batch)
**Reversibility**: `two-way` — new table (created by create_all + a catch-up migration in DEPLOY-3) + service + a pure `select_model` override param. No-op until a policy is created AND routing is on.
**Blast radius**: `app/models/database.py` (+`RoutingPolicy`), `app/auth/permissions.py` (+`ROUTING_CONFIGURE`), `app/services/routing_policy_service.py` (new), `app/core/model_registry.py` (`select_model` override param), `app/services/llm.py` (`resolve_model` reads tenant overrides best-effort).

## 1. Task
Persist a per-tenant routing-policy override so models can be configured on the fly (the storage layer behind the CONFIG-API + UI). RBAC-gated, validated, audit-stamped. Addenda: A1 (record who/when + audit log), A3 (reject malformed overrides — never route to nowhere), config-not-branching, multi-tenant.

## 2. Spec
- [x] AC-1: `RoutingPolicy` table — one row per org (`organization_id` unique), `overrides` JSON, `enabled` bool, `updated_by`/`updated_at`.
- [x] AC-2: `validate_overrides` rejects bad keys (`task:complexity`) and bad tier names (A3).
- [x] AC-3: `upsert_policy` requires `ROUTING_CONFIGURE` (PermissionError otherwise); stamps `updated_by`; audit-logs before mutation.
- [x] AC-4: `get_policy_overrides` returns the overrides only when `enabled`; `{}` otherwise.
- [x] AC-5: `select_model(..., policy_overrides=…)` overlays the default policy; invalid overrides ignored.
- [x] AC-6: `resolve_model` reads the current tenant's overrides best-effort (errors / no-context → `{}`), so a missing table or absent tenant never breaks model resolution.

Out of scope: REST (CONFIG-API loop 8), UI (loop 9), the alembic migration for the table (DEPLOY-3 loop 10 — create_all handles fresh DBs meanwhile), chained system-audit (TMX-ROUTER-3a), per-call caching (TMX-ROUTER-3b).

## 3. Design
`RoutingPolicy` keyed by org. `routing_policy_service` provides `validate_overrides` (pure), `get_policy_overrides`, `get_policy`, `upsert_policy` (RBAC + validate + audit-log-before-mutate + upsert) — mirrors the TMX-3045 `rule_promotion` audited-service shape. `select_model` gains a pure `policy_overrides` param ("task:complexity" → tier) overlaying `_POLICY`. `resolve_model` fetches the tenant overrides best-effort (try/except → `{}`).

**Audit note:** routing-config changes aren't job-scoped, so the job-scoped v1/v2 chains don't fit; recorded via `updated_by`/`updated_at` + a structured log. Chained system-audit deferred (TMX-ROUTER-3a).

## 4. Code
| File | Change |
|---|---|
| `app/models/database.py` | +`RoutingPolicy` model |
| `app/auth/permissions.py` | +`ROUTING_CONFIGURE` (ADMIN auto; +PROJECT_MANAGER) |
| `app/services/routing_policy_service.py` | new — validate / get / upsert (RBAC + audit) |
| `app/core/model_registry.py` | `select_model` `policy_overrides` overlay |
| `app/services/llm.py` | `resolve_model` reads tenant overrides via `_tenant_policy_overrides` |
| `tests/test_routing_policy.py` | new — 8 tests (validation, RBAC, round-trip, override, no-row) |

## 5. Test
`pytest routing_policy + router-wire + model_registry` → 22 passed. Ratchet 17/17. Full suite — stage 8. (Pre-existing ruff F401/F811 in database.py's legacy re-exports + `Enum` alias are not from this loop and not ratchet-tracked.)

## 6. Red team
- `resolve_model` policy read is best-effort (swallow) — a missing `routing_policies` table on a stale DB or no tenant context can't break model resolution (verified: router-on tests with no org context still route off the default policy).
- Malformed overrides rejected at write time (A3) — can't persist a policy that routes to a non-existent tier.
- RBAC enforced before validation; only ADMIN/PM may write.
- Per-call DB read when routing on — acceptable for opt-in v1; caching → TMX-ROUTER-3b.

## 7. Fix
**Full-suite caught a real invariant violation:** `test_every_tenant_scoped_table_has_soft_delete_columns` failed — `RoutingPolicy` has `organization_id` (tenant-scoped) so the A9 invariant requires the soft-delete columns. Fixed by inheriting `SoftDeleteMixin` (mirroring `Organization`); kept `TenantScopedMixin` OFF deliberately (the service scopes by explicit `organization_id` and must not require an ambient tenant context, which would break the upsert/query path). Re-ran soft-delete + routing tests: 14/14. (Pre-existing database.py re-export ruff lint left untouched — intentional legacy re-exports.)

## 8. Deploy
- [x] Ratchet 17/17 · 22 tests · added-code ruff-clean
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-ROUTER-3a** — chained system-audit for routing-config changes (needs a job-less audit trail).
- **TMX-ROUTER-3b** — cache the per-tenant policy to avoid a DB read per LLM call.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~02:40Z | — | `[Verify]` | table + service + RBAC + select_model overlay + resolve_model read; 8 tests; ratchet 17/17; awaiting full suite |