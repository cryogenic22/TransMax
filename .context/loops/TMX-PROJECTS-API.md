# TMX-PROJECTS-API — project CRUD + membership endpoints

**State**: `[Done]` — pending commit
**Owner**: Reviewer Frontend
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — additive router; no existing endpoint changed (backwards-compatible API additions only).
**Pre-mortem**: a write without permission could mutate another tenant's project → `require_permission(DOCUMENT_CREATE/UPDATE)` + tenant middleware.
**Blast radius**: `app/api/projects.py` (new), `app/main.py` (router registration).

**Gates**: G1 ✅ end-user value — the workspace projects page was mock-only; this gives it a real backend. G2 N/A. G3 ✅ — HTTP contract smoke green.

## Spec
- AC-1: POST/GET/PATCH `/api/projects`; add/remove/list `/api/projects/{id}/documents`; `/{id}/summary`.
- AC-2: writes gated by DOCUMENT_CREATE/UPDATE; reads by authenticated user; 404 on missing project.
- AC-3: tenant-scoped via TenantContextMiddleware.

## Test
`tests/test_projects_api.py` — 4 passed (create/list/get, add+list+filter, metrics, 404).

## Deploy
- [ ] Commit: <sha>
