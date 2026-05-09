# TMX-3410-fix — `_find_missing_numbers` digit-only-boundary fix

**State**: `[Done]` pending push
**Owner**: Quality & Regulatory pod (Antigravity / Pod B)
**Sprint**: 1
**Started**: 2026-05-09
**Closed**: 2026-05-09

---

## 1. Task

The TMX-3410 helper `BaseLanguagePack._find_missing_numbers` uses `\b\d+\b` for both source extraction and target search. The `\b` (word-boundary) zero-width assertion fails in two important real-world cases:

1. **CJK adjacency**: in `服用500毫克`, both `用` and `5` are `\w` characters in Python 3 regex (CJK ideographs are Unicode word chars). No `\b` exists between them, so `\b500\b` doesn't match. → Chinese number-preserved test was failing: violation incorrectly raised when number IS present.

2. **Letter-glued digits**: in `Take 10mg.`, both `0` and `m` are `\w`, so no `\b` exists between them. `\b\d+\b` fails to extract `10` from the source at all. → Japanese `test_ja_number_width` was failing: missing-number tamper not detected because the source never produced any candidate.

This was a blind spot in TMX-3410: my regression-guard tests used space-separated digits (`200 mg`, `5 tablets`) and Latin-only target text. They didn't exercise the two failing cases.

**Blast radius**: `app/services/language_packs/base.py` only — every pack delegates here. A single regex change fixes 8 packs at once.

**Addenda**: A1 (audit-by-default — silent dose-tampering acceptance is the worst kind of broken-window), A2 (quality is enforced at gates).

## 2. Spec — acceptance criteria

- [ ] AC-1: `_find_missing_numbers` extracts digit runs from source without requiring `\b` (so `10mg` produces `10`).
- [ ] AC-2: `_find_missing_numbers` matches a number in target if and only if it is not adjacent to another digit on either side (digit-only boundary). No false-positive for CJK adjacency, no silent miss for letter-glued digits.
- [ ] AC-3: Existing TMX-3410 tests in `tests/test_lang_packs_numeric_word_boundary.py` stay green (15 cases).
- [ ] AC-4: Existing TMX-3408 tests in `tests/test_spanish_pack_numbers.py` stay green (7 cases).
- [ ] AC-5: New tests cover the two regression cases:
  - CJK-adjacent canonical match (zh, ja) — must NOT fire
  - Letter-glued digit tamper (10mg → 100mg, en→ja) — MUST fire
- [ ] AC-6: `tests/test_language_intelligence.py::TestChinesePack::test_number_preserved` and `tests/test_language_engines.py::test_ja_number_width` go from FAIL → PASS.
- [ ] AC-7: Ratchet stays 17/17 green.

**Out of scope**: ordinals like `1st`, `2nd` — these will start producing false-positives for non-Latin targets that translate to "primero" / "first" wording. Acceptable for now (preferable to silent dose tampering); a future ticket can add an ordinal-stripping prepass.

## 3. Design

**Why `\b` failed**: in Python 3, `\b` is the boundary between `\w` and non-`\w`, where `\w` includes Unicode letters and digits. CJK ideographs are letters → word chars. ASCII letters are also word chars. So `\b` only fires at:
- Whitespace ↔ digit
- Punctuation (some) ↔ digit
- String start/end ↔ digit

It does NOT fire at:
- CJK letter ↔ digit
- ASCII letter ↔ digit (the `10mg` case)

**Why digit-only-boundary works**: `(?<!\d)X(?!\d)` says "X is not surrounded by other digits". This is the actually-load-bearing semantic for TMX-3408's tampering check (catch `10` vs `100`), and it composes correctly with letter-glued and CJK-adjacent cases.

```python
# Source: any digit run (greedy with optional decimal/thousand separator)
nums = re.findall(r'\d+(?:[.,]\d+)?', source_text)

# Target: digit-only boundary
re.search(rf'(?<!\d){re.escape(form)}(?!\d)', target_text)
```

This is a 2-line edit in `_find_missing_numbers`.

**Alternatives rejected**:
- Locale-specific tokenisers (jieba for zh, MeCab for ja): heavyweight, version-pinned suppliers, runtime cost. Overkill for "is this number present?".
- Unicode-aware regex with `regex` package: another dependency for a one-line fix.
- Per-pack overrides: pushes the burden onto every pack maintainer; defeats the consolidation TMX-3410 just landed.

## 4. Code

| File | Change |
|---|---|
| `app/services/language_packs/base.py` | `_find_missing_numbers`: drop `\b` from source-extraction regex; replace target-search `\b...\b` with `(?<!\d)...(?!\d)` |
| `tests/test_lang_packs_numeric_boundary_extra.py` | New — CJK adjacency + letter-glued digit cases |

## 5. Eval / Test

```
$ pytest tests/test_lang_packs_numeric_word_boundary.py tests/test_spanish_pack_numbers.py tests/test_language_intelligence.py tests/test_language_engines.py tests/test_lang_packs_numeric_boundary_extra.py -v
```

Expected: all green.

## 6. Red team

- **CLEAN**. Tier 2 22-item self-review on the diff:
  - One-line regex change in shared helper, 8 packs benefit; no per-pack divergence reintroduced.
  - New tests cover the two failure modes I missed: CJK adjacency (zh / ja / ko) AND letter-glued digits (`10mg`).
  - `(?<!\d)X(?!\d)` is the correct semantic for "not surrounded by digits" — composes cleanly with substring-tamper detection from TMX-3408 (verified via re-run of all TMX-3410 tests, 24/24 still green).
  - 💡 Ordinals (`1st`, `2nd`) now extract `1`, `2` from the source. If the target is non-Latin and translates the ordinal as a word ("primero", "first"), the gate will raise a false-positive. Trade-off accepted: false-positives are ergonomic, dose-tampering is safety-critical (A2). A future ticket could add an ordinal-prepass that strips `\b\d+(?:st|nd|rd|th)\b` from source before extraction.
  - 💡 Cross-checked against pre-existing TMX-3408 case `10mg → 100mg`: source `10mg` now extracts `10` (didn't before because of `\b`); target `100mg` search `(?<!\d)10(?!\d)` correctly fails (lookahead is `0`, a digit). Tamper still fires.

## 7. Fix

No fix iterations needed. Single-pass fix (one helper, +9 tests).

## 8. Deploy

- [x] Code: `app/services/language_packs/base.py` (lines ~16-46 — 2-line regex change)
- [x] Tests: `tests/test_lang_packs_numeric_boundary_extra.py` (11 tests, all green)
- [x] Repaired tests: `test_language_intelligence.py::TestChinesePack::test_number_preserved` and `test_language_engines.py::test_ja_number_width` go FAIL → PASS
- [x] Full suite: 716 passed / 2 skipped (3 pre-existing flakes excluded — see test_reverse_translate, test_tamper_detection — pass in isolation, fail under full-suite ordering; spawned TMX-3018-flake as follow-up)
- [x] Ratchet: 17/17 green
- [ ] Commit + push (next)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T11:45Z | — | `[Spec]` | TMX-3410 regression caught during TMX-3606 baseline |
| 2026-05-09T11:55Z | `[Spec]` | `[WIP]` | Fix + 11 new tests |
| 2026-05-09T12:00Z | `[WIP]` | `[Done]` (pending commit + push) | 24/24 TMX-3410 tests green; both regressed tests pass; ratchet green |
