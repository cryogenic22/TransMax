# AI Eval Harness

Golden-case suites that exercise the deterministic quality gates against canonical and tampered translations.

## Why this exists

Per the v3.0 plan and the headless agent spec (Track 3 — Behavioural & Golden-Path), every release must prove:

- **Canonical translations produce zero critical defects.** A correct EN→ES translation of a SmPC must not trigger NEGATION_FLIP or NUMERIC_MISMATCH.
- **Tampered translations are caught.** A deliberate negation drop, decimal trap, or unit swap MUST fire the corresponding critical defect every time.

Without this harness we can't claim our quality gates work — we can only hope.

## What it tests (today)

`data/en_es/critical_safety.jsonl` — 10 cases covering:
- 6 tampered: negation flip ×2, numeric mismatch ×2, unit mismatch ×1, frequency mismatch ×1
- 4 canonical: structurally clean translations that must NOT trigger any critical defect

The suite is **deliberately offline** — no LLM calls. The evaluator is the deterministic `QualityGateService.check_segment(...)`. This makes the suite fast (<5s on a laptop) and CI-runnable without API keys.

Live LLM-driven golden runs (Track 3 full scope) gate on `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` and live under `tests/evals/live/` — deferred until v3.0 epic E7.9 lands.

## How to run

```bash
# Via pytest (CI default)
pytest tests/evals/ -v

# Via the standalone runner (writes a JSON report)
python -m tests.evals.runner --report-json eval_results/latest.json

# Specific suite only
pytest tests/evals/test_critical_safety_en_es.py -v
```

## Adding a new case

Append a JSONL line to the appropriate suite. Required fields:

```json
{
  "id": "negation_007",
  "kind": "tampered",
  "source": "Do not exceed 4 doses in 24 hours.",
  "target": "No exceda 4 dosis en 24 horas.",
  "expected_defects": [{"category": "NEGATION_FLIP", "severity": "CRITICAL"}],
  "rationale": "Negation preserved; this case proves the gate doesn't false-positive on correct preservation."
}
```

Field rules:
- `id` — unique within the suite; use `<defect_class>_<NNN>` (`negation_007`, `unit_012`).
- `kind` — `canonical` (translation is correct) or `tampered` (translation has a deliberate defect).
- `expected_defects` — list of `{category, severity}`. For `canonical` cases, leave it `[]`. Categories from `app/core/defect_taxonomy.py`.
- `rationale` — one line explaining what the case proves. Required; this is the spec for the case.

## Adding a new language pair

1. Create `data/<src_lang>_<tgt_lang>/critical_safety.jsonl` with at least 4 tampered + 4 canonical cases.
2. Add a sibling pytest entry: `test_critical_safety_<src_lang>_<tgt_lang>.py` (copy from `test_critical_safety_en_es.py`, change the data path and the `target_lang` argument).
3. Register the suite in `runner.py`'s `SUITES` list.
4. Verify the corresponding language pack exists in `app/services/language_packs/` — the harness depends on it for negation, numbers, punctuation, variants. If the pack is missing, the gate degrades silently and false negatives are possible.

## Cases that intentionally start failing

Some cases here may fail today because the relevant language pack rule isn't implemented yet. **A failing case is itself a deliverable** — it captures the gap and forces the gap to be filled before the v3.0 release. Don't xfail or skip cases just to keep CI green; either:

- the case is wrong (fix it), or
- the gate is wrong (fix it as a v3.0 ticket), or
- the language pack is missing the rule (fix it as a v3.0 ticket).

Use `--scope harness-only` in CI for hard-blocking; relax to `--scope full` once live-LLM tracks land.

## Where this fits in the v3.0 plan

This is the seed for v3.0 epic **E7.9** ("Eval harness — golden sets per language pair; CI release-blocker on critical-defect > 0"). The v3.0 plan extends this harness to:

- en→es / en→fr / en→de (Sprint 4, golden EMA SmPC samples)
- en→ar / en→ja with language-pack-aware tokenisation (Sprint 5)
- BERTScore-based reflexion check on the BackTranslator agent (Sprint 4)
- Drift detection: weekly report of per-pair quality KPIs (Sprint 5)

Until those land, this minimum harness is the baseline.

## Where this fits in the headless-spec validation strategy

This is **Track 3 — Behavioural & Golden-Path**, partially implemented. Track 3 ultimately requires 50–250 real anonymised pharma documents (SmPC, PIL, IFU, ICF, CSR, CTD Module 2.5). The current 10 synthetic cases are the seed; we grow toward 50 by GA and 250 by Phase 3.

## Performance

The suite must stay fast. Budget:
- ≤ 5s for the full suite on a laptop
- ≤ 30s in CI (cold-start with all language packs loading)

If a case adds significant runtime (e.g. it requires a large language-pack lookup), profile it and either optimise or split the suite.
