# TMX-A6-2b — Refinement-pass tokens in the usage telemetry

**State**: `[Done]` — `b289646` on origin/main  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  **Started/Closed**: 2026-06-03
**Reversibility**: `two-way` — new shared helper + a refiner emit + a DRY refactor of the engine. Revertable.
**Pre-mortem**: if it fails, refinement tokens stay unrecorded — degrades to A6-2 behaviour (translate-pass only); never blocks the pipeline (A3-wrapped).
**Blast radius**: `app/services/llm_usage.py` (new), `app/agents/graph.py` (refiner emit + config-snapshot extraction), `app/agents/nodes/translation_engine.py` (DRY delegation), `app/agents/_config_snapshot.py` (new, extracted).

**Gates**: G1 — A6 accuracy: per-job consumption must include refinement LLM calls, not just the first pass; reuses cost_for + the emit shim (no new dep). G2 — refiner-emit test red-before-green. G3 — a refined job leaves a second `LLM_USAGE_RECORDED` (`_actor_node='refiner'`) in the chain.

## 1. Task
A6-2 records only the translate pass; `refine_translation` makes its own LLM call (graph.py) whose tokens were never captured, so refined jobs under-report consumption. Capture them and emit a refiner usage event. Addenda A6 (full supplier consumption), A1 (chained), A3 (telemetry never blocks).

## 2. Spec
- [x] AC-1: shared `build_usage_record(model, in, out)` produces the canonical usage dict (cost from the pricing table).
- [x] AC-2: `extract_token_usage(response)` handles `response_metadata['token_usage']` + `usage_metadata` + missing (→ (0,0), never raises).
- [x] AC-3: `refine_translation` emits one `LLM_USAGE_RECORDED` with `_actor_node='refiner'`, `pass='refinement'`, and the refinement call's token counts, when tokens > 0 and job_id present.
- [x] AC-4: engine `_build_usage` + `_call_llm` token capture delegate to the shared helper (DRY; identical records).

Out of scope: aggregating a per-job total event at finalize (consumers sum the events); reflexion-node tokens (reverse_translate — separate, spawn if needed).

## 3. Design
New `app/services/llm_usage.py` holds `extract_token_usage`, `build_usage_record`, and `emit_usage_event` (writes the v2 event). Engine delegates to the first two (shrinks engine 785→759). Refiner captures tokens right after its LLM call (before parse/DB work, so consumption is recorded even if downstream fails) and emits via `emit_usage_event` after the try (A3-wrapped).

**Mega-file fix (not gaming):** the refiner emit pushed `graph.py` past the 800-line ratchet. Extracted the cohesive `build_config_snapshot` (+ its pinned-agents constant) to `app/agents/_config_snapshot.py` — a genuine separation (snapshot builder vs graph wiring). graph.py 803→763. (`draft_translate` + 3 helpers are dead in production but pinned by `test_tm_bypass.py`; removing them needs test migration → spawned TMX-GRAPH-DEADCODE rather than rush it here.)

## 4. Code
| File | Change |
|---|---|
| `app/services/llm_usage.py` | new — `extract_token_usage`, `build_usage_record`, `emit_usage_event` |
| `app/agents/nodes/translation_engine.py` | `_build_usage` + `_call_llm` delegate to the helper (DRY; engine 785→759) |
| `app/agents/graph.py` | refiner captures tokens + emits `LLM_USAGE_RECORDED`; extracted config snapshot (803→763) |
| `app/agents/_config_snapshot.py` | new — extracted `build_config_snapshot` |
| `tests/test_refinement_usage.py` | new — 5 tests (helpers + refiner emit; red-before-green) |

## 5. Test
`pytest tests/test_refinement_usage.py` → 5 passed. A6-2 + budget + graph-timestamp suites green. Ratchet 17/17 (no loosening; config-snapshot extraction kept mega_files green). Full suite — stage 8.

## 6. Red team
- Tokens captured BEFORE parse/DB so a downstream failure can't lose the consumption record; emit is after the try and A3-wrapped.
- Test fake LLM yields 0 tokens, so the emit only fires with real usage — refiner test injects a response with `token_usage` to exercise it.
- DRY refactor verified: existing A6-2 usage tests still pass against the shared helper (identical records).
- `response: object` (not `Any`) in the helper — no ratchet `Any` regression.

## 7. Fix
None beyond the in-loop mega-file extraction. Spawned TMX-GRAPH-DEADCODE (remove `draft_translate` + migrate `test_tm_bypass` to the engine) and TMX-A6-2b-reflexion (capture reverse_translate tokens if material).

## 8. Deploy
- [x] Ruff clean (graph.py retains 2 pre-existing E402) · Ratchet 17/17
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-03T~22:15Z | — | `[Verify]` | Helper + refiner emit + DRY + config-snapshot extraction; 5 tests; ratchet 17/17; awaiting full suite |