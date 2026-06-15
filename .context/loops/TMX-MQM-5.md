# TMX-MQM-5 — graph rewire: MQM engine shadow (phase a) → cutover (phase b)

**State**: phase-a (shadow) `[Done, pending push]` · phase-b (cutover) `[READY]`
**Owner**: Agent & AI / Quality & Regulatory
**Sprint**: MQM Keystone (Phase 1)
**Started**: 2026-06-14
**Reversibility**: phase-a `two-way` (observational, changes no verdict). phase-b `one-way` (flips the authority of record) — gated on the shadow diff.
**Pre-mortem**: if phase-a fails it logs a warning and the live verdict is untouched (the shadow is wrapped fail-safe); the real risk is in phase-b, which is why it waits for the diff.
**Blast radius**: phase-a adds one fail-safe call at the end of `run_quality_gates` (`app/agents/graph.py`) + a thin node module + 3 config flags. No verdict change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — reuses the MQM engine + profile registry; the shadow is the prerequisite for the safe cutover (review cond. 4); ships with tests.
- [x] **G2 Reproduce-the-failure** — N/A.
- [x] **G3 Completion** — the engine now scores live traffic in shadow and logs the legacy-vs-MQM diff; phase-b is explicitly deferred until that diff is reviewed.

---

## 1. Task
Make the pure MQM engine the platform's quality decider — but **shadow-first** (review cond. 4): phase-a runs the engine alongside the legacy `evaluate_verdict` and logs the comparison, changing no verdict; phase-b (later) flips `mqm_engine_enabled` per tenant to make the engine authoritative, strips the translator's self-certification, and converts the deterministic gates into annotation producers. Reconciles the scorer fork (`ConfidenceService`, SDK) only at phase-b, after the diff. Addenda: A2 (deterministic quality at gates), A3 (fail-safe shadow).

## 2. Spec — acceptance criteria (phase a)
- [x] AC-1: after the gate node computes `status`/`violations`, the same violations are scored through `score_from_violations` against a resolved metric profile and logged as `MQM_SHADOW ...`.
- [x] AC-2: the shadow changes NO verdict and NEVER raises (wrapped fail-safe; a failure logs a warning).
- [x] AC-3: gated by `settings.mqm_shadow_enabled` (default on, observational); `mqm_engine_enabled` (default off) reserved for phase-b; `mqm_default_profile` selects the profile until content→profile resolution (TMX-MQM-5c).
- [x] AC-4: the shadow logic lives outside `graph.py` (`app/agents/nodes/mqm_shadow.py`) so the gate node stays thin.

Out of scope (→ phase b / follow-ups): the verdict cutover, stripping self-cert, gates→annotators, `ConfidenceService`→adapter, SDK-fork unification, content→profile resolution (TMX-MQM-5c), emitting the shadow diff to the v2 chain (TMX-MQM-5a-emit).

## 3. Design
Strangler-fig: observe before cutover. `resolve_metric_profile` is a documented reconciliation seam returning the configured default; it is where the two legacy profile systems will wire in (TMX-MQM-5c). EWC = source words across translated segments. Rejected: hard cutover now (cond. 4 — would change every legacy caller's distribution unseen).

## 4. Code
| File | Change |
|---|---|
| `app/core/config.py` | +mqm_shadow_enabled / mqm_engine_enabled / mqm_default_profile |
| `app/agents/nodes/mqm_shadow.py` | new — resolve_metric_profile + run_mqm_shadow (fail-safe) |
| `app/agents/graph.py` | gate node calls run_mqm_shadow after the verdict (in-function import) |
| `tests/test_mqm_shadow.py` | new — 4 tests |

## 5. Eval / Test
```
python -m pytest tests/test_mqm_shadow.py -q  → 4 passed
# regression: gate/graph/review suites + all MQM tests → 81 passed
```

## 6. Red team
Risk: shadow throwing inside the gate node — double-wrapped (helper try/except + the node's own try). Risk: shadow altering the verdict — it only reads state + legacy_status and returns a dict; the gate node ignores the return. Risk: wrong default profile skewing the diff — documented; phase-b reads the real diff before trusting it. Risk: log volume — one INFO line per gate run (acceptable; can be sampled later).

## 7. Fix
No findings — clean.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill>
- [ ] Pushed to origin/main: **gated on Kapil** (branch `feat/mqm-keystone`)
- [x] `.context/active_tasks.md` updated

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-14 | — | phase-a `[Done, pending push]` | shadow live; phase-b cutover awaits diff review |
