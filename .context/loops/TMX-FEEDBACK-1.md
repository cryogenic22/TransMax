# TMX-FEEDBACK-1 — In-app feedback: backend (model + API + audit trail)

**State**: `[Done]` — `085aa94` on origin/main
**Owner**: Platform & Observability
**Sprint**: 2 (feedback-loop initiative)
**Started**: 2026-06-04
**Closed**: —
**Reversibility**: `two-way` — new additive table + new router; no existing schema or API shape changes. Revertable by dropping `feedback_entries` + deleting `app/api/feedback.py` + unregistering the router.
**Pre-mortem**: if this fails in production, the failure mode is a 500 on `POST /api/feedback` (the submit widget errors) OR a tenant-context leak letting one org read another's feedback. Neither touches the translation pipeline or audit chain.
**Blast radius**: `app/models/database.py` (+1 model), one Alembic revision, new `app/api/feedback.py`, one line in `app/main.py`, new `tests/test_feedback_api.py`. No translation, agent, or audit-chain code touched.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) net-new because there is no issue-intake surface today; (b) one router, <5 callers; (c) backend-only, no bundle impact; (d) reuses `TenantScopedMixin` + `SoftDeleteMixin` + `get_db` + `get_current_user` + `/api/*` router idiom; (e) ships with `tests/test_feedback_api.py` red-without-the-route.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield feature, not a reported failure).
- [ ] **G3 Completion** — `curl -X POST /api/feedback` persists a row with `status=new`, scoped to the caller's org; `GET /api/feedback?status=new` returns it; `PATCH` transitions status; `DELETE` soft-deletes (no hard delete).

---

## 1. Task

Replicate market_zero's in-app issue→triage→deploy loop for TransMax, Phase 1 = the **backend intake**. Users submit bug/issue/enhancement/feature reports from the UI; submissions are logged to a `feedback_entries` table and exposed via a small REST surface the automation (Phase 3 slash commands) will poll and update.

Addenda at play:
- **A4** — new table goes in `app/models/database.py` (operational layer; `String(36)` ids; SQLite-friendly), alongside `Document`/`Segment`/`ChangeLog`. No pgvector needed → does NOT go in `translation.py`.
- **A9** — soft-delete only. market_zero's `DELETE` hard-deletes the row; we use `SoftDeleteMixin.soft_delete()`.
- **A11/tenancy (TMX-3011/3012)** — table is `TenantScopedMixin`; `organization_id` auto-injects from request tenant context.
- **A1** — *considered and scoped out of the cryptographic v2 chain*: `AuditWriterV2.record_event` is keyed on `job_id` (FK `translation_jobs`). Feedback has no job and is product metadata, not a translation-pipeline state change — which is what A1 governs. The row's own lifecycle columns (`status`/`resolved_by`/`resolution`/`updated_at`), the append-only trackers (`.context/feedback/`, Phase 3), and the cron's per-item git commits constitute the feedback audit trail. Forcing feedback into the job chain would be wrong data-modelling and bloat (fails G1-a).

## 2. Spec — acceptance criteria

- [ ] AC-1: `POST /api/feedback` with `{category,title,...}` inserts a row with `status="new"`, `organization_id` from tenant context, and returns `{feedback:{id,category,title,status,priority,created_at}}`.
- [ ] AC-2: invalid `category` or `priority` → HTTP 400 (fail loud, A3); not silently coerced.
- [ ] AC-3: `GET /api/feedback?status=new&category=bug&limit=&offset=` returns `{items,total,limit,offset}`, newest first, only the caller's org, only non-deleted rows.
- [ ] AC-4: `PATCH /api/feedback/{id}` updates any of `status`/`priority`/`resolution`/`resolved_by`; invalid `status`→400; unknown id→404; bumps `updated_at`.
- [ ] AC-5: `DELETE /api/feedback/{id}` **soft-deletes** (sets `is_deleted`), returns 204; row no longer appears in `GET`; a hard `session.delete` is mechanically impossible (mixin raises).
- [ ] AC-6: all endpoints depend on `get_current_user` → adapt to `AUTH_MODE` (open in `none`, walled once TMX-AUTH-WALL flips `jwt`).
- [ ] AC-7: `GET /api/feedback/stats` returns counts by category + status.

Out of scope: attachments upload pipeline beyond storing the JSON blob; the frontend widget (TMX-FEEDBACK-2); the triage/auto-fix automation (TMX-FEEDBACK-3); the cron (TMX-FEEDBACK-4); the auth wall (TMX-AUTH-WALL).

## 3. Design

Mirror market_zero's `feedback_entries` schema (`schema/migrations/020_feedback_entries.sql`) but adapted to TransMax conventions: SQLAlchemy model with both mixins instead of raw SQL; `String(36)` id (A4) instead of Postgres `UUID gen_random_uuid()`; soft-delete `DELETE` (A9); `/api/feedback` prefix (TransMax `/api/*` idiom) instead of `/feedback`. Status lifecycle preserved verbatim: `new → triaged → in_progress → resolved | rejected`. Category/priority/status value sets preserved so the ported slash commands work unchanged.

Router built with `get_db` + `get_current_user` dependencies exactly like `app/api/auth.py`. The Alembic revision (down_revision = `c96c8b36799b`, current head) is added for convention; note the live Railway DB is built by `init_db()` `create_all`, so the table will appear there automatically on next deploy regardless of Alembic (see TMX-DEPLOY-MIGRATE devops note).

Rejected: (a) reusing `ChangeLog` for feedback — wrong semantics (ChangeLog is HITL segment edits); (b) a global non-tenant table — breaks the tenant-isolation invariant the auto-filter enforces.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/models/database.py` | +~40 | `Feedback` model (TenantScoped + SoftDelete) |
| `alembic/versions/20260604_tmx_feedback_1.py` | new | create `feedback_entries` + indexes |
| `app/api/feedback.py` | new | POST/GET/GET-stats/PATCH/DELETE router |
| `app/main.py` | +2 | register `feedback_router` |
| `tests/test_feedback_api.py` | new | AC-1..AC-7 regression tests |

## 5. Eval / Test

```
python -c "from app.core.database import init_db; init_db()"   # add feedback_entries to local sqlite via create_all
python -m pytest tests/test_feedback_api.py -q
```

```
11 passed, 2 warnings in 8.24s
```

Adjacent regression (router/app intact): `tests/test_feedback_api.py tests/test_dashboard_activity_feed.py` → **23 passed**.
Alembic single-head confirmed (`tmx_feedback_1`). App imports with routes:
`/api/feedback` (POST+GET), `/api/feedback/stats`, `/api/feedback/{id}` (PATCH+DELETE).

## 6. Red team

- Ran ruff on the diff. `app/api/feedback.py` → **clean**. `app/models/database.py` carries **10 pre-existing ruff errors on HEAD** (unused `Enum` alias; `engine` F811; E402 on the legacy `from app.core.database import …` re-export block that sits at file-end to avoid a circular import). NOT introduced by this ticket. Added `# noqa: F401` to the re-export; residual E402/F811/Enum are pre-existing debt — out of scope, flagged for a focused hygiene pass at commit time (or **TMX-FEEDBACK-1-lint**).
- mypy: `feedback.py` shows the endemic SQLAlchemy `Column[str]`-assignment false-positives (81 across 12 files repo-wide); matches the existing idiom in `app/api/auth.py`. **mypy is not a pre-commit gate** (no hook, no `[tool.mypy]`). Left as-is to match repo convention.
- Tenancy: reads/writes go through `get_db` + the request `TenantContextMiddleware` (DEFAULT_ORG_ID), and `Feedback` is `TenantScopedMixin` → auto-filter prevents cross-org reads. Verified org-scoping in `test_create_scopes_to_default_org`.
- A9: `test_delete_soft_deletes_and_hides_row` proves the row survives in-DB with `is_deleted=True` and is auto-hidden; a 2nd DELETE 404s. Hard-delete is mechanically refused by the mixin.
- Failure modes: invalid category/priority/status → 400 (fail loud, A3); unknown id → 404. No silent coercion.
- Edge not covered (acceptable for Phase 1): attachment payload size cap (frontend caps at 2MB/5 files in TMX-FEEDBACK-2); rate-limiting on the public-in-`none`-mode POST (closes once TMX-AUTH-WALL flips jwt).

## 7. Fix

No code-behaviour findings from red team. Only the pre-existing `database.py` lint debt noted above (out of scope). Clean.

## 8. Deploy

- [x] Commit: `085aa94` (bundled with TMX-FEEDBACK-2)
- [x] Pushed to origin/main (auto-deploys to Railway) — authorized by Kapil ("push 1+2 together")
- [x] `.context/active_tasks.md` updated
- [x] Final hygiene pass on `database.py` ruff debt before staging (dropped unused Enum import, renamed shadowing param)
- [x] All gates validated manually (no pre-commit hooks installed in this clone): ruff/ruff-format clean, ratchet 17/17 (no loosening), quality-gate pass, 11 backend tests green

**G3 completion check**: backend ACs all proven green by tests. The user-visible capability (submit feedback from UI) is not exercisable until TMX-FEEDBACK-2 (widget) ships — but the API contract it depends on is complete and tested. Status stays `[WIP — pending push]`, not `[Done]`, until the SHA is on origin/main (push hygiene rule).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-04 | — | `[Spec]` | Created |
| 2026-06-04 | `[Spec]` | `[WIP]` | Design locked; implementing backend |
