# TMX-INJ-1a — Injection-scanner hardening (normalization + expanded vectors)

**State**: `[Verify]`  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  Loop 3/10 (2026-06-04 batch)
**Reversibility**: `two-way`. **Blast radius**: `app/services/injection_guard.py` only (feeds `quality_gate.check_segment`).

## 1. Task
Raise the prompt-injection scanner's recall against obfuscation without hurting precision (the load-bearing constraint from TMX-INJ-1). Two levers: (a) normalize input before matching, (b) add a few high-precision vectors. Addenda A2 (deterministic gate), A3.

## 2. Spec
- [x] AC-1: zero-width-char and full-width obfuscation of "ignore previous instructions" is detected (NFKC + zero-width strip + whitespace collapse).
- [x] AC-2: new vectors detected — `begin your response with`, `you must output/respond/…`, `translate this as "<literal>"`.
- [x] AC-3: the benign-pharma false-positive suite stays 100% clean after normalization + new patterns.
- [x] AC-4: `translate this as accurately…` (no quote) is NOT flagged (the new pattern is quote-anchored).

## 3. Design
`_normalize`: `unicodedata.normalize("NFKC", …)` (folds full-width/compatibility forms) + strip zero-width chars (ZWSP/ZWNJ/ZWJ/WJ/BOM) + collapse whitespace; `scan` normalizes first. Normalizing benign text never creates an injection phrase, so recall rises with no precision cost (proven by re-running the benign suite on the normalized path). New patterns kept phrase/quote-anchored for precision.

## 4. Code
| File | Change |
|---|---|
| `app/services/injection_guard.py` | `_normalize` + zero-width table; `scan` normalizes; +3 precision patterns (begin_response_with, you_must_output, translate_as_literal) |
| `tests/test_injection_guard.py` | +18 cases (4 obfuscation, 3 new vectors, benign-still-clean re-run, quote-anchor negative) → 49 total |

## 5. Test
`pytest tests/test_injection_guard.py` → 49 passed. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Normalization can only fold characters together, never fabricate a trigger phrase → benign suite re-run confirms zero new false positives.
- `translate_as_literal` is quote-anchored to avoid "translate as accurately" false positives (negative test added).
- `you_must_output` requires an output-verb so "you must consult your doctor" is safe.
- Recall is still bounded (paraphrase/semantic evasion not caught) — acceptable; a miss degrades to pre-INJ-1 behaviour. Parent TMX-INJ-1 noted this.

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 49 tests
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~00:40Z | — | `[Verify]` | normalize + 3 vectors; 49 tests; ratchet 17/17; awaiting full suite |