# TMX-PROJECTS-MODEL — Project + project_documents tables + service

**State**: `[Done]` — pending commit
**Owner**: Reviewer Frontend / Platform (jobs management)
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — **NEW tables only** (no column added to existing `documents`). Railway `create_all` provisions new tables automatically, so this is two-way-safe (unlike a column-add to an existing table, which stays Kapil-gated — see TMX-3706 / TMX-DEPLOY-MIGRATE). Verified `create_all` adds `projects` + `project_documents` locally.
**Pre-mortem**: if a join leaked across tenants, a project could group another tenant's docs → both tables are `TenantScopedMixin` (auto org-filter) and `SoftDeleteMixin`.
**Blast radius**: `app/models/database.py` (2 new tables), `app/services/project_service.py` (new).

**Gates**: G1 ✅ functional depth — a professional TMS needs to group jobs above the single-document level (submission/study/client). New table not a column-add → does not deepen the dual-model debt (A4: operational table in database.py). G2 N/A. G3 ✅ — service tested DB-isolated.

## Design
New `projects` + `project_documents` join (not a FK column on `documents`) so the existing schema is untouched and membership is itself soft-deletable/audit-scoped. Membership de-dup in the service layer (not a DB unique constraint) so a soft-removed doc can be re-added (A9). `ProjectService` is a new module — keeps the `db_service` god-object from growing (deep module, single responsibility).

## Spec
- AC-1: `projects` + `project_documents` exist; `create_all` provisions them; both tenant-scoped + soft-delete.
- AC-2: create/list/update + add/remove/list-members + summary work under tenant context.
- AC-3: idempotent membership; soft-remove then re-add; fail-loud on missing doc/project; status validated.

## Test
`tests/test_project_service.py` — 6 passed.

## Deploy
- [ ] Commit: <sha>
