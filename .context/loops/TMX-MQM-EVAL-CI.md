# TMX-MQM-EVAL-CI — release-blocking judge-reliability gate + one canonical gold loader

**State**: `[Done]`
**Owner**: Quality & Regulatory + Platform
**Sprint**: MQM Keystone / Phase 2
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (new script + new CI job + new pre-commit hook + a loader move; revertable by deleting them)
**Pre-mortem**: if this fails in production, the failure mode is *a green gate that proves nothing* — a missing/empty gold set silently scoring recall=1.0. Guarded by an explicit non-empty + has-planted + has-clean integrity assertion that fails the build (the exact vacuous-green trap the audit warned about).
**Blast radius**: `app/services/judge_eval.py` (canonical loader), `tests/test_judge_eval_cases.py` (dedupe onto it), new `scripts/judge_eval_gate.py`, `.github/workflows/eval.yml` (new job), `.pre-commit-config.yaml` (mirror hook). No runtime/app behaviour change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: there is no entrypoint that exercises judge reliability as a gate today; the pure metric exists but nothing fails the build; (b) <5 callers; (c) CI-only; (d) reuses `compute_judge_reliability` + mirrors the existing `eval.yml`/`ratchet.yml` gate shapes + the existing gold set; (e) ships with tests incl. a failing-on-empty-gold test.
- [x] **G2 Reproduce-the-failure** — the "empty gold scores vacuously green" failure is reproduced as a red test (gate exits non-zero on an empty gold file) BEFORE the guard is asserted to work.
- [ ] **G3 Completion** — the gate blocks a broken/empty gold set; when LLM keys are present it enforces a real recall floor over the gold via the real judge.

---

## 1. Task

Turn the pure judge-reliability metric (TMX-MQM-EVAL) into a **release-blocking CI gate** and collapse the duplicated gold-set loader into one canonical source. The gate has two honest tiers mirroring `eval.yml`'s scope detection: **always** validate gold-set integrity (a broken/empty gold set fails the build — closing the "vacuous green" trap); **with LLM keys present**, run the real judge over the gold and enforce a recall floor.

Addenda: **A2** (the judge-reliability gate is deterministic, beside the gates), **A3** (no silent green on empty gold), Tier-0 SSOT (one gold loader, not three).

## 2. Spec — acceptance criteria

- [ ] AC-1: `load_judge_gold(path=None) -> list[dict]` is the ONE canonical gold loader in `judge_eval.py`; `tests/test_judge_eval_cases.py` imports it instead of its private `_load()` (no forked JSONL parsing).
- [ ] AC-2: `python -m scripts.judge_eval_gate check` exits non-zero when the gold set is missing, empty, has no planted Critical, or has no clean case (the no-vacuous-green guard).
- [ ] AC-3: With `--require-judge` AND live LLM keys, the gate runs the real judge over the gold cases, computes `compute_judge_reliability`, and exits non-zero when `recall < floor` (default 0.75, configurable via `--min-recall`).
- [ ] AC-4: Without keys/`--require-judge` (the default CI scope when no secrets), the gate runs structure-only and still fails on a broken gold set — never silently passes.
- [ ] AC-5: A new `judge-gate` job in `eval.yml` runs the gate (scope-detected like the existing golden-suite job) and blocks the PR on failure; a `.pre-commit-config.yaml` local hook runs the structure-only gate.
- [ ] AC-6: `tests/test_judge_eval_gate.py` proves: real gold passes the integrity check; an empty/temp gold file fails; a planted-only or clean-only gold fails.

Out of scope: drift/control-limits over a rolling window (**TMX-MQM-EVAL-DRIFT**); growing the gold set to 50 cases (README target, GA); per-content-type partitioning.

## 3. Design

One loader (`load_judge_gold`) in `judge_eval.py`, default path = `tests/evals/judge/planted_critical.jsonl`. `scripts/judge_eval_gate.py` (run via `python -m scripts.X`, like `scripts.mqm_shadow_report`) with a `check` subcommand: load → integrity-assert → optionally run the real judge → enforce floor → JSON report + exit code. The two-tier scope mirrors `eval.yml` exactly (reuse-and-reconcile, not a new CI idiom). The integrity guard is itself a real release gate even in structure-only mode — it blocks the precise vacuous-green trap (empty gold ⇒ recall defaults to 1.0).

Alternatives rejected: (a) a new ratchet metric — rejected, `Metric.measure` is `Callable[[], int]` and recall is a float; forcing a scaled-int forks the ratchet contract; a sibling gate is cleaner; (b) bolt the judge into `tests/evals/runner.py` SUITES — rejected, that harness tests deterministic gate output, not the judge; sharing the loader (not the runner) is the right reconcile; (c) a 3rd inline loader — rejected (Tier-0 SSOT).

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/judge_eval.py` | +~12 | `load_judge_gold(path=None)` + `DEFAULT_GOLD_PATH` |
| `tests/test_judge_eval_cases.py` | ~12 | import `load_judge_gold`; drop the private `_load()` |
| `scripts/judge_eval_gate.py` | new | `check` gate: integrity + optional real-judge recall floor |
| `.github/workflows/eval.yml` | + job | `judge-gate` job (scope-detected, release-blocking) |
| `.pre-commit-config.yaml` | + hook | structure-only `judge-eval-gate` local hook |
| `tests/test_judge_eval_gate.py` | new | integrity pass/fail cases |

## 5. Eval / Test

```
python -m pytest tests/test_judge_eval_gate.py tests/test_judge_eval_cases.py -q
python -m scripts.judge_eval_gate check
```
```
gate tests pass (integrity: empty/missing/planted-only/clean-only/corrupt-line/
missing-key all → exit 2; precision floor enforced via mock judge → exit 1; good
judge → exit 0). CLI structure-only → result=PASS_STRUCTURE_ONLY. Full regression
202 passed.
```

## 6. Red team

4-lens adversarial review (workflow `wn9n1w41k`). Verified fail-closed: `--require-judge` with a fake LLM → recall 0.0 → exit 1 (not vacuous pass); empty/lopsided gold → exit 2; recall floor uses `>=`. **Honesty lens found two real defects:** (1) `--min-precision` defaulted to 0.0 → a permanent no-op, so a flag-everything judge passed on recall alone; (2) `load_judge_gold` raised a raw `JSONDecodeError` on a corrupt line instead of the structured exit-2 contract.

## 7. Fix

(1) `--min-precision` default 0.0 → **0.5, enforced** (a flag-everything judge now fails a binding precision floor; documented as tightening with the gold). (2) `cmd_check` wraps the load and converts `JSONDecodeError` → `FAIL_INTEGRITY` (exit 2, structured). Added two reproduce-then-fix tests (precision-floor enforced; corrupt-line clean fail). Re-ran: green.

## 8. Deploy

- [x] Commit: `6536939` (batch w/ ENSEMBLE-RUN + EVAL-KAPPA)
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created; gate over the existing planted gold; structure-tier always blocks, judge-tier blocks when keys present |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `6536939`; red team fixed precision no-op (→0.5 enforced) + corrupt-gold crash (→FAIL_INTEGRITY) |
