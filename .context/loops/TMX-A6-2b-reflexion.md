# TMX-A6-2b-reflexion — Reflexion-pass tokens in usage telemetry

**State**: `[Verify]`  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  Loop 2/10 (2026-06-04 batch)
**Reversibility**: `two-way` — accumulate tokens + one emit in the reflexion node. Revertable.
**Blast radius**: `app/agents/nodes/reverse_translate.py` only. No schema.

## 1. Task
Completes A6 per-job consumption accounting. A6-2 captured the translate pass, A6-2b the refine pass; the **reflexion** node (`reverse_translate`) makes a back-translation LLM call per segment whose tokens were never captured. Accumulate them and emit an `LLM_USAGE_RECORDED` event (`_actor_node='reflexion'`). Addenda A6/A1/A3.

## 2. Spec
- [x] AC-1: per-segment back-translation tokens accumulate across the gathered workers (asyncio single-threaded ⇒ `+=` safe).
- [x] AC-2: one `LLM_USAGE_RECORDED` (`_actor_node='reflexion'`, `pass='reflexion'`) summing all segments' tokens, when job_id + tokens>0.
- [x] AC-3: no tokens ⇒ no event.
- [x] AC-4: A3-wrapped — emit failure logged, never blocks the pipeline.

## 3. Design
Closure-local `usage_acc` accumulated in `process_segment` via the shared `extract_token_usage`; after `asyncio.gather`, `emit_usage_event(..., actor_node="reflexion")`. Reuses the TMX-A6-2b helper (DRY across translate/refine/reflexion). Added a module `logger` (the node previously used `print` only) so the new failure path doesn't trip the `print_in_app` ratchet.

## 4. Code
| File | Change |
|---|---|
| `app/agents/nodes/reverse_translate.py` | imports (llm_usage, settings, logging); `usage_acc`; per-segment accumulate; post-gather emit; removed dead `List` import |
| `tests/test_reflexion_usage.py` | new — 2 tests (aggregated emit across 2 segments; no-tokens no-event); red-before-green |

## 5. Test
`pytest tests/test_reflexion_usage.py` → 2 passed (aggregated test RED before wiring). Ratchet 17/17 (logger, not print). Full suite — stage 8.

## 6. Red team
- Concurrency: asyncio is single-threaded; `+=` between an `await` and the next has no preemption point → safe. (True multi-process would need per-call return + sum; noted.)
- Pre-existing caught defect surfaced: `reverse_translate` calls `update_quality_scorecard_metric(job_id, {dict})` but the signature wants `(job_id, metric, value)` → "Reflexion Persistence Failed" (caught, non-fatal). Spawned **TMX-REFLEXION-SCORECARD-SIG**.
- emit is A3-wrapped; failure never blocks.

## 7. Fix
Removed dead `List` import. No other findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 2 tests
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-REFLEXION-SCORECARD-SIG** — fix `update_quality_scorecard_metric` call-signature mismatch in `reverse_translate`.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~00:25Z | — | `[Verify]` | accumulate + emit; 2 tests; ratchet 17/17; awaiting full suite |