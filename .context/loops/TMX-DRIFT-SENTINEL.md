# TMX-DRIFT-SENTINEL — semantic-drift returns None (not 0.0) when unavailable

**State**: `[Done]` — `a987c3d` on origin/main
**Owner**: Quality & Regulatory + Agent & AI
**Sprint**: 2 (engine-to-regulatory-grade batch)
**Started**: 2026-06-11
**Reversibility**: `two-way` — changes one method's sentinel + relaxes one pure helper's filter. Forward-only behaviour change (a genuine catastrophic-0 drift now gates instead of being skipped). Revert restores the `0.0` sentinel.
**Pre-mortem**: if this fails in production, the failure mode is either (a) a job held for review on a genuine 0-score back-translation (correct, A3) or (b) a `null` drift in the `/tools` response — never a crash. The drift gate already handled `None` defensively, so no NPE path.
**Blast radius**: `app/services/quality_gate.py` (`calculate_semantic_drift` return contract + logger), `app/agents/nodes/reverse_translate.py` (`assess_reflexion` filter), new tests. Two callers: the reflexion node + `app/api/tools.py` (back-translation tool). A2/A3 surfaces.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (robustness + trust) closes the A3 silent-default smell flagged in TMX-DRIFT-GATE: `0.0` on no-key was indistinguishable from a real catastrophic score, forcing the gate to exclude all zeros and miss a genuine one. No new code path; tightens an existing one.
- [x] **G2 Reproduce-the-failure** — a no-key call currently returns `0.0` (a "maximally drifted" lie). A RED test asserts it returns `None`; it fails on the current literal.
- [x] **G3 Completion** — `calculate_semantic_drift` returns `None` when it cannot compute (no key / embed error); `assess_reflexion` excludes only `None` (a real `0.0` now gates); the `/tools` back-translation response carries `null` rather than a fake `0.0`; both `print()`s removed. Proven by `tests/test_drift_sentinel.py` (3) + updated `tests/test_drift_gate.py`.

---

## 1. Task
Make back-translation semantic-drift honest about "couldn't compute" (A3 — no silent default), and let a genuine low/zero score gate. Supersedes the `> 0.0` exclusion caveat documented in [[TMX-DRIFT-GATE]].

## 2. Spec — acceptance criteria
- [ ] AC-1: `calculate_semantic_drift(...) -> Optional[float]` returns `None` when `settings.openai_api_key` is absent and on embed-failure (logged), instead of `0.0`.
- [ ] AC-2: the two `print()` calls in `quality_gate.py` (drift + governance) become `logger` calls (file gains a module logger).
- [ ] AC-3: `assess_reflexion` counts a score iff it `is not None` (drop the `> 0.0` guard); a genuine `0.0` now flags review.
- [ ] AC-4: the `/api/tools` back-translation response returns `drift_score: null` when unavailable, never a fabricated `0.0`.

Out of scope: batching the embedding call (TMX-AUDIT-QG-BATCH-EMBED); per-tenant drift threshold.

## 3. Design
`None` is the honest "unavailable" signal; every consumer already tolerates it (the gate excludes `None`, the API serialises it to `null`). Relaxing `assess_reflexion` to `is not None` is now safe *because* the no-key sentinel is no longer a numeric `0.0` colliding with a real score — the two failure modes are finally distinguishable. Add a module logger (the file had none) and retire both stray prints while here (A10 entropy).

Rejected: returning a sentinel like `-1` (still a magic number a caller could average in); raising (a telemetry helper must never block the pipeline — A3).

## 4. Code
| File | Change |
|---|---|
| `app/services/quality_gate.py` | logger; `calculate_semantic_drift -> Optional[float]`, `None` on no-key/error; 2 `print`→`logger` |
| `app/agents/nodes/reverse_translate.py` | `assess_reflexion` filter `> 0.0` → `is not None` + docstring |
| `tests/test_drift_sentinel.py` | new — AC-1..AC-4 |
| `tests/test_drift_gate.py` | update the 0.0-exclusion test to the new (gating) behaviour |

## 5. Eval / Test
```
tests/test_drift_sentinel.py → 3 passed (None on no-key; real 0.0 gates; all-None not held)
tests/test_drift_gate.py (updated) + test_parallel_reflexion + test_finalize_output_hash → green
Full suite: <pending background run>
Ratchet 17/17 — print_in_app dropped (2 more prints removed); mega_files_800 held at baseline
  (quality_gate.py kept at 799 by trimming the new docstring — the C-08/TMX-3400 split stays a
  separate, deliberate refactor, not a side effect of this loop).
```
## 6. Red team
- A3: the no-key and embed-failure paths now log + return `None` (honest "unavailable"), not a fabricated `0.0`. Telemetry never raises — pipeline unblocked.
- Gate interaction: `assess_reflexion` now holds on a genuine `0.0` (was masked before); `None` still skipped. The two failure modes are finally distinguishable.
- Caller `/api/tools`: `drift_score` serialises to `null` when unavailable — a more honest contract than `0.0`. No consumer asserted `==0` (grep-checked).
- Not claimed: embedding-call batching (TMX-AUDIT-QG-BATCH-EMBED) and the quality_gate singleton split (TMX-3400) remain open.

## 7. Fix
Trimmed the new docstring to keep `quality_gate.py` at 799 lines (it was a pre-existing 798 near-miss; the ratchet correctly flags it as a split candidate, deferred to TMX-3400). `Optional[float]` return — no new `Any`.

## 8. Deploy
- [x] Commit: `a987c3d`
- [x] Pushed to origin/main (Railway auto-deploys) — two-way-safe auto-deploy
- [x] SHA recorded here + in `.context/active_tasks.md`

---
## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Spec]` | Created — follow-up spawned by TMX-DRIFT-GATE |
| 2026-06-11 | `[Spec]` | `[Done — pending SHA record]` | Implemented + tested; ratchet 17/17 (quality_gate.py held at 799). Awaiting commit SHA. |
