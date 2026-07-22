# TMX-MQM-3 — pure MQM-2.0 quality engine

**State**: `[Done]`
**Owner**: Quality & Regulatory / Agent & AI
**Sprint**: MQM Keystone (Phase 1)
**Started**: 2026-06-14
**Closed**: 2026-06-14
**Reversibility**: `one-way` — the §5.5 scoring bytes are the spec future code reproduces; the cutover that would change live behaviour is deferred to TMX-MQM-5 behind a flag.
**Pre-mortem**: if this fails in production, the failure mode is a wrong pass/fail verdict — mitigated by purity (deterministic, testable), spec-binding tests pinned to the vision's worked numbers, and the engine shipping in SHADOW (it decides nothing live yet).
**Blast radius**: new `app/services/mqm_engine.py`. `ConfidenceService` and the graph are untouched — zero live behaviour change this loop.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — the measurement instrument the entire defensibility story needs; reuses the taxonomy SPM + the profile registry; reconciliation bridge `score_from_violations` reuses the gate output; ships with spec-binding tests.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield); spec-binding tests stand in.
- [x] **G3 Completion** — `score()` reproduces the vision's §5.5 worked examples bit-for-bit; the shadow helper agrees with the legacy scorer on a Critical.

---

## 1. Task
Build the pure, deterministic MQM-2.0 engine (§5.5): annotations + versioned profile + EWC → reproducible RQS/CQS + pass/fail. It is the **sole authority on the verdict**; producers only emit annotations. Reuses `defect_taxonomy` (SPM) and `metric_profiles`. Addenda: A2 (deterministic quality at gates, not in translate), A1 (engine output is audit-emittable — TMX-MQM-5).

## 2. Spec — acceptance criteria
- [x] AC-1: `score(annotations, profile, ewc)` implements ETPT→APT→PWPT→NPT→RQS→CQS exactly; pure (no LLM/DB/clock); same inputs ⇒ identical `MqmScore`.
- [x] AC-2 (cond. 3): auto-fail is engine-derived from `severity==CRITICAL AND profile.critical_auto_fail`; the annotation's `is_auto_fail` is ignored; a Critical is non-overridable by a high score.
- [x] AC-3 (cond. 2): `passed` is the pure quality verdict; `insufficient_sample` (+ confidence interval, §5.6) is a SEPARATE flag the routing layer owns — never folded into `passed`.
- [x] AC-4 (cond. 4): ships in shadow — `shadow_compare_legacy()` diffs the legacy scorer vs the engine; `ConfidenceService` untouched.
- [x] AC-5: `score_from_violations()` adapter scores legacy gate dicts (reconciliation, no gate re-authoring).

Out of scope: graph rewire + `ConfidenceService`→adapter cutover + SDK-fork unification (→ TMX-MQM-5, after the shadow diff is signed off).

## 3. Design
Producer/calculator/decider split (ADR-0007): the engine is the calculator+decider. SQC interval is a named, documented heuristic (`_sqc_interval`, margin ~ 1/√EWC) explicitly flagged as the §8.3 open calibration item — not a hidden placeholder. EWC clamped to ≥1 for the denominator while reporting the real EWC. Rejected: hard-cutting `ConfidenceService` now (cond. 4 — would silently change every legacy caller's distribution).

## 4. Code
| File | Change |
|---|---|
| `app/services/mqm_engine.py` | new — MqmScore, score(), score_from_violations(), shadow_compare_legacy(), _sqc_interval() |
| `tests/test_mqm_engine.py` | new — 14 tests (spec-binding + condition tests) |

## 5. Eval / Test
```
python -m pytest tests/test_mqm_engine.py -q   → 14 passed
# spec-binding: RQS=99 (10 minors/1000w); SmPC CQS 98→97 boundary; Promo CQS 90→80 boundary
# cond.3: Critical with CQS≥PT and huge EWC ⇒ passed=False; profile flag, not annotation, governs
# cond.2: 80-word clean doc ⇒ passed=True AND insufficient_sample=True (separate)
python -c "shadow_compare_legacy(... Critical numeric ...)"  → legacy BLOCKED ↔ mqm critical_auto_fail=True
```

## 6. Red team
Risk: insufficient_sample leaking into the verdict — explicitly tested separate (`test_short_high_scoring_doc_passes_but_is_flagged_not_trusted`). Risk: producer setting `is_auto_fail` to dodge a Critical — engine ignores the field (`test_engine_ignores_annotation_is_auto_fail_flag`). Risk: EWC=0 divide-by-zero — clamped + flagged. Risk: SQC interval over-claiming rigour — docstring + module comment flag it as a starting heuristic (§8.3). Risk: silent cutover blast radius — averted by shadow-first (cond. 4).

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: `da7831a` (batched: "TMX-MQM-1/2/3: build the MQM keystone (annotation->engine) in shadow")
- [ ] Pushed to origin/main: **gated on Kapil** (branch `feat/mqm-keystone`)
- [x] `.context/active_tasks.md` updated

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-14 | — | `[Done, pending push]` | Built + tested; shadow-verified; on `feat/mqm-keystone` |
