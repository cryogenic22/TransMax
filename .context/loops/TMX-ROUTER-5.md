# TMX-ROUTER-5 — Cost-aware routing (budget posture into model selection)

**State**: `[Verify]`  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  Loop 6/10 (2026-06-04 batch)
**Reversibility**: `two-way`. No-op unless `enable_llm_router` AND a per-job budget are configured.
**Blast radius**: `app/services/budget_guard.py` (+`budget_posture`, `JobBudget.from_settings`), `app/services/llm.py` (`resolve_model`/`get_llm` accept `budget_posture`), `app/agents/graph.py` (refine), `app/agents/nodes/reverse_translate.py` (reflexion).

## 1. Task
Close the "…and cost consideration" part of the router ask: as a job's consumption nears its TMX-BUDGET-1 ceiling, the router downgrades the model tier one step (cheaper model) for the remaining passes. Addenda A3 (cost control), config-not-branching.

## 2. Spec
- [x] AC-1: `budget_posture(tokens, cost, budget)` → `"constrained"` at ≥80% of either limit, else `"normal"`; disabled budget ⇒ always `"normal"`.
- [x] AC-2: `JobBudget.from_settings()` reads the opt-in per-job limits.
- [x] AC-3: `resolve_model`/`get_llm` accept `budget_posture`, passed to `select_model` (which downgrades one tier when constrained).
- [x] AC-4: refine + reflexion compute posture from the consumption so far (`quality_report.usage`) and pass it.
- [x] AC-5: routing off ⇒ posture ignored (default model); no behaviour change.

Out of scope: deriving translate-pass complexity from segment signals; constraining the engine's initial translate model mid-batch (the engine resolves once at start — downstream passes are where posture applies). 

## 3. Design
Pure `budget_posture` in budget_guard (threshold 0.8). `resolve_model`/`get_llm` gain a `budget_posture` arg threaded to `select_model`'s existing downgrade logic (ROUTER-1). The refine + reflexion nodes read the running `quality_report.usage` (translate/refine consumption captured by A6-2/A6-2b) + `JobBudget.from_settings()` to compute posture, then resolve/request their model with it. The first (translate) pass stays `normal` (no usage yet). `from_settings` keeps graph.py free of a direct settings import.

## 4. Code
| File | Change |
|---|---|
| `app/services/budget_guard.py` | +`budget_posture()`; +`JobBudget.from_settings()` |
| `app/services/llm.py` | `resolve_model`/`get_llm` accept + thread `budget_posture` |
| `app/agents/graph.py` | refine computes posture from usage; passes to `get_llm` + `resolve_model` |
| `app/agents/nodes/reverse_translate.py` | reflexion computes + passes posture |
| `tests/test_budget_posture.py` | new — 6 tests (thresholds, from_settings, constrained downgrade, router-off no-op) |

## 5. Test
`pytest posture + router + budget + reflexion` → 19 passed. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- No-op safety: disabled budget OR router-off ⇒ `normal`/default (verified). Zero prod change while flags off.
- Posture uses consumption-so-far from the report — refine sees translate usage, reflexion sees translate(+refine) — a monotonic signal; good enough to trigger a downgrade as budget depletes.
- Threshold 0.8 is a sensible default; tunable later (could move to settings).

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean (2 pre-existing E402) · Ratchet 17/17 · 19 tests
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~02:00Z | — | `[Verify]` | posture helper + threaded into router + refine/reflexion; 6 new tests; ratchet 17/17; awaiting full suite |