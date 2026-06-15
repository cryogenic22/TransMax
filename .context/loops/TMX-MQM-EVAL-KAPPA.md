# TMX-MQM-EVAL-KAPPA — judge↔rater agreement (Cohen's κ) primitive + durable per-segment judge labels

**State**: `[Done]`
**Owner**: Quality & Regulatory
**Sprint**: MQM Keystone / Phase 2 (judge reliability)
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (pure additive metric + a wider audit payload; revertable by deleting the new symbols and narrowing the payload)
**Pre-mortem**: if this fails in production, the failure mode is *a κ number that looks authoritative but is computed over a biased/insufficient label set* — guarded by an explicit `insufficient` flag (A3, never fabricate agreement).
**Blast radius**: `app/services/judge_eval.py` (new pure functions), `app/agents/nodes/mqm_shadow.py` (widen the `MQM_JUDGE_SHADOW` payload with per-segment labels). No live verdict. New tests only otherwise.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) the κ metric is the measurement that makes the vision's "judge↔human κ ≥ 0.80" claim *checkable* — net-new capability, not an extension of recall; (b) <5 callers; (c) no bundle impact (backend); (d) reuses `JudgeReliability` dataclass style + `MqmAnnotation`/`DefectSeverity`; (e) ships with tests that fail without it. Inter-judge κ gets an immediate caller in TMX-MQM-ENSEMBLE-RUN, so the primitive is not dangling.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield metric, not a bug).
- [ ] **G3 Completion** — κ primitive computes correct values on known fixtures; judge labels become durable in the audit chain.

---

## 1. Task

The independent judge (TMX-MQM-4) must be *measured like a model*. Recall/precision over planted Criticals exists (TMX-MQM-EVAL); the missing reliability axis is **inter-rater agreement** — Cohen's κ between two raters (judge↔judge for ensemble consistency now; judge↔human for calibration once structured human labels land). This loop ships the **pure κ primitive** and makes the judge's **per-segment labels durable** in the `MQM_JUDGE_SHADOW` audit event so a future judge↔human join is possible.

Addenda at play: **A1** (judge labels become first-class audit evidence), **A2** (measurement lives beside the judge metric, not in the gate), **A3** (no fabricated agreement — `insufficient` is explicit), **A6** (per-segment provenance preserved).

## 2. Spec — acceptance criteria

- [ ] AC-1: `cohen_kappa(labels_a, labels_b)` is pure (no LLM/DB), inner-joins the two raters on shared item keys, and returns a `KappaResult(n_items, observed_agreement, expected_agreement, kappa, categories)`.
- [ ] AC-2: κ math is correct on known fixtures — perfect agreement → κ=1.0; chance-level agreement → κ≈0.0; systematic disagreement → κ<0.
- [ ] AC-3: Degenerate cases are honest (A3): zero shared items → `kappa=None` (not 0, not 1); single-category-with-full-agreement → `kappa=1.0`; single-category-with-disagreement → `kappa=0.0`. No `NaN`/`Infinity` ever escapes.
- [ ] AC-4: A `binary_severity_label_map(segment_ids, critical_segment_ids)` helper builds `{segment_id: "CRITICAL"|"OK"}` over a KNOWN segment universe (so unflagged segments are "OK", not absent — otherwise the join is biased).
- [ ] AC-5: `run_judge_shadow`'s `MQM_JUDGE_SHADOW` payload carries `judge_segment_labels: [{segment_id, severity, dimension}]` (strings only — canonical-JSON safe) so the per-segment judge verdict is recoverable from the chain. Aggregate counts unchanged.
- [ ] AC-6: New + existing MQM/judge tests green; no live verdict changes.

Out of scope for this ticket: the judge↔**human** κ join end-to-end — it needs a structured human MQM label, which needs the deferred `mqm_annotations` table (**TMX-MQM-1a**). That join is the follow-up **TMX-MQM-EVAL-KAPPA-JOIN** (spawned). Fleiss' κ (≥3 raters) deferred until a 3rd rater exists.

## 3. Design

Cohen's κ = (p_o − p_e) / (1 − p_e), p_o = observed agreement over the inner-join of items both raters labeled, p_e = Σ_c P_a(c)·P_b(c) over categories. Convention for (1−p_e)=0: κ=1.0 iff p_o=1.0 else 0.0. n=0 → κ=None + the result is flagged degenerate. Labels are arbitrary category strings; callers build them from annotations via the helper. Severities/dimensions stored as `.value` strings in the payload (the map flagged float/NaN canonical-JSON rejection).

Alternatives rejected: (a) reuse `compute_judge_reliability` and bolt κ onto it — rejected, different shape (recall is over planted ids, κ is over a shared universe); separate pure function, same module. (b) persist judge labels in a new table — rejected, would pre-empt TMX-MQM-1a and fork storage; the v2 chain already carries the event, so widening its payload is the single-source-of-truth move. (c) compute judge↔human κ now over `ChangeLog` free-text edits — rejected, edits are not MQM severities (A3 would be violated by inventing a severity).

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/judge_eval.py` | +~40 | `KappaResult` dataclass + `cohen_kappa()` + `binary_severity_label_map()` |
| `app/agents/nodes/mqm_shadow.py` | ~146 | widen `MQM_JUDGE_SHADOW` payload with `judge_segment_labels` |
| `tests/test_judge_kappa.py` | new | κ math + degenerate cases + binary label helper |
| `tests/test_mqm_shadow.py` | +1 | assert the widened payload carries per-segment labels |

## 5. Eval / Test

```
python -m pytest tests/test_judge_kappa.py tests/test_mqm_shadow.py -q
```
```
7 (kappa) + shadow tests pass; full MQM/judge regression 202 passed, 0 failed.
```
κ math fuzzed against `sklearn.metrics.cohen_kappa_score` by the red team over 2000 random cases — zero true mismatches (only 3rd-decimal banker's-rounding deltas; unrounded values identical). Pinned cases verified: perfect→1.0, chance→0.0, systematic flip→−1.0, n=0→None.

## 6. Red team

4-lens adversarial review (workflow `wn9n1w41k`). Honesty lens confirmed κ=None for n=0 serialises to JSON `null` and is never coerced. **Reconcile lens found a real anti-bloat defect:** `severity_label_map` had NO caller (the ensemble uses `binary_severity_label_map`) and forked `_SEVERITY_RANK` (byte-identical to `mqm_review.py`'s) — a G1 + Tier-0 SSOT violation.

## 7. Fix

Deleted `severity_label_map` + the duplicated `_SEVERITY_RANK` + its test (the binary helper needs no severity ranking; removal breaks nothing). If a most-severe-per-segment collapse is needed by the future judge↔human join, it lands THEN with a real caller, importing the canonical `_SEVERITY_RANK`. Re-ran: green.

## 8. Deploy

- [x] Commit: `6536939` (batch w/ ENSEMBLE-RUN + EVAL-CI)
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created from the next-10 resume batch; κ primitive + durable judge labels; human join deferred to TMX-MQM-1a |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `6536939`; red team deleted the dangling `severity_label_map`; spawned TMX-MQM-EVAL-KAPPA-JOIN |
