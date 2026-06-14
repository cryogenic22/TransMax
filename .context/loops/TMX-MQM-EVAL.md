# TMX-MQM-EVAL — judge-reliability metric (recall/precision)

**State**: `[Done, pending push]` · **Owner**: Quality & Regulatory / Agent & AI · **Sprint**: Phase 2 seed (E13.S2)
**Reversibility**: `two-way` (pure, additive). **Pre-mortem**: n/a (pure metric). **Blast radius**: new `app/services/judge_eval.py`.

**Gates**: G1 ✓ (the metric the no-vacuous-green CI gate will block on; pure + tested) · G2 N/A · G3 ✓ (recall over planted Criticals + precision computed deterministically).

## 1–3. Task / Spec / Design
The judge is a model and must be measured (§6.10/E13.S2). Ship the pure metric first: `compute_judge_reliability(planted_critical_segment_ids, judge_annotations)` → recall (caught/planted — the headline gate metric) + precision (judge-Critical on a non-planted segment = false positive). AC-1 perfect recall/precision when all planted caught + no FPs; AC-2 a missed planted Critical drops recall; AC-3 over-flagging drops precision; AC-4 a Minor flag does NOT count as a Critical catch. Out of scope: the release-blocking CI gate + drift control limits (Phase 2).

## 4. Code
`app/services/judge_eval.py` — `JudgeReliability` + `compute_judge_reliability`.

## 5. Test
`pytest tests/test_judge_eval.py -q` → 5 tests (recall/precision/leniency/over-flag/empty).

## 6–7. Red team / Fix
Risk: span-level vs segment-level recall — segment-level here (planted Critical = a flagged segment); span-level is a Phase-2 refinement. No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | recall/precision metric ready for the Phase-2 gate |
