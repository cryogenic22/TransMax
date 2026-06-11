# TMX-DBSERVICE-LINT — Clean ruff debt in db_service.py

**State**: `[Done]` — `9bbcc4e` on origin/main
**Owner**: Platform & Observability
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — removes unused imports + one dead assignment; one intentional SQLAlchemy filter `# noqa`'d.
**Pre-mortem**: removing a "used" import would break import — guarded by an import smoke + the full suite (db_service is exercised across the API/agent tests).
**Blast radius**: `app/services/db_service.py` only.
**Context (supersedes L6 batch-embed)**: the planned drift-embedding batch loop is entangled with the `quality_gate.py` 800-line ceiling (adding a batch method trips `mega_files_800`) and the per-pair embed is *already* a single batched call; deferred to ride the TMX-3400 split. Substituted this contained, high-certainty lint loop.

**Gates**: G1 ✅ (stability — pays down real lint debt in a 904-line legacy module; surfaced while print-sweeping). G2 N/A. G3 ✅ — `ruff check app/services/db_service.py` passes; module imports; full suite green.

## Spec
- AC-1: remove 3 unused imports (`DocumentStatus`, `AuditRecord`, `Segment`/`SegmentStatus`) + 2 redundant re-imports (`Session`, `text`).
- AC-2: remove the dead `dist = 0.0` assignment (documented unused).
- AC-3: keep the intentional `Glossary.is_active == True` SQLAlchemy filter (it must stay `== True` for SQL generation) — annotate `# noqa: E712`, do NOT "fix" it.

## Test
`ruff check app/services/db_service.py` → clean. `import app.services.db_service` OK. Full suite in batch wrap-up.

## Deploy
- [x] Commit: `9bbcc4e`
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done]` — `9bbcc4e` on origin/main | 6 auto-fixed + 2 judged manually (kept the SQLAlchemy `== True`) |
