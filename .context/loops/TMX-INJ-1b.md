# TMX-INJ-1b — INJECTION_DETECTED audit event

**State**: `[Verify]`  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  **Started/Closed**: 2026-06-03
**Reversibility**: `two-way` — additive emit in the node. Revert by deleting the block.
**Pre-mortem**: if it fails, an injection breach would be flagged as a quality violation but not chained — degrades to TMX-INJ-1 behaviour (still BLOCKED, just no dedicated audit event). A3-wrapped: never blocks the job.
**Blast radius**: `app/agents/nodes/translation_engine_node.py` only. No schema.

**Gates**: G1 — A1 (audit-by-default): an attempted hijack of the qualified-supplier call is security evidence that belongs in the immutable chain, not just the quality report. G2 — N/A (additive); node-emit test red-before-green. G3 — an injected segment leaves an `INJECTION_DETECTED` event in the v2 chain.

## 1. Task
TMX-INJ-1 surfaces prompt-injection as a `PROMPT_INJECTION` quality violation, but that is not chained audit evidence. When the gate fires, emit a chained `INJECTION_DETECTED` v2 event (A1). Addenda: A1 (audit-by-default), A3 (audit emit never blocks the job), A6 (protects the supplier call).

## 2. Spec
- [x] AC-1: a report containing ≥1 `PROMPT_INJECTION` violation ⇒ exactly one `INJECTION_DETECTED` event for the job.
- [x] AC-2: payload carries `count`, `segment_ids`, `messages` (capped at 50), `_actor_node="translator"`.
- [x] AC-3: a clean report emits no event.
- [x] AC-4: emit is A3-wrapped (failure logged, never propagated).

## 3. Design
The node already emits `LLM_USAGE_RECORDED` + `BUDGET_EXCEEDED` from the report. Violations (incl. `PROMPT_INJECTION`) flow into `report["violations"]` via the engine's per-segment gate → `_build_quality_report`. So the node filters violations by `category == PROMPT_INJECTION` and emits `INJECTION_DETECTED`, same A3-wrapped pattern. No new chokepoint.

## 4. Code
| File | Change |
|---|---|
| `app/agents/nodes/translation_engine_node.py` | +`DefectCategory` import; +INJECTION_DETECTED emit block |
| `tests/test_injection_guard.py` | +2 node-emit tests (injected ⇒ event; clean ⇒ none) |

## 5. Test
`pytest tests/test_injection_guard.py` → 31 passed (was 29). Full suite 958 passed / 0 failed. Ratchet 17/17.

## 6. Red team
- Detection via report category is decoupled from the (pre-existing, case-mismatched) `blocked` flag, so it fires regardless. **Spotted pre-existing bug:** the engine's `blocked` flag checks lowercase `'critical'` while severities are uppercase `'CRITICAL'`, so CRITICAL defects don't auto-set `blocked` via that line → **spawned TMX-QG-SEVCASE**.
- Payload capped at 50 segment_ids/messages to bound event size.
- A3-wrapped: an audit-writer failure never blocks translation.

## 7. Fix
None. Spawned TMX-QG-SEVCASE (pre-existing severity-case bug) + carries TMX-INJ-1a (normalise/expand corpus) from the parent.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · Full suite 958/0
- [ ] Commit / push

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-03T~22:00Z | — | `[Verify]` | Emit + 2 node tests; full suite 958/0; awaiting commit |