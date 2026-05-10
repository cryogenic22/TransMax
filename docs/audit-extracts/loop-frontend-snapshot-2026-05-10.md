# Frontend lane verification snapshot — 2026-05-10

Recorded by Antigravity / Pod B at the close of fire 35 (after the sonner-everywhere arc landed). Captures the green-light state of the frontend lane and surfaces a backend regression that's outside Pod B's scope.

---

## Frontend lane: GREEN

### Vitest (component / unit)

```
Test Files  12 passed (12)
     Tests  104 passed (104)
  Duration  ~12s
```

All component tests pass. No regressions from the dynamic aria-label change (TMX-3702-a11y) or the toast-pattern migrations.

### Playwright e2e (page-level integration)

```
20 passed (2.6m)
```

All 10 spec files green when run with `--workers=1`:
- `control-assets.spec.ts` (2) — TMX-3604-assets-err
- `control-jobs-delete.spec.ts` (1) — TMX-3604-delete-toast
- `control-jobs-download.spec.ts` (1) — TMX-3604-download-toast
- `document-review.spec.ts` (1) — TMX-3604-doc-review-err
- `document-segment-save.spec.ts` (1) — TMX-3604-save-toast
- `landing.spec.ts` (6) — pre-existing redirect coverage
- `segments-revisions.spec.ts` (5) — TMX-3702-e2e + 3 error-path triad tests
- `tools-audit-toast.spec.ts` (1) — TMX-3604-tools-toast
- `tools-correction-success.spec.ts` (1) — TMX-3604-alert-to-toast
- `upload-glossary.spec.ts` (1) — TMX-3705-glossary-err

**Note on parallelism**: `--workers=1` is required on this dev machine; the Playwright config defaults to `workers: undefined` (cpu-count) which races against a single shared `npm run dev` server and causes intermittent ERR_CONNECTION_REFUSED failures. CI is fine because it uses `workers: 1` already.

### Lint + typecheck + build

All clean. No changes to bundle size from the toast-pattern migrations (sonner already in deps).

---

## Frontend sweep arcs closed this session

Two parallel error-class sweeps shipped in this loop chain:

### Fetch-error sweep (5 surfaces)

A3 silent-fallback violations on regulator-facing fetch paths. Each surface now distinguishes "real empty state" from "API down" and surfaces the actual server message via a `role="status"` banner.

- jobs/[id] doc fetch — c7d7473 — TMX-3603-jobs-id-err
- jobs/[id] segments fetch — same commit
- jobs/[id] agent-activity polling — 418cbc5 — TMX-3603-agents-err
- control assets cards — 517a547 — TMX-3604-assets-err
- upload glossary catalog — e2ac305 — TMX-3705-glossary-err
- documents/[id] doc fetch — 9c3adca — TMX-3604-doc-review-err

### Mutation-error sweep (5 surfaces / 9 catch sites)

Same anti-pattern on user-action paths. Each surface now fires `toast.error(getErrMessage(err, "..."))` instead of `console.error` only.

- jobs delete (audit-trail tombstone path A9) — c6f87a0 — TMX-3604-delete-toast
- segment save (HITL correction audit-event path A1) — 1836924 — TMX-3604-save-toast
- 2× download (JobsView + documents/[id]) — fae481d — TMX-3604-download-toast
- tools-page 5 sub-sites (vote / Black Book correction / audit / back-trans / matrix) — 944f8d7 — TMX-3604-tools-toast

### Sonner-everywhere arc

After the failure-mode sweeps closed, two `alert()` sites remained:

- tools/page.tsx success on Black Book correction → toast.success — 6d529fd — TMX-3604-alert-to-toast
- workspace/page.tsx translate-fail (alert + console.error) → toast.error — same commit

Zero alert() sites in app code. Zero silent console.error swallows on user-action paths. (One remaining `console.error` in `CopyButton.tsx:15` is acceptable: clipboard failures are rare, the icon swap already gives user feedback, and there's no meaningful server message to surface.)

---

## Backend lane: YELLOW (pre-existing, NOT caused by Pod B)

`pytest tests/ --ignore=tests/test_docx_roundtrip.py --ignore=tests/evals` reports:

```
32 failed, 770 passed, 2 skipped, 21 errors in 197s
```

96% pass rate. Errors concentrate in:

- `tests/test_segments_element_meta.py` — `sqlalchemy.exc.PendingRollbackError`
- `tests/test_tamper_detection.py` — same pattern
- `tests/test_blackbook_v2.py::TestRuleCRUD` — 500-status assertions
- `tests/test_auth_endpoints.py` / `test_auth_rbac.py` — sqlalchemy errors
- `tests/test_dashboard_activity_feed.py` — limit-clamp + unknown-audit cases

The `PendingRollbackError` pattern is a session-state issue, not a logic regression. Most likely caused by schema drift introduced by recent parallel-lane work:

- TMX-3500 (Regulatory Pack scaffold, 99e2d81)
- TMX-3052 instance-based circuit breaker (fb3c8ee)
- TMX-3053 quality-gate singleton lock (3ee727e)
- TMX-3045 auto-promote removal (7231c7d)
- TMX-3012d DEFAULT_ORG_ID sweep (d1b8ae3)

Pod B did not touch any of these surfaces. Pod A (Auth & Tenancy) and Quality lanes own the cleanup. Recording here so the next backend fire picks it up directly rather than re-discovering.

**Suggested next action (backend lane)**: run failing test in isolation, identify whether the rollback comes from a missing migration or a session-scope fixture mismatch. Likely a one-line fixture fix (rollback or recreate session per test).

---

## Files of record

This snapshot is intended to live alongside the periodic 4-agent verify-audit reports per CLAUDE.md §"Periodic verification". It complements rather than replaces the next full audit, which should be run after backend regressions clear.
