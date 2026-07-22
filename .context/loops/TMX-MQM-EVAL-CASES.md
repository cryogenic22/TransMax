# TMX-MQM-EVAL-CASES — planted-defect judge fixtures + recall gate

**State**: `[Done]` · **Owner**: Quality & Regulatory · **Sprint**: Phase 2 seed (E13.S2)
**Reversibility**: `two-way` (additive data + test). **Pre-mortem**: none. **Blast radius**: new `tests/evals/judge/planted_critical.jsonl` + test.

**Gates**: G1 ✓ (seeds the judge gold set with real planted-defect cases; reuses `compute_judge_reliability`) · G2 N/A · G3 ✓ (demonstrates the leniency-drift recall gate over fixtures).

## 1–3. Task / Spec / Design
Establish the judge-reliability gold set (E13.S2): planted-defect cases (numeric, negation, frequency, meaning-reversal + clean controls) and a test that runs `compute_judge_reliability` over them — proving a perfect judge scores full recall and a lenient judge that misses planted Criticals is caught (recall < 1.0), the no-vacuous-green gate. AC-1 fixture has planted + clean cases; AC-2 perfect judge → recall 1.0; AC-3 leniency drift → recall < 1.0. Out of scope: running the real LLM judge over the cases in CI (Phase 2; needs cost budget), per-content-type partitioning + κ.

## 4. Code
`tests/evals/judge/planted_critical.jsonl` (6 cases); `tests/test_judge_eval_cases.py`.

## 5. Test
`pytest tests/test_judge_eval_cases.py -q` → 3 tests green.

## 6–7. Red team / Fix
Risk: too few cases to be statistically meaningful — this is the seed; README target grows it (50 by GA). No findings.

## 8. Deploy
- [x] Commit: `e03c760` (batched: "TMX-MQM-EVAL/DASH-LABEL/SHADOW-REPORT/EVAL-CASES: judge reliability + honest labels + cutover tool") · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | judge gold-set seeded; recall gate demonstrated |
