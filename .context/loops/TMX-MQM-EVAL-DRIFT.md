# TMX-MQM-EVAL-DRIFT — judge-reliability drift gate (rolling window blocks release)

**State**: `[Done]`
**Owner**: Quality & Regulatory / Agent & AI
**Sprint**: vision-delivery direction 2 (judge reliability)
**Started**: 2026-06-16
**Closed**: 2026-07-13
**Reversibility**: `two-way` — pure additions (drift math in `judge_eval.py`), a new opt-in `--check-drift` gate tier, a committed-but-empty baseline file, and a manual `drift-update` maintainer command. No schema, no public-API shape change, no live-verdict change. Revertable by deleting the additions.
**Pre-mortem**: if this fails in production, the failure mode is a *silently degrading judge* — recall/precision erode run-over-run while staying above the absolute EVAL-CI floor (0.75 / 0.5), so "no vacuous green" quietly stops being true and a weaker judge ships. The gate's own failure mode would be a false DRIFT block (crying wolf) that erodes trust in the gate; mitigated by the one-sided test + `min_abs_drop` floor + `INSUFFICIENT_HISTORY` cold-start honesty.
**Blast radius**: `app/services/judge_eval.py` (pure additions), `scripts/judge_eval_gate.py` (new tier + subcommand), `.github/workflows/eval.yml` (1 arg on the existing judge-gate step), new `tests/evals/judge/drift_baseline.json` (committed, empty), new `tests/test_judge_drift.py`. No app/runtime path; this is meta-eval / CI only.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) extends the existing judge-reliability module + the existing gate, no new service module; (b) <5 callers; (c) zero bundle impact (CI/test only); (d) reuses `load_judge_gold` + `compute_judge_reliability` + the ratchet `check`/`update` baseline convention; (e) ships with `tests/test_judge_drift.py` that fails without the change. Five-test rubric: **functional depth** (a real release gate the build process exercises — E13.S2); **end-user value** (safer outcome — catches judge erosion before it ships); **trust** (judge meta-eval reliability is exactly what §6.10 says a regulator scrutinises); **robustness** (removes the "above-floor slow erosion" failure mode); **stability** (measures real judge behaviour over time). All five pass.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield capability, not a bug ticket). Spirit honoured: `test_gate_blocks_on_drift_exit_3` plants recall 0.80 (ABOVE the absolute floor 0.75, so EVAL-CI passes it) against a stable 0.95 window and asserts the drift gate fires DRIFT / exit 3 — i.e. it reproduces the exact "above-floor slow erosion" that EVAL-CI alone misses, then proves the new gate catches it.
- [x] **G3 Completion** — the gate ACTUALLY BLOCKS a regression (not just computes a number): `test_gate_blocks_on_drift_exit_3` forces `gate.main(...) == 3` with `result == "FAIL_DRIFT"`; `test_gate_passes_when_no_drift` and `test_gate_improvement_does_not_block` prove it does not cry wolf. The gate is wired into `eval.yml`, so a drifted judge blocks the real release once history accrues. Curl/repro equivalent: `python -m scripts.judge_eval_gate check --require-judge --check-drift` exits 3 on a regressed judge.

---

## 1. Task

§6.10 of the LangOps design (and `MQM-DELIVERY-BACKLOG.md` Phase 2) require: **"alert when agreement, recall or precision regress beyond control limits over a rolling window; a regression blocks release."** The shipped `TMX-MQM-EVAL-CI` gate enforces an *absolute* floor (recall ≥ 0.75, precision ≥ 0.5) at a single point in time. That misses *erosion*: a judge whose recall slides from 0.95 → 0.80 is still above the floor but has measurably regressed. This loop adds rolling-window drift detection on top of EVAL-CI.

Addenda at play: **A2** (judge reliability is a deterministic meta-eval gate, not a translator concern), **A3** (no silent fallback / no fabricated baseline — explicit `INSUFFICIENT_HISTORY`; never auto-rebaseline a degrading judge), product principle **"no vacuous green"** (the drift gate is itself an anti-gaming control).

## 2. Spec — acceptance criteria

- [ ] AC-1: `detect_metric_drift(series, current, *, k, min_history, min_abs_drop)` is a pure function returning a `MetricDriftFinding` with status ∈ {`OK`, `DRIFT`, `INSUFFICIENT_HISTORY`}, the window mean/std, and the one-sided lower control limit. Same inputs → same output; no LLM/DB.
- [ ] AC-2: One-sided — an *improvement* (current ≥ mean) NEVER reports DRIFT. Only regression fires.
- [ ] AC-3: Below `min_history` observations → `INSUFFICIENT_HISTORY` (NOT a fabricated OK or DRIFT). This is the honest cold-start; the absolute EVAL-CI floor remains the backstop.
- [ ] AC-4: Drift fires iff `(mean - current) > max(k·std, min_abs_drop)` — the `min_abs_drop` floor prevents a hair-trigger when std≈0; the `k·std` term prevents crying wolf on a genuinely noisy judge. LCL reported = `mean - max(k·std, min_abs_drop)`.
- [ ] AC-5: `detect_judge_drift(current, history, *, metrics, …)` runs the per-metric detector over each configured metric (default `recall`, `precision`; metric-agnostic so `agreement`/κ plugs in once the judge↔human join lands). Returns a per-metric `{name: MetricDriftFinding}`.
- [ ] AC-6: A committed baseline `tests/evals/judge/drift_baseline.json` exists with an **empty** `observations` list (honest cold start — no invented history) + the window config. `load_drift_baseline` reads it; a malformed/missing file is handled (no raw traceback).
- [ ] AC-7: `python -m scripts.judge_eval_gate check --check-drift` — structure-only (no keys) validates the baseline integrity and reports drift `SKIPPED_NO_CURRENT` (no current data point → no regression possible → exit 0). With `--require-judge` + keys, it computes the current run, runs drift detection, and exits **3** ("FAIL_DRIFT") if ANY metric regresses, alongside the existing exit 1 (below floor) / 2 (integrity).
- [ ] AC-8: `python -m scripts.judge_eval_gate drift-update --label <id>` runs the real judge once and **appends** the observation to the baseline file (the deliberate, PR-reviewed history-accrual path — mirrors `scripts/ratchet.py update`). It is NOT wired into CI (no self-rebaselining).
- [ ] AC-9: `eval.yml`'s existing `judge-gate` step passes `--check-drift`. Behaviour today is unchanged (cold start → SKIPPED/INSUFFICIENT defers to the absolute floor); the mechanism activates once real history accrues.

Out of scope: the judge↔human agreement (κ) series — needs structured human MQM labels from `TMX-MQM-1a` (deferred join `TMX-MQM-EVAL-KAPPA-JOIN`); the detector is built metric-agnostic so κ wires in with zero new math. Auto-accrual of history in CI (deliberately excluded — that is the self-rebaselining anti-pattern). Calibration/recalibration loop (`TMX-MQM-CALIBRATE`).

## 3. Design

**Why a one-sided rolling-window control limit (not a fixed second floor).** A second absolute floor (e.g. recall ≥ 0.90) is brittle: it either duplicates EVAL-CI or guesses a number with no basis. Drift is *relative to the judge's own established behaviour*, which is what §6.10 ("control limits over a rolling window") asks for and what survives a growing/changing gold set. One-sided because only *regression* matters — a judge getting better is never a release blocker.

**The control rule (AC-4).** `drop = mean - current`; `threshold = max(k·std, min_abs_drop)`; DRIFT iff `drop > threshold`. Defaults `k=3.0`, `min_history=5`, `min_abs_drop=0.05`. Population std over the window. This composes the statistical-process-control idea (μ − kσ) with a minimum meaningful-drop floor so the gate is neither hair-trigger (σ≈0) nor blind (σ large) — the σ-large blind spot is backstopped by EVAL-CI's absolute floor.

**Honest cold start (A3).** The baseline ships with `observations: []`. Until ≥ `min_history` real judge runs accrue (via the deliberate `drift-update`), every metric reports `INSUFFICIENT_HISTORY` and the gate defers to the absolute floor. We never fabricate a starting window — a made-up baseline is exactly the "vacuous green" this whole pillar exists to prevent.

**No self-rebaselining (A3 / no vacuous green).** History accrues ONLY through the manual `drift-update` command (PR-reviewed, like `ratchet.py update`), never automatically in CI. Auto-appending each CI run would let a slowly-degrading judge keep re-centering its own window downward — the classic drift-detector failure. Maintainer review is the structural floor.

**Reuse / strangler-fig.** Drift math lives in `app/services/judge_eval.py` (the judge-reliability home) — no new module. The gate gains a tier, reusing the existing `load_judge_gold` + judge-run + `compute_judge_reliability`. The baseline file sits beside the gold set under `tests/evals/judge/` (a tracked dir; `eval_results/` is transient/untracked, so the baseline must NOT live there). Naming is explicit — `judge`/`drift_baseline` — to avoid collision with the unrelated back-translation `semantic_drift.py` / `TMX-DRIFT-GATE`.

Alternatives rejected: (1) a second absolute floor — brittle, basis-free; (2) auto-accrue history in CI — self-rebaselining vacuous-green trap; (3) a new `drift_service.py` module — bloat; the metric is judge-reliability, it belongs in `judge_eval.py`; (4) two-sided control limits — improvements are not regressions.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/judge_eval.py` | +~90 | `MetricDriftFinding`, `detect_metric_drift`, `detect_judge_drift`, `load_drift_baseline`, `DEFAULT_DRIFT_BASELINE_PATH` |
| `tests/evals/judge/drift_baseline.json` | new | committed empty-observations baseline + window config |
| `scripts/judge_eval_gate.py` | +241 | split `_run_judge_tier` → `_run_judge` (reusable) + tier; `_apply_drift_check` / `_apply_drift_structure_only`; `cmd_drift_update`; `--check-drift` / `--drift-baseline` args; exit 3 (FAIL_DRIFT) + exit 2 on malformed baseline |
| `.github/workflows/eval.yml` | +6/-1 | `--check-drift` on the judge-gate step + explanatory comment |
| `tests/test_judge_drift.py` | new (250→316) | drift math (7) + multi-metric (2) + cold-start/loader (4) + gate integration incl. exit-3 block (5) + **drift-update append/preserve-`_doc` + NO_KEYS (2, added stage 7)** |

## 5. Eval / Test

```
$ python -m pytest tests/test_judge_drift.py -q
...................                                                      [100%]
19 passed in 0.37s
```

- `ruff check` (judge_eval.py, judge_eval_gate.py, test_judge_drift.py): **All checks passed!**
- `ruff format --check`: **3 files already formatted**
- `mypy app/services/judge_eval.py scripts/judge_eval_gate.py`: after clearing a stale cache (a transient numpy typing-stub `_AnyShape` fixup crash), mypy checked both files and attributed **0 errors to them**. The 82 errors it surfaced are **pre-existing debt in 13 unrelated files** (`app/auth/*`, `app/services/routing_policy_service.py` — SQLAlchemy `Column[...]` assignment noise), untouched by this loop. No mypy pre-commit hook exists (config line 4 names mypy only in a comment); CI is the mypy gate.
- Existing judge/gate/kappa suite: **53 passed, 0 failed** (no regression from the `_run_judge_tier` → `_run_judge` split).
- `python scripts/ratchet.py check`: **✓ all 17 metrics at or better than baseline** (after the stage-7 `Any`-tightening below).

Coverage of the acceptance criteria:

| AC | Proven by |
|---|---|
| AC-1 pure `MetricDriftFinding` | `test_stable_window_no_drift`, `test_lower_control_limit_is_mean_minus_threshold` |
| AC-2 one-sided | `test_improvement_never_fires_one_sided`, `test_gate_improvement_does_not_block` |
| AC-3 cold start honest | `test_insufficient_history_below_min`, `test_cold_start_defers_to_floor` |
| AC-4 `max(k·std, min_abs_drop)` | `test_min_abs_drop_floor_guards_hair_trigger`, `test_noisy_window_widens_the_band` |
| AC-5 metric-agnostic multi | `test_detect_judge_drift_per_metric`, `test_detect_judge_drift_skips_unmeasured_and_none` |
| AC-6 committed empty baseline | `test_committed_baseline_is_cold_start`, `test_load_missing_baseline_is_honest_empty` |
| AC-7 `--check-drift` tiers + exit 3 | `test_gate_blocks_on_drift_exit_3`, `test_gate_structure_only_skips_drift`, `test_gate_malformed_baseline_is_integrity_failure` |
| AC-8 `drift-update` appends (PR-reviewed) | `test_drift_update_appends_and_preserves_doc`, `test_drift_update_requires_keys` |
| AC-9 `eval.yml` passes `--check-drift` | diff on `.github/workflows/eval.yml`; cold start ⇒ SKIPPED/INSUFFICIENT, behaviour unchanged today |

## 6. Red team — Tier 2 + A1-A10

**Tier 2 (22-item red-flag checklist).** No flag stands:
- *Silent fallback?* — no. Missing baseline → documented honest cold-start (empty window ⇒ INSUFFICIENT_HISTORY, defers to the absolute EVAL-CI floor); malformed baseline → **fails loud** as FAIL_INTEGRITY / exit 2 (not swallowed).
- *Fabricated data?* — no. Baseline ships `observations: []`; history accrues only via the deliberate, PR-reviewed `drift-update` (never auto in CI). This is the anti-vacuous-green control itself.
- *Deep module / information hiding* — the SPC math is a pure function (`detect_metric_drift`) with a narrow interface; the gate composes it without knowing its internals.
- *DRY* — reuses `load_judge_gold`, `compute_judge_reliability`, and the ratchet `check`/`update` baseline idiom; the `_run_judge` split removes the duplicate judge-invocation that a second LLM call would have needed.
- *Unrelated changes bundled?* — the diff carries ruff-format normalisation of pre-existing lines in `judge_eval.py` (path reflow, dataclass comment realignment). Cosmetic, enforced by the standing `ruff format` gate anyway; not behaviour.
- *Error handling* — the only new IO (`load_drift_baseline`) either returns an honest empty dict (missing) or propagates `JSONDecodeError` (malformed) into a structured gate failure; no bare `except`, no `Any`-leak in business logic.

**A-addenda:**
- **A2 (quality at gates, not translate)** ✅ — drift is a deterministic meta-eval gate; zero translator-prompt change.
- **A3 (no silent fallback in regulated paths)** ✅ — the whole design is A3: no fabricated baseline, no self-rebaselining, malformed→loud. This was the sharpest scrutiny axis and it holds.
- **A8 (prompt versioning)** — untouched (no prompt change).
- **A1/A4/A5/A6/A7/A9/A10** — N/A (no state transition, no model-layer/schema change, no ID derivation, no LLM-call path change, no route, no delete, `.context` updated at stage 8).

**Verified false-alarm axes (things that could regress but don't):**
- *Noisy-judge blind spot* — a genuinely high-variance judge gets a wide `k·std` band, so a real erosion inside the band won't fire drift. **Documented, and backstopped by EVAL-CI's absolute floor** (recall ≥ 0.75) which is the hard stop. Acceptable, intentional.
- *`drift-update` bakes in a degraded run* — possible if run while already degraded; mitigated by PR review (same trust model as `ratchet.py update`). Documented.

## 7. Fix

Red team surfaced exactly one gap: **AC-8's `cmd_drift_update` append path had zero test coverage** — the write must preserve the committed `_doc`/config (the regulatory evidence window) and append rather than clobber, and the NO_KEYS guard must actually block the judge from running keyless. Both are silent-corruption / silent-bypass risks with no regression net. Cleared the anti-bloat rubric (robustness + trust) and added two tests:
- `test_drift_update_appends_and_preserves_doc` — seeds a baseline with a `_doc` + config + one observation, runs `drift-update` with a fake judge, asserts APPENDED, `_doc`/config survive, and the new observation is appended (not clobbered).
- `test_drift_update_requires_keys` — asserts NO_KEYS / exit 2 and that `_run_judge` is never reached without a key.

Also verified against real code that `settings.openai_api_key` / `anthropic_api_key` (`config.py:80-81`) are the correct attribute names the guard reads. No source-code logic fix needed beyond the tests — the implementation was correct; it was untested.

**Second gate catch — ratchet `Any` regression (+8).** The first `ratchet.py check` red-flagged `backend.any_annotations 293 > 285 (+8)` — the new gate helpers had leaned on `-> Any` / `Dict[str, Any]`, violating the repo "No `Any`" convention. Fixed by tightening (NOT by loosening the baseline): concrete returns `-> JudgeReliability` / `-> Dict[str, object]`, `f: MetricDriftFinding`, report dicts `Dict[str, object]`, and JSON gold/history rows typed as `Sequence[Mapping[str, Any]]` (the file's existing honest JSON-row convention, Any-compatible downstream). Re-run: **✓ all 17 metrics at/under baseline**, ruff + 19 tests still green. Decision: fix the types, never loosen the ratchet for a self-inflicted regression.

## 8. Deploy

- [x] Commit: a19c953 (implementation — judge_eval.py, judge_eval_gate.py, eval.yml, drift_baseline.json, test_judge_drift.py)
- [x] Closing docs commit: this worksheet (state → Done, SHA recorded)
- [ ] Pushed to `origin/feat/vision-delivery-2` (this session)
- [ ] `.context/active_tasks.md` — drift-Done row rides the ADR-0008 batch commit (active_tasks is mid-edit for that effort; not bundled here). Drift-audit anchor is this worksheet's `Commit:` line, not active_tasks.
- [ ] memory `mqm-keystone.md` resume section updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-16 | — | `[Spec]` | Created; surface mapped (judge_eval.py + judge_eval_gate.py + eval.yml + planted_critical.jsonl); confirmed no overlap with semantic_drift |
| 2026-07-13 | `[Spec]` | `[Done]` | Resumed code-complete (17 tests green). Red team added 2 tests for the untested AC-8 `drift-update` append/preserve-`_doc` + NO_KEYS path (19 total). Gate catch: ratchet flagged +8 `Any` — fixed by tightening types (never loosened baseline). Refactor cleared QG complexity/size warnings (DRY: unified malformed-baseline→FAIL_INTEGRITY + drift-update fail-emit). All gates green: ruff, QG PRS≥85 (0 issues), ratchet OK, mypy 0 errors on the 2 files, 19 tests. Impl commit **a19c953** on `feat/vision-delivery-2`. |
