# TMX-LIFESPAN — Migrate main.py @app.on_event → lifespan protocol

**State**: `[Done — pending SHA record]`
**Owner**: Platform & Observability
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — swap a deprecated startup hook for the lifespan context manager; identical startup behaviour.
**Pre-mortem**: if this fails, app boot breaks (DB not initialised) — caught immediately by any import/health smoke before deploy. Verified with a TestClient health check.
**Blast radius**: `app/main.py` (lifespan handler replaces `@app.on_event("startup")`).

**Gates**: G1 ✅ (stability — `on_event` is deprecated and slated for removal in FastAPI; lifespan is the supported path). G2 ✅ — reproduced as a DeprecationWarning on import. G3 ✅ — `TestClient(app)` boots via lifespan, `/health` returns 200, no `on_event` remains.

## Spec
- AC-1: startup (init_db + conditional auth-table create) runs via an `@asynccontextmanager` lifespan passed to `FastAPI(lifespan=...)`.
- AC-2: no `@app.on_event` remains; importing `app.main` under `-W error::DeprecationWarning` no longer trips the FastAPI on_event deprecation.

## Test
Smoke: `TestClient(app)` boots, `/health`→200 (verified). Covered indirectly by the full API suite (every TestClient test exercises lifespan).

## Deploy
- [x] Commit: `<pending>` (batch B)
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done — pending SHA record]` | lifespan migration; health 200 verified |
