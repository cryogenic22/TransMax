# TMX-MQM-SHADOW-REPORT — shadow-diff report for the cutover gate

**State**: `[Done, pending push]` · **Owner**: Audit & Validation · **Sprint**: MQM Keystone (Phase 1)
**Reversibility**: `two-way` (read-only script). **Pre-mortem**: none (no writes). **Blast radius**: new `scripts/mqm_shadow_report.py`.

**Gates**: G1 ✓ (the tool that produces the phase-b cutover evidence; reuses the v2 model + the documented admin scan) · G2 N/A · G3 ✓ (summarises legacy-vs-MQM agreement + CQS distribution from the audit chain).

## 1–3. Task / Spec / Design
The phase-b cutover is gated on reviewing the shadow diff (review cond. 4). Provide the read-only tool: read `MQM_SHADOW_SCORE` v2 events (TMX-MQM-5a-emit), report block-agreement rate, disagreement count, CQS min/mean/max, critical-auto-fail + insufficient-sample counts. AC-1 prints a summary; AC-2 `--json` output; AC-3 honest empty-state when no events yet. Uses `include_other_tenants=True` (documented forensic-admin scan) so one report covers the pilot.

## 4. Code
`scripts/mqm_shadow_report.py` — `collect_shadow_rows` + `summarise` + CLI.

## 5. Test
Smoke: `python -m scripts.mqm_shadow_report` → honest empty-state on a fresh DB (0 events). Populated runs summarise after traffic with `mqm_shadow_enabled` on.

## 6–7. Red team / Fix
Risk: cross-tenant read — intentional, documented admin scan (matches TMX-3110b). Read-only; no mutation. No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | cutover-gate evidence tool ready |
