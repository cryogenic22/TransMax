# TMX-MQM-5a-emit — persist the shadow diff to the v2 audit chain

**State**: `[Done, pending push]` · **Owner**: Audit & Validation / Agent & AI · **Sprint**: MQM Keystone (Phase 1)
**Reversibility**: `two-way`. **Pre-mortem**: emit failure → logged + skipped (the emit helper is fail-safe); never affects the verdict. **Blast radius**: `run_mqm_shadow` (one extra v2 event per gate run when a job_id is present).

**Gates**: G1 ✓ (makes the shadow diff durable + queryable for the phase-b gate review and Phase-2 κ; reuses `emit_v2_audit_event`) · G2 N/A · G3 ✓ (the legacy-vs-MQM diff + judge findings now land in the immutable chain, not just logs).

## 1–3. Task / Spec / Design
The shadow comparison was log-only; for the phase-b cutover decision and Phase-2 calibration it must be durable + queryable. Emit `MQM_SHADOW_SCORE` (legacy-vs-MQM diff) and `MQM_JUDGE_SHADOW` (judge annotations + judge-only score) to the v2 audit chain via the existing fail-safe emit shim. AC-1 a job with a job_id emits `MQM_SHADOW_SCORE`; AC-2 emit failure never breaks the gate. Reuses `app/agents/_audit_v2_emit.emit_v2_audit_event`.

## 4. Code
`app/agents/nodes/mqm_shadow.py` — `run_mqm_shadow` emits `MQM_SHADOW_SCORE`; `run_judge_shadow` emits `MQM_JUDGE_SHADOW`.

## 5. Test
Covered by `tests/test_mqm_shadow.py` (comparison returned) + the gate/graph regression (96 green; v2 emit is fail-safe). The emit path itself reuses the TMX-3110-tested shim.

## 6–7. Red team / Fix
Risk: audit volume (one event/gate run) → acceptable; can be sampled later. Risk: non-JSON payload → `MqmScore.to_dict` is JSON-safe (interval→list). No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | shadow diff + judge findings durable in v2 |
