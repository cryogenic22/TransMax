# TMX-MQM-ENSEMBLE-RUN — multi-judge ensemble shadow runner (most-severe + disagreement escalation)

**State**: `[WIP]`
**Owner**: Agent & AI
**Sprint**: MQM Keystone / Phase 1→2
**Started**: 2026-06-15
**Closed**: —
**Reversibility**: `two-way` (additive shadow node behind a default-OFF flag; revertable by removing the function + flag + the one graph call line)
**Pre-mortem**: if this fails in production, the failure mode is *an "ensemble" that is really one model agreeing with itself, presented as independent corroboration* — guarded by an explicit `single_lineage` honesty flag in the payload + the inter-judge κ (which is ~1.0 under single lineage, surfacing the caveat numerically).
**Blast radius**: `app/agents/nodes/mqm_shadow.py` (new `run_ensemble_shadow`), `app/core/config.py` (2 flags), `app/agents/graph.py` (1 call), `app/services/mqm_judge.py` (honest per-judge model provenance). No live verdict; extra LLM calls only when the flag is on.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: nothing today runs the judge >1× and combines; the pure `aggregate_ensemble` helper (TMX-MQM-6) was built to be consumed and has no caller; (b) <5 callers; (c) backend, no bundle; (d) reuses `judge_segments` + `aggregate_ensemble` + `score` + `emit_v2_audit_event` + `cohen_kappa` — composition only, zero new scoring/aggregation logic; (e) ships with tests.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield runner).
- [ ] **G3 Completion** — the runner calls the judge N× and combines via the existing helper; emits a durable `MQM_ENSEMBLE_SHADOW` event; default-OFF; no verdict change.

---

## 1. Task

Build the ensemble runner the pure `aggregate_ensemble`/`enforce_conservation` primitives (TMX-MQM-6) were pre-built for. It runs the independent judge N times, merges per span taking the **most severe** severity (never averaged — averaging manufactures vacuous green, §6.4), escalates on disagreement, scores the merged annotation set through the **one** engine, and records the result + an honest single-lineage caveat to the audit chain — all in **shadow** (no verdict), default-OFF.

Addenda: **A1** (ensemble evidence to the chain), **A2** (engine remains the sole scorer; the ensemble only shapes annotations), **A3** (honest about single-model self-agreement; fail-safe), **A6** (each judge's real resolved model recorded).

## 2. Spec — acceptance criteria

- [ ] AC-1: `run_ensemble_shadow(state)` is async + fully fail-safe (never raises, never changes a verdict) and returns `None` when `mqm_ensemble_shadow_enabled` is False.
- [ ] AC-2: With the flag on, it calls `judge_segments` `mqm_ensemble_size` times (≥2; distinct `judge_id`s), collects `List[List[MqmAnnotation]]`, and combines via `mqm_review.aggregate_ensemble` — it does NOT re-implement merging and does NOT average.
- [ ] AC-3: It scores `result.merged` through `mqm_engine.score` **once** (engine is the sole pass/fail authority) — the ensemble never computes its own verdict.
- [ ] AC-4: It emits a `MQM_ENSEMBLE_SHADOW` v2 event carrying `num_judges`, `merged_annotation_count`, `escalate`, `disagreement_count`, `ensemble_mqm` (score dict), `single_lineage` (True when the router is off ⇒ all judges share one model), `models` (each judge's resolved model), and `inter_judge_kappa` (via `cohen_kappa`, TMX-MQM-EVAL-KAPPA).
- [ ] AC-5: `escalate` is surfaced as a SEPARATE signal (like `insufficient_sample`), never folded into the quality verdict.
- [ ] AC-6: `judge_segments` records each judge's REAL resolved model (`resolve_model(task="judge")`) so provenance does not lie when routing flips (A6) — a surgical fix that also corrects the single-judge path.
- [ ] AC-7: Wired into the gate node next to `run_judge_shadow`; existing tests green.

Out of scope: the live revise loop + `enforce_conservation` wiring (that is **TMX-MQM-6-wire**, tied to the cutover); flipping the ensemble to drive the verdict (post-cutover, gated).

## 3. Design

`run_ensemble_shadow` is `run_judge_shadow` generalised from 1 to N judges. Honest model-independence: with `enable_llm_router=False`, `get_llm(task="judge")` returns the same model for every judge, so the "ensemble" is single-lineage self-consistency — we record `single_lineage=True` and the inter-judge κ (≈1.0 under single lineage) rather than pretending corroboration. When a 2nd in-boundary lineage is validated and the router flips, the SAME code becomes a true ensemble with zero changes here (ADR-0007 review condition 1).

`aggregate_ensemble` keeps the single most-severe annotation per span, so the surviving annotation's provenance is one judge's; the multi-judge view lives in `disagreements`. We do not try to merge provenance — the disagreements list + per-judge `models` are the audit trail.

Alternatives rejected: (a) a new module — rejected, `run_judge_shadow` is the template and mqm_shadow.py is the home; (b) averaging severities / majority vote — rejected, `aggregate_ensemble` already encodes most-severe + escalate (reuse, don't fork); (c) hardcoding a 2nd model name for "real" independence — rejected (A6/A8 violation); independence is the router's job.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/config.py` | ~102 | `mqm_ensemble_shadow_enabled: bool = False` + `mqm_ensemble_size: int = 2` |
| `app/services/mqm_judge.py` | ~149 | record each judge's real `resolve_model(task="judge")` (A6) |
| `app/agents/nodes/mqm_shadow.py` | +~55 | new `run_ensemble_shadow(state)` |
| `app/agents/graph.py` | ~428 | `await run_ensemble_shadow(state)` next to the judge shadow |
| `tests/test_mqm_ensemble_run.py` | new | disabled→None; N judges merged; escalate on disagreement; single_lineage flag; never-raises |

## 5. Eval / Test

```
python -m pytest tests/test_mqm_ensemble_run.py -q
```
```
6 passed — disabled→None; agreeing judges merge w/o escalation (κ_first_pair=1.0);
disagreement escalates + κ_first_pair=0.0; size clamp ≥2; never-raises on judge
failure; no-translated-segments→None. Full MQM/judge regression: 202 passed.
```

## 6. Red team

4-lens adversarial review (workflow `wn9n1w41k`). Correctness lens confirmed: scores via the engine exactly once, never averages severities, escalate is a separate signal, clamp `min(5,max(2,…))` safe for 0/neg/huge/non-int. Safety lens confirmed the gate-node `except` is unreachable from the shadow (each call is internally fail-safe). **Honesty lens found two narrower-than-named issues:** `inter_judge_kappa` was computed first-pair-only but named generically; `single_lineage` fell back to the router flag when no model was observed.

## 7. Fix

Renamed the field → `inter_judge_kappa_first_pair` + added `kappa_pair: ["judge-a","judge-b"]` so the metric's scope matches its name. `single_lineage` now reports `None` (unknown) when no judge produced an annotation, rather than asserting independence from the router flag alone (A3). Re-ran: green.

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [ ] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created; consumes the unwired TMX-MQM-6 `aggregate_ensemble` + TMX-MQM-EVAL-KAPPA `cohen_kappa`; shadow + default-OFF |
