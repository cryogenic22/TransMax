# TMX-ROUTER-1 — Model capability registry + select_model policy

**State**: `[Verify]`  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  **Started/Closed**: 2026-06-03
**Reversibility**: `two-way` — new pure module, nothing wired to it yet (ROUTER-2 integrates). Revert by deleting the file.
**Pre-mortem**: if the policy/quality scores are wrong, the router would pick a sub-optimal model — but nothing calls it yet, and ROUTER-2 records the choice + reason in the audit chain so it's reviewable. No runtime impact this loop.
**Blast radius**: `app/core/model_registry.py` (new) only. No behaviour change (not imported by app code yet).

**Gates**: G1 — foundation for the LLM router the Programme Lead explicitly requested (task/complexity/cost-aware model selection); reuses the pricing-registry model ids; pure + tested; not speculative. G2 — N/A (greenfield). G3 — `select_model` returns a costable model id for every task/complexity.

## 1. Task
Build the brain of the LLM router: per-model capability metadata (tier/quality/provider/context) + a pure, config-driven `select_model(task, complexity, budget_posture)` policy. Pricing answers "what does it cost"; this answers "which model for this task". Addenda: A6 (the choice is qualified-supplier provenance — recorded in ROUTER-2), config-not-branching (policy is a data table), A3 (every selectable model is costable).

## 2. Spec — acceptance criteria
- [x] AC-1: every registered model is in the pricing registry (`cost_for` doesn't raise) — enforced by test.
- [x] AC-2: `model_for_tier` returns the highest-quality registered model of a tier.
- [x] AC-3: `select_model` maps (task, complexity) → model per `_POLICY`: translate/high→frontier(gpt-4o), translate/low→cheap(mini), review/*→frontier, detect/*→cheap, refine→balanced.
- [x] AC-4: `budget_posture="constrained"` downgrades one tier (floored at cheap) — cost-aware selection (ties to TMX-BUDGET-1).
- [x] AC-5: accepts enum or string task/complexity; unlisted combos default to balanced.

Out of scope (→ later loops): wiring into `get_llm` + recording the choice (ROUTER-2); per-tenant DB-backed policy (ROUTER-3); UI (ROUTER-4); using live budget telemetry to set `budget_posture` (ROUTER-5).

## 3. Design
`ModelSpec` (model_id, provider, tier, quality 0-100, max_context). Registry: gpt-4o-mini=cheap(72), gpt-4-turbo-preview=balanced(85), gpt-4o=frontier(90). `_POLICY` is a `(Task, Complexity) → ModelTier` data table (config-not-branching); `select_model` resolves tier→highest-quality model, applying a one-step downgrade when budget-constrained, with a costable fallback. Pure + deterministic — ROUTER-2 wires the result into the LLM gateway + audit snapshot.

## 4. Code
| File | Change |
|---|---|
| `app/core/model_registry.py` | new — `ModelSpec`, `ModelTier`/`Task`/`Complexity` enums, `_REGISTRY`, `_POLICY`, `select_model`, `model_for_tier`, `get_spec`, `registered_models` |
| `tests/test_model_registry.py` | new — 11 tests (pricing-sync, tier resolution, policy matrix, budget downgrade, string coercion) |

## 5. Test
`pytest tests/test_model_registry.py` → 11 passed. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Quality scores are judgement calls; documented + easily tuned; nothing depends on them yet. The pricing-sync test prevents the dangerous failure (router picks an uncostable model).
- Policy is data — ROUTER-3 lifts it to per-tenant config without touching callers.
- `budget_posture` is plumbed but not yet fed by live budget (ROUTER-5); default "normal" keeps current behaviour.

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 11 tests
- [ ] Commit / push (after full suite)

### Epic roadmap (LLM Router + Config)
- **ROUTER-2** — `get_llm(task, complexity)` resolves via `select_model` at the 11 call sites; record chosen model + reason in the audit snapshot (A6/A8).
- **ROUTER-3** — per-tenant `routing_policy` table + RBAC-gated, audited CRUD; router reads the active policy.
- **ROUTER-4** — `/workspace/settings/models` UI: capability+cost view, edit policy, per-tenant overrides (frontend loop).
- **ROUTER-5** — feed live TMX-BUDGET-1/A6-2 telemetry into `budget_posture` (downgrade tier as a job's budget depletes).

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-03T~23:00Z | — | `[Verify]` | Registry + policy + 11 tests; ratchet 17/17; awaiting full suite |