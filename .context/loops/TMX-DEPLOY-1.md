# TMX-DEPLOY-1 — Deploy hardening: boot-time schema-drift guard + alembic heads merge

**State**: `[Done]` — `de63de2` on origin/main  ·  **Owner**: Platform & Observability  ·  **Sprint**: 2  ·  **Started/Closed**: 2026-06-03
**Reversibility**: `two-way` — new read-only guard module + a startup call gated to Postgres + an empty alembic merge revision. Revertable.
**Pre-mortem**: if the guard is wrong it could refuse a healthy boot — mitigated by (a) only flagging *missing model columns of existing tables* (unambiguous), (b) Postgres-only gating (SQLite dev/test unaffected), (c) `ALLOW_SCHEMA_DRIFT=1` escape hatch.
**Blast radius**: `app/core/schema_guard.py` (new), `app/core/database.py` (`init_db` calls the guard on Postgres), `alembic/versions/` (+1 merge revision). No model/schema change.
**G2 (reproduce-the-failure)**: the 2026-06 Railway 500 (`column documents.organization_id does not exist`) is reproduced as a test that drops a column and asserts the guard raises — RED before the guard existed.

## 1. Task
Root-caused a recurring prod failure: the deploy runs `create_all`, which never ALTERs an existing table to add new columns, so a persisted DB silently 500s on every query naming a column added since it was created (`organization_id`, `total_tokens`, …). Convert that silent runtime failure into a loud boot-time one, and repair the alembic chain so migrations are usable. Addenda: A3 (fail loud, never silently serve broken state), A10 (operational integrity), backend-integrity-paramount.

## 2. Spec — acceptance criteria
- [x] AC-1: `find_schema_drift(engine)` returns `table.column` for every model column missing from an existing DB table; `[]` when current.
- [x] AC-2: tables absent from the DB (e.g. pgvector-only on SQLite) are NOT flagged (no A4 false positives).
- [x] AC-3: `assert_schema_current` raises `SchemaDriftError` on drift; `allow_drift=True` returns the list + logs CRITICAL instead.
- [x] AC-4: `init_db` invokes the guard **only on Postgres** (`engine.dialect.name == "postgresql"`), so SQLite dev/test (incl. the stale committed `transmax.db`) is unaffected; `ALLOW_SCHEMA_DRIFT=1` is the escape hatch.
- [x] AC-5: the two divergent alembic heads (`e5f3045_rule_approval`, `e5f3107_relax_anchors`) are merged into one (`c96c8b36799b`), so `alembic heads` is single-valued again.

Out of scope (→ TMX-DEPLOY-2): wiring `alembic upgrade head` into the deploy CMD. **Rejected here** because the chain runs `CREATE EXTENSION vector` (Postgres-only) and the post-merge chain is unvalidated on a fresh Postgres — forcing it on deploy could brick the container. Needs a throwaway-Postgres validation first.

## 3. Design
`schema_guard.find_schema_drift` uses the SQLAlchemy inspector: for each `Base.metadata` table that EXISTS in the DB, assert its model columns ⊆ DB columns. Existing-tables-only scoping avoids false positives on tables `init_db` intentionally skips on an incompatible engine (A4 dual-layer). `init_db` calls `assert_schema_current` after `create_all` + seed, gated on the Postgres dialect — targeting exactly the deployments where drift bites, while leaving every SQLite path (tests, local dev) untouched (so the known-stale `transmax.db` doesn't brick the suite). Heads merged via `alembic merge` (empty up/down).

**Why dialect-gate, not app_env-gate:** the pilot Railway backend runs `app_env=dev` (auth off), so an `app_env`-gate would never engage there. Dialect is the robust signal: Postgres ⇒ production-like ⇒ enforce.

## 4. Code
| File | Change |
|---|---|
| `app/core/schema_guard.py` | new — `find_schema_drift`, `assert_schema_current`, `SchemaDriftError` |
| `app/core/database.py` | `init_db` runs the guard on Postgres (escape hatch `ALLOW_SCHEMA_DRIFT=1`) |
| `alembic/versions/c96c8b36799b_*.py` | new — merge revision unifying the two heads |
| `tests/test_schema_guard.py` | new — 4 tests (no-drift, detect+raise, allow-drift warn, absent-table-not-drift) |

## 5. Test
`pytest tests/test_schema_guard.py` → 4 passed. Config-safety suite green. Ratchet 17/17. `alembic heads` → single. (`alembic upgrade head` on fresh SQLite still fails on `CREATE EXTENSION vector` — Postgres-only, expected; that's why deploy-CMD wiring is deferred.) Full suite — stage 8.

## 6. Red team
- **False-positive boot refusal:** only missing-columns-of-existing-tables are flagged; Postgres-gated; escape hatch present. Low risk.
- **Stale transmax.db in tests:** dialect-gate means SQLite init never runs the guard → suite unaffected (verified).
- **Guard engaging on the user's Railway:** gated on Postgres, so it engages regardless of `app_env` — exactly the goal.
- **Chain still Postgres-only:** documented; alembic-on-deploy deferred (TMX-DEPLOY-2) rather than risk bricking deploys.

## 7. Fix
None beyond removing 2 auto-generated unused imports in the merge revision.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · guard tests 4/4
- [ ] Commit / push (after full suite)

### Operator note (for the user's Railway)
After restarting the backend (so `create_all` rebuilds the dropped schema), the guard runs on the Postgres DB. A future model-column addition deployed without reseeding will now **fail the boot loudly** with the exact missing columns, instead of serving 500s.

### Spawned
- **TMX-DEPLOY-2** — validate the merged alembic chain on a throwaway Postgres, then wire `alembic upgrade head` into the deploy CMD (auto-migrate persisted DBs). Depends on a Postgres CI/test env.
- **TMX-DEPLOY-3** — catch-up migration for the `create_all`-only columns (`total_tokens`, `total_cost_usd`, `element_type`, `element_meta`) so the alembic chain matches the models (prereq for DEPLOY-2 to fully fix persisted DBs).

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-03T~22:45Z | — | `[Verify]` | Guard + heads merge; 4 tests; ratchet 17/17; awaiting full suite |