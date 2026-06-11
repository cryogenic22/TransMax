# TMX-AUDIT-DB-DOCID-LOOKUP — Resolve doc_id from a job/review identifier; implement the get_pending_reviews stub

**State**: `[Done]`
**Owner**: pod-A (Auth & Tenancy + Reviewer Frontend)
**Sprint**: 2
**Started**: 2026-06-11
**Closed**: —
**Reversibility**: `two-way` — pure addition (new db_service method) + filling a stub body; no schema change.
**Pre-mortem**: if this fails in production, the HITL reviewer queue silently returns nothing (the current `pass`-body behaviour) and blocked segments never reach a human — a regulator-facing A3 failure.
**Blast radius**: `app/services/db_service.py` (+1 read method), `app/services/review_service.py` (fill `get_pending_reviews`). Read-only query path; no writes.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — net-new method has a real caller (`ReviewService.get_pending_reviews`), <5 callers, reuses the existing `get_flagged_segments` delegation, ships with a failing-first test. PASS.
- [x] **G2 Reproduce-the-failure** — `get_pending_reviews` currently returns `None` (falls off a `pass`). Test pins that the stub returned `None`; post-fix it returns the flagged-segment list.
- [x] **G3 Completion** — a reviewer calling `get_pending_reviews(job_id)` now receives the blocked/review-required segments instead of `None`.

---

## 1. Task

`ReviewService.get_pending_reviews(job_id)` is a `pass`-bodied stub (`app/services/review_service.py:36`) carrying a `TODO(TMX-AUDIT-DB-DOCID-LOOKUP)`. It silently returns `None`, so the HITL review surface has no working "what needs my review on this job" path. A3 (no silent fallbacks in regulated paths): a reviewer queue that silently yields nothing is a safety hazard. Add the missing `get_doc_id_from_job` lookup to `db_service` and wire `get_pending_reviews` to the existing `get_flagged_segments`.

A4 is at play: the operational layer (`database.py`: `Document`/`Segment`, String IDs) and the queue layer (`models.py`: `TranslationJobQueue`) are parallel. The reviewer/job surface already uses `Document.id` as its identifier end-to-end (the frontend calls `api.documents.get(jobId)` / `api.segments.list(jobId)`). To avoid deepening the dual-layer divergence (and the SQLite cross-layer-query crash A4 warns about), the lookup resolves the identifier *within the operational layer*: it is a doc_id iff a `Document` with that id exists.

## 2. Spec — acceptance criteria

- [ ] AC-1: `DBService.get_doc_id_from_job(identifier)` returns the identifier when a `Document` with that id exists, and `None` otherwise (explicit, A3 — no guessed default).
- [ ] AC-2: `ReviewService.get_pending_reviews(job_id)` returns the same list `get_flagged_segments` returns for the resolved doc (BLOCKED / REVIEW_REQUIRED segments).
- [ ] AC-3: When the identifier resolves to no document, `get_pending_reviews` returns `[]` (not `None`) and logs a WARNING (visible, not silent).
- [ ] AC-4: Tenant scoping is preserved — the lookup goes through the tenant-scoped session, so a cross-tenant id resolves to `None`.

Out of scope: bridging `TranslationJobQueue` ↔ `Document` (A4 — would deepen divergence; tracked separately if a real non-doc job-id path emerges). Building a reviewer API endpoint (frontend already has the segments path).

## 3. Design

`get_doc_id_from_job` is a thin, operational-layer-only read: `session.query(Document).filter(Document.id == identifier).first()` → return `identifier` if found else `None`. It deliberately does NOT join across to the queue layer.

`get_pending_reviews` resolves the doc id, logs+returns `[]` on miss, else delegates to `get_flagged_segments(doc_id)` (single source of truth for "which segments need a human").

Rejected: querying `TranslationJobQueue` to map job→doc (no FK exists; A4 cross-layer query is the documented SQLite-crash hazard). Rejected: returning a mocked structure (the old comment floated this — A3 hard reject).

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/db_service.py` | +~20 | new `get_doc_id_from_job(identifier) -> Optional[str]` |
| `app/services/review_service.py` | 19-36 | implement `get_pending_reviews`; remove stub `pass` + mock comments |
| `tests/test_review_service_pending.py` | new | AC-1..AC-4 |

## 5. Eval / Test

`python -m pytest tests/test_review_service_pending.py -q` → 4 passed (AC-1 known/unknown, AC-2 flagged-only list, AC-3 unknown→[], AC-4 tenant scoping). Full backend suite 1160 passed / 2 skipped. Ratchet 17/17.

## 6. Red team

- Cross-layer query hazard (A4): avoided — the lookup queries only `Document` (operational layer), never `TranslationJobQueue`. AC-4 proves tenant auto-filter is honoured (org B can't resolve org A's doc).
- Silent-None regression: the test pins `get_pending_reviews` now returns `[]` (list) on a miss, never `None`, and logs a WARNING.
- `original_segment` dead var + stale imports in the touched file cleaned (ruff green) — no broken window left behind.

## 7. Fix

No findings — clean.

## 8. Deploy

- [ ] Commit: <SHA> (batch B)
- [x] `.context/active_tasks.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[WIP]` | Created; code in progress |
| 2026-06-11 | `[WIP]` | `[Done]` | code+tests+suite+ratchet green |
