# TMX-ROUTER-2 — Wire the router into get_llm + record the model choice

**State**: `[Verify]`  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  Loop 5/10 (2026-06-04 batch)
**Reversibility**: `two-way` — opt-in, **default-off** (`enable_llm_router=False`). When off, every task uses `default_gpt_model` (pre-router behaviour) ⇒ zero production change.
**Pre-mortem**: if routing picked a model the deployment's key can't access, translate would 404 (the live Railway incident) — averted by the default-off flag: routing engages only when the operator confirms the registry matches available models.
**Blast radius**: `app/core/config.py` (+flag), `app/services/llm.py` (rewrite: `resolve_model` + task-aware `get_llm` + per-model cache), `translation_engine.py` / `graph.py` (refine) / `reverse_translate.py` (each requests its task's model + records it in usage).

## 1. Task
Make the ROUTER-1 brain actually drive model selection: `get_llm(task, complexity)` resolves a model via `select_model` when routing is enabled, and the qualified-supplier usage telemetry (A6) records the **routed** model id. Keep it opt-in so production is unchanged until enabled. Addenda A6 (provenance of the model that ran), A8, config-not-branching.

## 2. Spec
- [x] AC-1: `resolve_model(task, complexity)` returns `select_model(...)` when `enable_llm_router` is on + a task is given; else `default_gpt_model` (incl. when no task).
- [x] AC-2: `get_llm(task, complexity)` constructs the resolved model (verified via a captured `ChatOpenAI` stub); caches per model; non-live mode returns the deterministic fake.
- [x] AC-3: the three LLM passes request their task — translate→`translate`, refine→`refine`, reflexion(back-translation)→`review` — and their `LLM_USAGE_RECORDED` events record the routed model.
- [x] AC-4: default-off ⇒ all existing usage tests (model == default_gpt_model) still pass unchanged.

Out of scope: deriving `complexity` from segment signals (fixed `medium`/`low` for now → ROUTER-5/later); per-tenant policy (ROUTER-3); recording the per-task routing map in the JobConfigSnapshot (the per-usage `model` field is the A6 evidence; snapshot enrichment is a follow-up).

## 3. Design
`llm.py` becomes the routing chokepoint: `resolve_model` gates on the flag; `get_llm` builds/caches per resolved model (one fake under `__fake__` for tests). Consumers pass their task to BOTH `get_llm(task=…)` (so the routed model runs) and `resolve_model(task=…)` (so usage records it). Engine stores `self._model = resolve_model("translate")`; refine/reflexion compute it inline at emit. `reset_llm_cache_for_test` added.

## 4. Code
| File | Change |
|---|---|
| `app/core/config.py` | +`enable_llm_router: bool = False` |
| `app/services/llm.py` | rewrite: `resolve_model`, task-aware `get_llm`, per-model cache, `reset_llm_cache_for_test` |
| `app/agents/nodes/translation_engine.py` | `get_llm(task="translate")` + `self._model`; usage uses `self._model` |
| `app/agents/graph.py` | refine: `get_llm(task="refine")` + usage `resolve_model("refine")`; dropped now-unused `settings` import |
| `app/agents/nodes/reverse_translate.py` | `get_llm(task="review")` + usage `resolve_model("review")`; dropped unused `settings` import |
| `tests/test_llm_router_wire.py` | new — 4 tests (resolve off/on, get_llm routed model on/off) |
| `tests/test_reflexion_usage.py` | get_llm monkeypatch lambdas now accept `task` kwarg |

## 5. Test
`pytest test_llm_router_wire + usage + reflexion + budget` → 19 passed. Ratchet 17/17. Full suite — stage 8. Red-team caught: the reflexion test's zero-arg `get_llm` lambda broke when the call gained `task=` → fixed to `*a, **k`.

## 6. Red team
- **Default-off safety** = the whole point: prevents routing to an inaccessible model (the gpt-4-turbo-preview 404). Verified existing usage tests (model==default) still pass.
- Per-model cache replaces the old single `_llm` singleton; `reset_llm_cache_for_test` lets tests re-resolve after a settings change. The fake path is byte-identical to before (one cached fake).
- Reflexion mapped to `review` (verification) — frontier when routed; cost-tunable via the policy (ROUTER-3/UI). Documented.
- Complexity is fixed (`medium`) for now; ROUTER-5 will derive it + feed budget posture.

## 7. Fix
Removed now-unused `settings` imports (graph.py, reverse_translate.py); fixed the reflexion-test lambdas. No other findings.

## 8. Deploy
- [x] Ruff clean (2 pre-existing E402 only) · Ratchet 17/17
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-ROUTER-2a** — enrich the JobConfigSnapshot with the per-task routing map when the router is on (A8 reproducibility).

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~01:30Z | — | `[Verify]` | router wired (opt-in) + usage records routed model; 19 tests; ratchet 17/17; awaiting full suite |