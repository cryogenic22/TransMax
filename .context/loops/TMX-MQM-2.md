# TMX-MQM-2 — content-type metric profile registry

**State**: `[Done, pending push]`
**Owner**: Quality & Regulatory
**Sprint**: MQM Keystone (Phase 1)
**Started**: 2026-06-14
**Closed**: 2026-06-14
**Reversibility**: `two-way` — pure addition; new module + versioned YAML data.
**Pre-mortem**: if this fails in production, the failure mode is a mis-calibrated threshold passing bad content — mitigated because profiles are versioned, content-hashed, and the thresholds are explicitly flagged as starting proposals pending gold-data calibration.
**Blast radius**: new `app/core/metric_profiles/` package + 5 profile YAMLs. Nothing on the live path reads them yet (TMX-MQM-5 wires them).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — mirrors the existing `PromptRegistry` pattern (reuse); is the reconciliation home for the two pre-existing profile systems (single source of truth); ships with tests.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield).
- [x] **G3 Completion** — all 5 §5.4 profiles load with the vision's PT/APP/ETW and feed the engine.

---

## 1. Task
Provide the versioned content-type metric profiles (ETW/PT/APP/eval-mode/sample-floor) the MQM engine scores against — the reconciliation point for the orphaned `regulatory_profiles.py` (authority metadata) and `profile_resolver.py` (archetype/tier), neither of which carried scoring semantics. Addenda: A8 (pin versions — profiles are change-controlled, content-hashed).

## 2. Spec — acceptance criteria
- [x] AC-1: registry loads `<profile_id>/v<semver>.yaml` with class-cache + lock + `latest` resolution + content-hash, mirroring `PromptRegistry`.
- [x] AC-2: 5 profiles ship (icf, smpc_pil, pv, pro_coa, promo) with the §5.4 PT/APP/evaluation/auto-fail/ETW values.
- [x] AC-3: `MetricProfile.etw(dimension)` resolves per-dimension weight with a `default` fallback.
- [x] AC-4: schema validation rejects missing keys, version/id mismatch, bad evaluation mode, and APP ≤ 0 (divide-by-zero guard on the Scaling Factor).

Out of scope: wiring a resolver from document content → profile_id (→ TMX-MQM-5).

## 3. Design
Copy the proven `PromptRegistry` rather than invent a new loader — keeps one mental model and makes a future shared versioned-YAML-registry extraction (the "3rd copy" rule) clean. ETW keyed by `MqmDimension` value strings + `default`. Rejected: putting scoring thresholds into `regulatory_profiles.py` (would conflate authority metadata with scoring and deepen the dual-profile divergence).

## 4. Code
| File | Change |
|---|---|
| `app/core/metric_profiles/registry.py` | new — MetricProfile + MetricProfileRegistry |
| `app/core/metric_profiles/__init__.py` | new — public API |
| `app/core/metric_profiles/{icf,smpc_pil,pv,pro_coa,promo}/v1.0.0.yaml` | new — 5 profiles |
| `tests/test_metric_profiles.py` | new — 8 tests |

## 5. Eval / Test
```
python -m pytest tests/test_metric_profiles.py -q
→ 8 passed (thresholds asserted against vision §5.4)
```

## 6. Red team
Risk: APP=0 → divide-by-zero in the engine's Scaling Factor — guarded at load (`acceptable_penalty_points must be > 0`). Risk: profile drift — content_hash pins each version; a profile change is a new version (shadow re-score is E4.S2). Risk: ETW key typo silently defaulting — acceptable (default=1); a future lint can assert keys ∈ MqmDimension values.

## 7. Fix
No findings — clean.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill>
- [ ] Pushed to origin/main: **gated on Kapil** (branch `feat/mqm-keystone`)
- [x] `.context/active_tasks.md` updated

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-14 | — | `[Done, pending push]` | Built + tested; on `feat/mqm-keystone` |
