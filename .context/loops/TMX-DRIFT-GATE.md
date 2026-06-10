# TMX-DRIFT-GATE — Back-translation semantic drift becomes an enforced review gate

**State**: `[Done]` — `5f04b44` on origin/main
**Owner**: Agent & AI + Quality
**Sprint**: 2 (engine-to-regulatory-grade batch)
**Started**: 2026-06-10
**Reversibility**: `two-way` — additive state fields + a pure helper + a fail-toward-review escalation in `finalize_job`. Changes job *outcome* only in the safe direction (TRANSLATED → IN_REVIEW, never the reverse). Revert = drop the helper + the escalation branch.
**Pre-mortem**: if this fails in production, the failure mode is an over-eager hold (a clean job routed to human review) — annoying, never unsafe. The opposite (a drifted job auto-passing) is the failure we are removing. The helper is pure + A3-wrapped so it cannot crash the pipeline.
**Blast radius**: `app/agents/nodes/reverse_translate.py` (helper + flag in return + print→logger hygiene), `app/agents/graph.py` (TransMaxState +2 fields; `finalize_job` reads the flag), new `tests/test_drift_gate.py`. Sensitive surfaces A2/A3.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (trust + robustness) back-translation drift is already *computed* and stored but never *acted on*; measuring without enforcing is theatre. This turns a measured signal into a gate that holds risky output for a human (A2 deterministic gate, A3 fail-loud). No new dependency; reuses the per-segment `validation_score` the node already produces.
- [x] **G2 Reproduce-the-failure** — today a job whose back-translation diverges badly (low `validation_score`) still finalizes as `TRANSLATED`. A RED test drives a low-score segment through `finalize_job` and asserts `IN_REVIEW`; it fails before the gate exists.
- [x] **G3 Completion** — a job with any genuinely-assessed segment scoring below the threshold finalizes as `IN_REVIEW` with the reason recorded in the audit payload; a clean job is unaffected; no-key/unassessed (score==0.0 sentinel) jobs are NOT falsely held. Proven by `tests/test_drift_gate.py` (6 tests).

---

## 1. Task
`reverse_translate_node` computes per-segment semantic-drift (`calculate_semantic_drift`, 0–100, 100=identical) and an aggregate, but nothing consumes it for routing. Make low back-translation fidelity *enforce* human review. Also retire the `print()` calls in this app module (convention: logger only).

## 2. Spec — acceptance criteria
- [ ] AC-1: pure `assess_reflexion(segments, threshold=REFLEXION_REVIEW_THRESHOLD)` returns `{review_required, min_score, n_assessed, n_below}`; only scores that are `not None` and `> 0.0` count as *assessed* (the `0.0` no-API-key sentinel and `None` are excluded — A3: don't hold on a non-signal).
- [ ] AC-2: `review_required` is True iff at least one assessed score `< threshold` (default 70).
- [ ] AC-3: `reverse_translate_node` returns `reflexion_review_required` + `reflexion_min_score` in its state update (TransMaxState carries both).
- [ ] AC-4: `finalize_job` escalates `final_status` TRANSLATED → IN_REVIEW when `reflexion_review_required`, and records `reflexion_review_required` + `reflexion_min_score` in the JOB_FINALIZED payload (legacy + v2). Never downgrades an already-held status.
- [ ] AC-5: no `print(` remains in `app/agents/nodes/reverse_translate.py` (logger instead).

Out of scope: changing `calculate_semantic_drift`'s `0.0`-on-no-key contract (2 callers — separate ticket TMX-DRIFT-SENTINEL); per-tenant threshold config (uses a module constant for now).

## 3. Design
`assess_reflexion` is pure and lives beside the node. The node sets the flags into state; `finalize_job` reads them — no new edge, no re-entry into `gates` (reflexion already runs immediately before finalize). Escalation is one-directional (only TRANSLATED→IN_REVIEW), so it composes with the existing BLOCKED/REVIEW_REQUIRED status without fighting it. Threshold is a named module constant (`REFLEXION_REVIEW_THRESHOLD = 70.0`) so it is one edit away from per-tenant config later.

The `0.0`-sentinel exclusion is the load-bearing safety choice: `calculate_semantic_drift` returns `0.0` when no API key, indistinguishable from a real catastrophic score. Holding every keyless job would be a false-positive flood, so `> 0.0` is required to count. Documented as a known caveat with a follow-up (TMX-DRIFT-SENTINEL) to make the method return `None` on no-key.

Rejected: routing reflexion back into `gates` (would re-run the whole quality pass + risk an infinite refine loop); hard-BLOCK on drift (a single embedding wobble should pause for a human, not fail the job — A3 fail-toward-review, not fail-hard).

## 4. Code
| File | Change |
|---|---|
| `app/agents/nodes/reverse_translate.py` | +`REFLEXION_REVIEW_THRESHOLD`, +`assess_reflexion`, set flags in return, `print`→`logger` |
| `app/agents/graph.py` | TransMaxState +`reflexion_review_required`/`reflexion_min_score`; `finalize_job` escalation + payload |
| `tests/test_drift_gate.py` | new — AC-1..AC-5 |

## 5. Eval / Test
```
tests/test_drift_gate.py  → 6 passed
  - assess_reflexion: flags low score; clean job not held; excludes 0.0 + None;
    threshold-boundary is inclusive-pass
  - finalize escalates PASS→HELD on drift (+ records reason); clean job stays PASS
  - hygiene: no print( in reverse_translate.py
tests/test_parallel_reflexion.py → still green (returned-dict flags don't disturb its asserts)
Full suite: 1085 passed, 2 skipped, 0 failed
Ratchet: 17/17; print_in_app count DROPPED (removed 7 prints) — net entropy win
```

## 6. Red team
- A3 direction: the gate only escalates TRANSLATED→IN_REVIEW (one-way); it can never auto-pass or downgrade a BLOCKED/REVIEW_REQUIRED job. Worst case is an over-cautious hold, never an unsafe pass.
- A2: drift is a measured deterministic signal consumed at finalize; no new LLM call, no creativity in the gate.
- Sentinel trap: `calculate_semantic_drift` returns `0.0` with no API key — excluded via `> 0.0` so keyless/test jobs aren't falsely held. **Documented caveat**: a genuine 0.00 cosine (implausible for natural language) would also be skipped — follow-up **TMX-DRIFT-SENTINEL** to return `None` on no-key and tighten this.
- No infinite loop: reflexion runs once, immediately before finalize; the gate does not re-enter `gates`/`refine`.
- Not claimed: per-tenant thresholds (module constant for now); drift isn't a hard BLOCK (intentional — pause for a human, not fail the job).

## 7. Fix
Replaced 7 `print()` calls with `logger` in the same module (in-scope hygiene; reduces the `print_in_app` ratchet). `Dict[str, object]` on the new helper to keep `any_annotations` flat. No other change.

## 8. Deploy
- [x] Commit: `5f04b44` (bundled with TMX-3213)
- [x] Pushed to origin/main (Railway auto-deploys) — authorized under Kapil's two-way-safe auto-deploy model
- [x] SHA recorded here + in `.context/active_tasks.md`

---
## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-10 | — | `[Spec]` | Created as part of the engine-to-regulatory-grade batch |
| 2026-06-10 | `[Spec]` | `[Done — pending SHA record]` | Implemented + tested; full suite green; ratchet clean; 7 prints removed. Awaiting commit SHA. |
