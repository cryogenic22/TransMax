# TMX-JOBS-FILTER — richer job query + metrics endpoint

**State**: `[Done]` — pending commit
**Owner**: Reviewer Frontend / Platform
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — additive query params + new read-only endpoint; omitting params preserves prior behaviour.
**Pre-mortem**: a filter could leak cross-tenant jobs → all queries run under the tenant auto-filter.
**Blast radius**: `app/api/documents.py` (`list_documents` params + `/metrics`).

**Gates**: G1 ✅ end-user value — "manage all jobs properly": filter by target language + project, and a status/language metrics roll-up for the dashboard. G2 N/A. G3 ✅ — covered by the projects-API smoke (`project_id` filter + metrics shape).

## Spec
- AC-1: `GET /api/documents?target_language=&project_id=` filters jobs (backward-compatible).
- AC-2: `GET /api/documents/metrics` returns `{total, by_status, by_target_language}` in one tenant-scoped pass.
- AC-3: `/metrics` declared before `/{doc_id}` so it is not shadowed.

## Test
`tests/test_projects_api.py::test_metrics_endpoint_shape` + `::test_add_and_list_documents_and_filter`.

## Deploy
- [ ] Commit: <sha>
