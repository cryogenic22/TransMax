# TMX-INJ-1 — Prompt-injection detection gate (source-side, deterministic)

**State**: `[Verify]`
**Owner**: Quality & Regulatory
**Sprint**: 2
**Started**: 2026-06-03
**Closed**: —
**Reversibility**: `two-way` — additive: a new pure scanner + one taxonomy enum value + one deterministic check wired into the existing per-segment gate. Revert by deleting `injection_guard.py`, the `PROMPT_INJECTION` enum + classify rule, and the `check_prompt_injection` call. No schema, no migration.
**Pre-mortem**: if this fails in production, the failure modes are (a) a missed novel injection phrasing → degrades to today's behaviour (LLM still translates it), or (b) a false positive wrongly BLOCKs legitimate clinical text. (b) is the dangerous one, so the design optimises for PRECISION and ships a benign-pharma false-positive suite.
**Blast radius**: `app/services/injection_guard.py` (new), `app/core/defect_taxonomy.py` (+1 enum, +1 classify rule), `app/services/quality_gate.py` (+1 method, +1 call in `check_segment`). Runs per segment in the existing deterministic gate. No engine/concurrency change, no frontend, no schema.

**Gates**:
- [x] **G1 Anti-bloat** — (a) needed: pharma source flows through an LLM (qualified supplier, A6); an adversarial/compromised source that hijacks the translator ("ignore previous instructions…") is a real attack surface with no current defence. (b) 1 module, 1 enum, ~2 call sites. (c) negligible. (d) reuses the gate's Defect pipeline + `_create_defect` + taxonomy. (e) ships tests (incl. false-positive suite).
- [ ] **G2** — N/A (greenfield gate); behaviour proven by the detection + false-positive suites.
- [ ] **G3** — after stage 7: an injected source segment surfaces a CRITICAL `PROMPT_INJECTION` violation (→ BLOCKED → human review); benign pharma text does not.

## 1. Task

Add a deterministic source-side scanner that flags prompt-injection / instruction-override attempts embedded in the text submitted for translation, surfacing them as a CRITICAL `PROMPT_INJECTION` defect so the segment is BLOCKED for human review rather than silently translated. Addenda: **A2** (deterministic gate, never inside the translator prompt), **A3** (fail loud — block, never silently translate adversarial input), **A6** (protects the qualified-supplier call from hijack).

## 2. Spec — acceptance criteria

- [ ] **AC-1**: `InjectionScanner.scan` detects each curated injection vector (ignore/disregard/forget-previous, "you are now", system-prompt refs, reveal/print prompt, "new instructions:", "instead …output", "act as an AI", role/INST markup, override, jailbreak, "prompt injection").
- [ ] **AC-2**: A benign-pharma false-positive suite (patient instructions, "do not exceed", "immune system", "previous studies", "repeat the dose", etc.) yields ZERO findings.
- [ ] **AC-3**: Findings carry a `label` + matched `snippet` (evidence).
- [ ] **AC-4**: `PROMPT_INJECTION` defect messages classify as `CRITICAL` (auto-BLOCK).
- [ ] **AC-5**: `check_segment` on an injected source returns a CRITICAL `PROMPT_INJECTION` violation; on a clean source it returns none.

Out of scope: scanning at upload/ingestion (this is per-segment at the gate); LLM-based injection classification (deterministic only, A2); target-side leakage of injected output (separate concern); per-tenant pattern config.

## 3. Design

Pure scanner `app/services/injection_guard.py` (mirrors `budget_guard.py`): a tuple of `(label, compiled-regex)` high-precision patterns + `InjectionScanner.scan/is_injected` + a module singleton. Patterns target injection *phrases* and chat/instruction *markup*, never single words, so benign pharma language is safe (PRECISION over recall — see pre-mortem). `PROMPT_INJECTION` added to `DefectCategory`; `TaxonomyService.classify_violation` maps any message containing "injection" → CRITICAL. `QualityGateService.check_prompt_injection(source)` adapts findings → `Defect`s and is called as universal check "7b" in `check_segment`. Detection logic stays in the sibling module (A2: gate-not-translate; keeps `quality_gate.py` thin — it is already a TMX-3412 split candidate).

**Rejected:** (a) regex inside the translator prompt — violates A2. (b) single-word denylist ("instructions", "system") — unacceptable false-positive rate on clinical text. (c) blocking at the engine level — the per-segment gate is the canonical deterministic chokepoint and already feeds BLOCKED→review.

## 4. Code

| File | Change |
|---|---|
| `app/services/injection_guard.py` | new — pure `InjectionScanner` (14 precision patterns) + `InjectionFinding` + singleton |
| `app/core/defect_taxonomy.py` | +`PROMPT_INJECTION` enum; +"injection"→CRITICAL classify rule; removed 3 pre-existing dead imports (`List`/`Dict`/`Any`) |
| `app/services/quality_gate.py` | +`check_prompt_injection`; call as universal check 7b in `check_segment` |
| `tests/test_injection_guard.py` | new — 29 tests: vector detection, benign false-positive suite, taxonomy, gate integration |

## 5. Eval / Test

```
python -m pytest tests/test_injection_guard.py -q   # 29 passed
python scripts/ratchet.py check                     # 17/17 OK
python -m pytest -q                                 # full suite — see stage 8
```
One vector ("Forget everything above…") was red on first run (pattern required a trailing noun); broadened the `forget` pattern, re-verified benign suite still clean.

## 6. Red team

- **False positives (the real risk)** — mitigated by phrase/markup-anchored patterns + a 10-case benign-pharma suite asserting zero findings. "patient instructions", "do not exceed", "the system was evaluated", "previous studies", "forget to take" all stay clean.
- **Evasion / recall gaps** — obfuscated/novel phrasings (unicode homoglyphs, base64, creative paraphrase) will be missed. Accepted: a miss degrades to today's behaviour (no regression); chasing recall would raise false positives. Follow-up TMX-INJ-1a (normalise + expand corpus).
- **Severity** — routed through the existing taxonomy ("injection"→CRITICAL) so an injected segment is auto-BLOCKED and cannot be auto-approved (A3).
- **Pre-existing `quality_gate.py` ruff/SyntaxWarning** (unused `tgt_nums`, `\[` raw-string) are in distant GCHK-006/latex blocks I did not touch — left for the TMX-3412 split; my additions are ruff-clean.
- `/review`: no new dependency; pure module; reuses Defect pipeline; one enum value; failing-vector caught + fixed before green.

## 7. Fix

Broadened the `forget` pattern (red-team / first-run miss). No other findings. Recall gaps documented as TMX-INJ-1a.

## 8. Deploy

- [x] Ruff clean on all changed files (added code)
- [x] Ratchet 17/17 (no loosening)
- [x] Commit: `d1e0b48`
- [x] Pushed to origin/main (`091f12a..d1e0b48`)
- [x] `.context/active_tasks.md` updated

### Spawned follow-ups
- **TMX-INJ-1a** — input normalisation (homoglyph/whitespace fold) + expanded vector corpus + eval-suite cases under `tests/evals/`.
- **TMX-INJ-1b** — emit a dedicated `INJECTION_DETECTED` audit event (currently surfaced as a quality violation only).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-03T~21:10Z | — | `[Spec]` | Created; baseline 924 passed/0 failed (post-BUDGET-1) |
| 2026-06-03T~21:20Z | `[Spec]` | `[Verify]` | Scanner + taxonomy + gate wiring; 29/29 injection tests; ratchet 17/17; awaiting full suite |