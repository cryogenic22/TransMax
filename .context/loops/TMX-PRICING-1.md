# TMX-PRICING-1 — Canonical model-pricing registry; remove hardcoded price magic-numbers

**State**: `[Done]`
**Owner**: pod Platform & Observability (E9)
**Sprint**: 3
**Started**: 2026-06-03
**Closed**: 2026-06-03 (committed to worktree branch; push deferred per task — do NOT push)
**Reversibility**: `two-way`
  Pure internal refactor. No schema change, no public-API shape change. The
  `/estimate` endpoint response keeps identical keys and (for gpt-4o-mini)
  identical values. Revert is a single `git revert`.
**Pre-mortem**: If this fails in production, the failure mode is the
  `/estimate` endpoint raising `UnknownModelError` (500) for a model whose
  pricing isn't registered — but that is the A3-correct behaviour (fail loud
  rather than record a wrong-model cost). The endpoint currently only prices
  the hardcoded `"gpt-4o-mini"` constant, which IS registered, so no live
  path can hit the raise today.
**Blast radius**: `app/core/model_pricing.py` (new), `app/api/documents.py`
  (`/estimate` endpoint), `app/services/observability.py`
  (`estimate_cost`, currently uncalled in app code). One new test file.
  No frontend, no DB, no migration. The `transmax_sdk/` package keeps its own
  separate per-1k pricing (different package, different unit) — out of scope,
  see TMX-PRICING-1b below.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — passes. This is anti-bloat-POSITIVE: it removes
  duplication (two+ copies of pricing) rather than adding net-new surface.
  (a) needed: yes — three independent pricing definitions existed, two with
      drifting gpt-4o rates. (b) callers: 2 in app/ today, bounded by
      cost-emitting code. (c) zero bundle impact (backend). (d) reuses stdlib
      dataclass per conventions. (e) ships with a test that fails without the
      module (RED confirmed: ModuleNotFoundError before code).
- [x] **G2 Reproduce-the-failure** — TDD. The "failure" being prevented is a
  silent cost drift / wrong-model cost. `tests/test_model_pricing.py` was
  written FIRST and confirmed RED (`ModuleNotFoundError: app.core.model_pricing`)
  before the module existed. `test_documents_estimate_equivalence` pins the
  exact legacy arithmetic so the refactor cannot change a recorded cost.
- [x] **G3 Completion** — the source code (not just tests) changed: both
  hardcoded sites now import and call `cost_for`. A repro of the `/estimate`
  endpoint returns the IDENTICAL `estimated_cost_usd` for gpt-4o-mini
  (proven by the equivalence test) and now names the same model it priced.

---

## 1. Task

Create a single canonical model-pricing table and remove the gpt-4o-mini
price magic-numbers (`0.00000015` per input token, `0.0000006` per output
token) duplicated across the codebase. Replace each with a call into the
registry. Behaviour for the currently-priced model must be byte-identical.

**Addenda at play**:
- **Single source of truth** (Tier 1 / TMX-3017 spirit) — the core driver.
  Two registries described the same thing; pick one canonical, derive others.
- **A3 (no silent fallbacks in regulated paths)** — `observability.estimate_cost`
  had `pricing.get(model, pricing["gpt-4o"])`, silently recording a cost for
  gpt-4o when an unknown model was passed. A recorded cost is a regulator-
  facing number; an unknown model must fail loud, not default.
- **A6 (LLMs are qualified suppliers)** — pricing is part of the cost
  telemetry that the JobConfigSnapshot must carry accurately; the model
  priced and the model recorded must be the same.

## 2. Spec — acceptance criteria

- [x] AC-1: New module `app/core/model_pricing.py` exposes a typed pricing
  record (`ModelPricing` frozen dataclass — not a raw dict), a registry, and
  `cost_for(model, input_tokens, output_tokens, cached_input_tokens=0) -> float`.
- [x] AC-2: Real 2026 per-1M prices registered: gpt-4o (2.50 / 10.00 / 1.25),
  gpt-4o-mini (0.15 / 0.60 / 0.075).
- [x] AC-3: Unknown model raises `UnknownModelError` (A3) — never returns 0,
  never defaults to another model.
- [x] AC-4: `app/api/documents.py` `/estimate` imports and calls `cost_for`;
  the priced model and the reported `"model"` are the same constant.
- [x] AC-5: `app/services/observability.py` `estimate_cost` delegates to
  `cost_for`; the silent gpt-4o default is removed.
- [x] AC-6: `cost_for("gpt-4o-mini", 1M, 1M) == 0.75`; gpt-4o pins;
  cached-input discount applies — all pinned in tests.
- [x] AC-7: Behaviour IDENTICAL for gpt-4o-mini (legacy-arithmetic
  equivalence test green).
- [x] AC-8: Broad suite green except the pre-existing unrelated
  `test_tm_bypass` failure (proven independent of this change).

Out of scope: the `transmax_sdk/` package's own pricing (`config.py`,
`telemetry/cost.py`) — different package, per-1k unit, separate test surface
→ TMX-PRICING-1b. gpt-4.1 + Claude tier registration → TMX-PRICING-1a (TODO
annotated in the module).

## 3. Design

A frozen dataclass `ModelPricing(input_per_1m, output_per_1m,
cached_input_per_1m)` and a module-level `_PRICING: dict[str, ModelPricing]`.
Prices stored per-1M tokens (the published-rate unit) so the registry reads
the way the OpenAI pricing page does; `cost_for` divides by 1_000_000 once at
the end. `get_pricing` raises `UnknownModelError` (subclass of `KeyError` for
backward-compatible `except KeyError`, but with a descriptive message naming
the model and the known set). `cost_for` rejects negative token counts and
adds the cached-input tier.

**Alternatives considered + rejected**:
- *Per-1k unit (like the SDK)*: rejected — published rates are quoted per-1M
  in 2026; per-1M reads more directly and avoids a second mental conversion.
- *Enum of models*: rejected as over-engineering — model ids are free-form
  strings elsewhere (settings, audit snapshots); a dict keyed by the same
  string is the single source of truth without a parallel enum to keep in
  sync (would itself be a fork, violating single-source-of-truth).
- *Silent default to gpt-4o for unknown models* (the status quo in
  observability): rejected on A3 grounds — recording a cost for the wrong
  model is a regulatory defect.
- *Including the SDK pricing in this loop*: rejected — different package,
  different unit, larger blast radius; spun out as TMX-PRICING-1b.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/model_pricing.py` (new) | ~145 | `ModelPricing` dataclass, `_PRICING` registry, `UnknownModelError`, `get_pricing`, `cost_for`. TODO(TMX-PRICING-1a) for gpt-4.1/Claude. |
| `app/api/documents.py` | +1 import, ~7 in `/estimate` | replace `(in*0.00000015)+(out*0.0000006)` with `cost_for("gpt-4o-mini", ...)`; reported `"model"` now the same `estimate_model` constant. |
| `app/services/observability.py` | +1 import, -12/+8 in `estimate_cost` | replace local pricing dict + silent gpt-4o default with `cost_for`. |
| `tests/test_model_pricing.py` (new) | ~95 | 9 tests: gpt-4o-mini pin, gpt-4o pin, unknown-raises, cached discount, cached+standard sum, legacy-equivalence, typed-record, get_pricing-unknown, negative-rejected. |
| `.context/loops/TMX-PRICING-1.md` (this) | n/a | worksheet |

De-duplicated sites (the magic numbers removed):
- `app/api/documents.py:373` (was `(est_input_tokens * 0.00000015) + (est_output_tokens * 0.0000006)`)
- `app/services/observability.py:44-48` (was the `pricing` dict with `0.00015/1000`, `0.0006/1000` + silent gpt-4o default)

## 5. Eval / Test

### RED (pre-fix)
```
$ python -m pytest tests/test_model_pricing.py -q
ModuleNotFoundError: No module named 'app.core.model_pricing'
1 error in 0.41s
```

### GREEN (post-fix)
```
$ python -m pytest tests/test_model_pricing.py tests/test_observability.py -q
11 passed in 7.12s
```

### Lint / type
```
$ python -m mypy app/core/model_pricing.py app/services/observability.py
Success: no issues found in 2 source files
$ python -m ruff check app/core/model_pricing.py app/services/observability.py app/api/documents.py tests/test_model_pricing.py
All checks passed!
```

### Broad suite
```
$ python -m pytest tests/ -q --timeout=120 --ignore=tests/evals
1 failed, 874 passed, 2 skipped in 151.71s
FAILED tests/test_tm_bypass.py::test_graph_tm_bypass
```
The single failure is PRE-EXISTING and unrelated: it is a mock mismatch in
`app/agents/graph.py` (the test mocks `find_best_match` but the code calls
`find_exact_matches_batch`). Proven independent by stashing the TMX-PRICING-1
changes and re-running — it fails identically without this loop's code. Both
files (`graph.py`, `test_tm_bypass.py`) carry no diff from this loop.

### Ratchet
`scripts/ratchet.py` and `ratchet/baseline.json` are NOT present in this
worktree branch, so `python scripts/ratchet.py check` cannot run here. The
change introduces ZERO new TODO/FIXME (the one TODO is annotated
`TODO(TMX-PRICING-1a)` per the ratchet's issue-ref convention), ZERO bare
except, ZERO `Any`, ZERO `print()` — so no ratchet metric should move.
Mechanical pre-commit hooks (ruff, mypy) run and pass on commit.

## 6. Red team

Ran the Tier 2 checklist + A1-A10 against the diff.

- **Single source of truth**: confirmed all THREE app-layer pricing copies
  reduced to one. `documents.py` and `observability.py` now both derive from
  `model_pricing._PRICING`. The SDK package keeps its own (out of scope,
  TMX-PRICING-1b filed) — flagged so it isn't forgotten.
- **A3 (no silent fallback)**: the old `pricing.get(model, pricing["gpt-4o"])`
  is gone. Unknown models now raise `UnknownModelError`. Pinned by
  `test_unknown_model_raises_not_zero` (asserts it raises, NOT returns 0).
- **Behaviour identity**: `test_documents_estimate_equivalence` recomputes the
  exact legacy expression and asserts equality with `cost_for` for gpt-4o-mini.
  Green ⇒ no cost drift for the live model. NOTE: observability's gpt-4o rate
  CHANGED (old $5/$15 per-1M placeholder → canonical $2.50/$10). This is an
  intentional correction — but `estimate_cost` has ZERO callers in app/ (only
  `track_request` is wired), so no live cost recording changes. Documented so
  a reviewer isn't surprised.
- **Tier 2 #4 (boundaries)**: zero tokens, negative tokens (raises),
  cached-only, cached+standard — all tested. Float arithmetic uses
  `math.isclose(abs_tol=1e-12)`.
- **Typed (conventions)**: `ModelPricing` is a frozen dataclass, not a raw
  dict. No `Any`. mypy clean.
- **Tier 2 #18 (ratchet)**: no new TODO without issue-ref, no type:ignore, no
  bare except.

**Findings deliberated**:
1. *Should `/estimate` price the actual configured model
   (`settings.default_gpt_model`) instead of hardcoded gpt-4o-mini?* — Left as
   gpt-4o-mini to keep the change surgical and behaviour identical (the ticket
   asks for byte-identity). But the priced model and the reported model are
   now ONE constant, closing the "recorded cost for a different model than the
   recorded model" hazard the ticket called out. A follow-up could wire it to
   settings; out of scope here to avoid behaviour change.
2. *UnknownModelError subclassing KeyError* — chosen so existing
   `except KeyError` sites keep working, while the message is descriptive.

**Spawned follow-ups**:
- **TMX-PRICING-1a** — register gpt-4.1 + Claude tier once per-1M rates
  confirmed (TODO annotated in module).
- **TMX-PRICING-1b** — migrate `transmax_sdk/` pricing
  (`config.py`, `telemetry/cost.py`) onto a shared canonical source (needs a
  unit-reconciliation decision: SDK uses per-1k).

## 7. Fix

No code changes required from red team — first-pass clean (mypy + ruff green
on first run). Documented the observability gpt-4o rate correction (harmless,
no live caller) rather than papering over it.

## 8. Deploy

- [x] Commit: <filled post-commit>
- [ ] Pushed: NO — task explicitly says commit to worktree branch, do not push.
- [x] `.context/active_tasks.md`: not updated (isolated worktree loop; the
  orchestrator owns the board merge).
- [n/a] Ratchet baseline: ratchet tooling absent in this worktree.

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-03T00:00Z | — | `[Spec]` | Created. two-way; internal refactor. |
| 2026-06-03T00:10Z | `[Spec]` | `[Design]` | Frozen dataclass + per-1M registry; A3 raise on unknown. |
| 2026-06-03T00:20Z | `[Design]` | `[WIP]` | Test written first; RED (ModuleNotFoundError). |
| 2026-06-03T00:35Z | `[WIP]` | `[Verify]` | Module + 2 call-sites refactored. Focused tests green; mypy + ruff clean. Broad suite 874 passed, 1 pre-existing unrelated failure. |
| 2026-06-03T00:45Z | `[Verify]` | `[Done]` | Red team clean. Committed to worktree branch (no push). |
