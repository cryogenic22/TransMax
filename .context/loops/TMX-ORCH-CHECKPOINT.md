# TMX-ORCH-CHECKPOINT (Loop A) — stuck-PROCESSING job sweeper

**State**: `[WIP]`
**Owner**: Platform & Observability
**Sprint**: MQM Keystone / Phase 0 (lifecycle integrity)
**Started**: 2026-06-15
**Closed**: —
**Reversibility**: `two-way` (new read-only-by-default script + 2 default-OFF settings; revertable by deleting them)
**Pre-mortem**: if this fails in production, the failure mode is *it sweeps a still-alive job*. The red team showed the engine does NOT heartbeat the Document row during translate (only Segment rows), so `Document.updated_at` is frozen while a job is alive — anchoring on it alone WOULD wrongly sweep a long translate. Fixed: "stuck" requires no recent activity on the Document **or any of its Segments** (Segments are written throughout translate), so a live-but-slow job is never swept. Further guarded by a generous timeout, a default-OFF mutation gate (in `sweep()`, not just the CLI), and an AC pinning the live-but-slow case.
**Blast radius**: new `scripts/stuck_job_sweeper.py`, 2 `config.py` settings. No request-path code; no happy-path change. Only ever touches docs already abandoned in `processing` past the timeout.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: a worker killed mid-run (deploy/OOM/crash) leaves a doc orphaned in `processing` forever — neither `finalize_job` nor `runner.py`'s except handler ran; nothing recovers it today; (b) <5 callers; (c) script-only; (d) reuses `Document.status` (NO new `JobStatus` enum/table — A4), `update_document_status`, the `emit_v2_audit_event` shim, `org_context`, and the `scripts/mqm_shadow_report.py` `python -m` template; (e) ships with tests.
- [x] **G2 Reproduce-the-failure** — a seeded doc left `processing` with no recent Document/Segment activity is the orphan; the test reproduces it and proves the sweep recovers it (and that a fresh one, and a live-but-slow one with a fresh Segment, are untouched).
- [x] **G3 Completion** — the sweep flips an orphan to `IN_REVIEW` + emits a `JOB_SWEPT_STUCK` audit event; default-OFF (gate in `sweep()`); idempotent; happy path untouched.

---

## 1. Task

LangGraph jobs are tracked by `Document.status` (`job_id == doc_id`, `runner.py:31`). `validate_request` sets `PROCESSING`; the translation engine flips the doc out of `processing` mid-run (`translation_engine.py:723`); `finalize_job` writes the terminal status + audit. If the worker dies before either runs (deploy, OOM, kill), the doc is **orphaned in `processing` forever** — invisible, never recovered (A8 lifecycle integrity). Build a sweeper that finds these and flips them to `IN_REVIEW` (fail-toward-human-triage, A3) with an audit event (A1). Loop B (a LangGraph checkpointer for crash-resume) is a SEPARATE, one-way follow-up — a `MemorySaver` does NOT survive a crash so it is not the fix; a persisted saver needs a checkpoint table + `thread_id` plumbing.

## 2. Spec — acceptance criteria

- [ ] AC-1: `collect_stuck_docs(timeout)` returns every `Document` with `status=='processing'` AND `updated_at` older than the timeout, **across all tenants** (`include_other_tenants=True`).
- [ ] AC-2: `sweep()` flips each stuck doc to `IN_REVIEW` via `update_document_status` (REUSE the existing status — no new enum) and emits a `JOB_SWEPT_STUCK` v2 audit event (`actor_kind='system'`, payload `{reason, timeout_seconds, last_updated, swept_at}`) — A1.
- [ ] AC-3: A doc in `processing` whose `updated_at` is WITHIN the timeout is NEVER touched; no doc in a terminal status (`translated`/`in_review`/`approved`) is ever a candidate. Happy path provably unchanged.
- [ ] AC-4: Idempotent — a second consecutive run finds zero candidates (the flip removes the doc from the `processing` set) and writes nothing.
- [ ] AC-5: Default-OFF — `stuck_job_sweep_enabled=False`; the script refuses to MUTATE unless the flag is on. `--dry-run` previews (read-only) regardless. Triggering a translation is byte-for-byte unchanged.
- [ ] AC-6: One bad doc (missing tenant/audit trail) cannot abort the batch — `sweep` isolates per-doc errors and continues (A3 fail-loud-but-isolate).
- [ ] AC-7: Per-doc tenant isolation — each `JOB_SWEPT_STUCK` event is written under the doc's own `org_context(organization_id)`.

Out of scope: **Loop B** — the LangGraph checkpointer + crash-resume (one-way: checkpoint table + `thread_id`); a follow-up worksheet. The `runner.py:58` `status='error'` latent bug (not a valid `DocumentStatus`) — flag it, but do NOT add an `error` enum here (A4/anti-bloat); a distinct terminal-failed status is its own one-way UI+enum ticket.

## 3. Design

Engine-first reuse: the job lifecycle engine already IS `Document.status`. The staleness anchor is sound because `updated_at` has `onupdate=now` (`database.py:142`) and the engine flips a live job out of `processing` mid-run — so a doc still `processing` past the timeout provably never advanced and nothing has been re-writing its row. Read cross-tenant (forensic admin scan, mirroring `mqm_shadow_report.py`), filter `updated_at` in Python (dialect-safe naive/aware normalisation; the `processing` set is tiny), then per-doc enter `org_context` and flip + audit. Audit goes to the **canonical v2 chain only** (`emit_v2_audit_event`, system actor) — matching every recent loop (MQM shadow/judge/ensemble); the legacy v1 dual-write is being retired (TMX-3110d) and is not written for new system events. `emit_v2` is fail-safe; if a doc has no `translation_jobs` row (died before the job row existed) the event is logged-not-persisted and the status still flips (fail-loud-but-proceed) — documented honestly.

Alternatives rejected: (a) a `MemorySaver` checkpointer — doesn't survive a crash, so it doesn't address the orphan; (b) a new `JobStatus`/terminal-failed enum — A4/anti-bloat, `IN_REVIEW` already means "held for a human"; (c) running the sweep from the request path — keeps the happy path pure; the script runs via `python -m` / the orchestrator only.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/config.py` | ~110 | `stuck_job_sweep_enabled: bool = False` + `stuck_job_timeout_seconds: int = 1200` |
| `scripts/stuck_job_sweeper.py` | new | `collect_stuck_docs` + `sweep` + `_sweep_one` + v2 audit + CLI (`--dry-run`/`--json`/`--timeout-seconds`) |
| `tests/test_stuck_job_sweeper.py` | new | orphan swept; fresh untouched; terminal untouched; idempotent; dry-run writes nothing; audit emitted; per-doc isolation |

## 5. Eval / Test

```
python -m pytest tests/test_stuck_job_sweeper.py -q
```
```
11 passed — orphan swept; live-but-slow job (fresh Segment) NOT swept; died-mid-
translate (old Segments) swept; fresh/terminal untouched; disabled-finds-but-no-
mutate; idempotent; dry-run writes nothing; per-doc isolation. Full regression 230 passed.
```

## 6. Red team

4-lens adversarial review (workflow `wctx81sw8`). **3 real defects found:** (1) [high] the staleness anchor on `Document.updated_at` alone is unsound — the engine writes only Segment rows during translate, so a long-but-alive job is wrongly swept (false `JOB_SWEPT_STUCK` audit event); (2) [med] audit emitted AFTER the status flip (A1 wants audit-before-side-effect) — and the v2 emit shares `finalize_job`'s `translation_jobs` FK surface; (3) [low] the default-OFF gate lived only in `main()`, so a programmatic `sweep()` caller bypassed it. Confirmed sound: idempotency, dry-run read-only, naive/aware compare, per-doc isolation, A4 (no new enum), reuse.

## 7. Fix

(1) `collect_stuck_docs` now anchors on the most-recent activity across the Document AND its Segments (`max(Segment.updated_at)`) — a live translate writing Segments is never swept; added two tests (fresh-Segment protects; old-Segments swept). (2) `_sweep_one` emits the audit BEFORE the flip (A1 ordering); the v2-only + shared-FK caveat is documented in the module docstring (the recovery still proceeds on a sink hiccup — unblocking the orphan is the priority). (3) The enabled gate moved into `sweep()` (resolved from `stuck_job_sweep_enabled` when None); tests pass `enabled=True`; added a disabled-finds-but-no-mutate test. Re-ran: 11 green.

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [ ] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 3); Loop A sweeper only; Loop B checkpointer deferred (one-way) |
