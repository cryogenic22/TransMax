# TMX-MQM-CAPTURE — reviewer override → learning bridge (gold signal)

**State**: `[Done]`
**Owner**: Reviewer Frontend / Quality & Regulatory
**Sprint**: MQM Keystone (Phase 1)
**Started**: 2026-06-14
**Closed**: 2026-06-14
**Reversibility**: `two-way` — additive background-task hook + one flag; revertable by removing the `add_task` call.
**Pre-mortem**: if this fails it logs a warning off the request path; the reviewer's edit still succeeds (capture is best-effort).
**Blast radius**: `app/api/segments.py` `update_segment` (+ a background helper) + one config flag.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — reuses the existing `LearningService.process_learning_event` bridge (the audit found it reachable from no endpoint); cheap now, expensive to backfill (review cond. 6); ships with tests.
- [x] **G2 Reproduce-the-failure** — N/A (closes a coverage gap, not a crash).
- [x] **G3 Completion** — a reviewer override now lands a PROPOSED Black-Book candidate; confirmed by tests asserting the bridge is invoked within the tenant context.

---

## 1. Task
Wire the live reviewer-edit path (`PATCH /api/segments/{id}`) into the learning bridge so a reviewer **override** is captured as the gold signal Phase-2 judge calibration needs — without leaving Phase 1 to start cold (review cond. 6). The audit found `submit_correction`/`process_learning_event` reachable from no production endpoint; this reconnects it. Addenda: A1 (the override is institutional learning), A3 (fail-safe, tenancy-honest), A10 (`.context` not relevant; this is code).

## 2. Spec — acceptance criteria
- [x] AC-1: when a reviewer PATCH actually changes the MT text, the override (source, MT, correction) is fed to `LearningService.process_learning_event` as a PROPOSED candidate.
- [x] AC-2: it runs as a FastAPI `BackgroundTask` — zero added request latency.
- [x] AC-3: it re-establishes the segment's tenant context (`org_context`) so the tenant-scoped candidate write does not fail loud; if no org is resolvable it skips with a warning (A3), never crashes.
- [x] AC-4: gated by `settings.enable_hitl_learning_capture` (default on); only fires on a real change (confirms/no-ops cost nothing).

Out of scope: persisting an `MqmAnnotation.human_decision` row (→ TMX-MQM-1a once the table lands); distinguishing confirm vs override vs amend as typed decisions (→ Phase 2).

## 3. Design
Reuse the existing bridge rather than author a new capture path. Background task + tenant-context propagation (the TMX-3012c pattern) solves the async + tenancy constraints. Use the segment's own `organization_id` for the context (robust regardless of request scoping). Rejected: synchronous capture (adds an LLM call to the request); a new ChangeLog column (schema churn for a signal the learning bridge already models).

## 4. Code
| File | Change |
|---|---|
| `app/core/config.py` | +enable_hitl_learning_capture |
| `app/api/segments.py` | +_capture_hitl_override background helper; update_segment schedules it on a real override |
| `tests/test_hitl_capture.py` | new — 3 tests |

## 5. Eval / Test
```
python -m pytest tests/test_hitl_capture.py -q  → 3 passed
# asserts: bridge invoked within tenant context; skips with no org; swallows learning failure
```

## 6. Red team
Risk: background task losing tenant context → tenant-scoped write fails loud — solved by `org_context(seg_org_id)`. Risk: capture failure surfacing to the reviewer — swallowed + logged. Risk: per-edit LLM cost — only fires on a real change + flag-gated. Risk: no org resolvable → silent miss — logged warning (A3), not a crash.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: `70953c9` (batched: "TMX-MQM-5a/CAPTURE: run the MQM engine in shadow + capture reviewer overrides")
- [ ] Pushed to origin/main: **gated on Kapil** (branch `feat/mqm-keystone`)
- [x] `.context/active_tasks.md` updated

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-14 | — | `[Done, pending push]` | bridge reconnected; gold capture live |
