# TMX-MQM-1 — MQM annotation object + taxonomy reconciliation

**State**: `[Done, pending push]`
**Owner**: Quality & Regulatory / Agent & AI
**Sprint**: MQM Keystone (Phase 1)
**Started**: 2026-06-14
**Closed**: 2026-06-14
**Reversibility**: `one-way` — the §5.7 annotation schema + the SPM ladder are the spec future code reproduces; design-justified below.
**Pre-mortem**: if this fails in production, the failure mode is a mis-typed annotation that scores wrong — mitigated by the engine being the sole verdict authority (TMX-MQM-3) and the spec-binding tests.
**Blast radius**: `app/core/defect_taxonomy.py` (additive), new `app/core/mqm_annotation.py`. No live-pipeline behaviour change — nothing imports the new object on the hot path yet.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — extends the existing taxonomy rather than forking a new severity/dimension type; the annotation is the shared currency for 5 downstream areas (functional depth); ships with failing-without-change tests.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield keystone, not a bug ticket).
- [x] **G3 Completion** — the §5.7 object exists, constructs from legacy `Defect`/violation dicts, and the SPM/dimension constants are consumed by TMX-MQM-3.

---

## 1. Task
Build the span-level MQM annotation object (§5.7) that is the shared currency of the quality engine, **reusing** the existing `defect_taxonomy.py` rather than introducing parallel types. Addenda at play: A2 (quality at gates), A4 (don't deepen dual-model divergence — annotation persistence deferred so no schema added this loop).

## 2. Spec — acceptance criteria
- [x] AC-1: `DefectSeverity` gains a `NEUTRAL` tier (MQM SPM 0); legacy CRITICAL/MAJOR/MINOR and `is_critical()` unchanged.
- [x] AC-2: `SEVERITY_PENALTY_MULTIPLIER` = {Neutral 0, Minor 1, Major 5, Critical 25}; `MqmDimension` enumerates the 7 MQM-Core dimensions.
- [x] AC-3: `CATEGORY_TO_DIMENSION` + `dimension_for_category()` bridge every `DefectCategory` (and unknown strings, falling back to ACCURACY) onto a dimension.
- [x] AC-4: `MqmAnnotation` (pydantic) with only `dimension`+`severity` required; `from_defect`/`from_violation` reconciliation constructors; lowercase-legacy severity normalised.
- [x] AC-5 (review cond. 3): `is_auto_fail` is a non-authoritative denormalised convenience, forced consistent with severity by `model_post_init`; the engine — not the annotation — decides auto-fail.

Out of scope: the `mqm_annotations` DB table + Alembic revision (→ TMX-MQM-1a — engine/judge need only the in-memory object).

## 3. Design
Polarity of reuse: severity + dimension are taxonomy concerns → live in `defect_taxonomy.py`. The annotation object is a new concept → its own module, importing the taxonomy. `is_auto_fail` kept as a UI convenience but documented as non-authoritative (the keystone closes "marking your own homework"; a second authoritative source would re-open it). Rejected: a brand-new severity enum (would fork the taxonomy and break `is_critical`).

## 4. Code
| File | Change |
|---|---|
| `app/core/defect_taxonomy.py` | +NEUTRAL, MqmDimension, SEVERITY_PENALTY_MULTIPLIER, CATEGORY_TO_DIMENSION, dimension_for_category() |
| `app/core/mqm_annotation.py` | new — Span, MqmAnnotation, from_defect/from_violation, _coerce_severity |
| `tests/test_mqm_annotation.py` | new — 12 tests |

## 5. Eval / Test
```
python -m pytest tests/test_mqm_annotation.py -q
→ 12 passed
python -m pytest tests/test_quality_gates.py tests/test_profile_gates.py tests/test_quality_gate_thread_safety.py ... -q
→ 53 passed (no regression from the taxonomy extension)
```

## 6. Red team
Risk: adding `NEUTRAL` could break exhaustive severity matches — checked: no code does an exhaustive match; `is_critical` and `classify_violation` default path unaffected. Risk: `is_auto_fail` re-opening self-certification — closed by making the engine ignore it (pinned in TMX-MQM-3 tests). Risk: `from_violation` on a malformed dict — `_coerce_severity` defaults to MAJOR, `dimension_for_category` defaults to ACCURACY; never raises.

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
