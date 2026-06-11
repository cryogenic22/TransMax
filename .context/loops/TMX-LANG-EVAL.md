# TMX-LANG-EVAL — golden critical-safety eval data for en→ja and en→de

**State**: `[Done]` — `942a8cf` on origin/main
**Owner**: Platform & Observability (E9)
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — additive eval data + mirrored tests; no runtime change.
**Pre-mortem**: a wrong canonical translation would make the eval lie → traced each case through the real gate logic so the right defects fire/stay silent.
**Blast radius**: `tests/evals/data/en_ja/`, `tests/evals/data/en_de/` (new jsonl), `tests/evals/test_critical_safety_en_ja.py`, `tests/evals/test_critical_safety_en_de.py` (new).

**Gates**: G1 ✅ stability — eval coverage previously existed only for en→es; ja/de are hard pairs (CJK + decimal-comma) with Tier-1 packs but zero golden coverage. G2 N/A. G3 ✅ — 22 tests pass; keys match en_es exactly.

## Spec
- AC-1: ≥6 golden cases per pair (negation flip, dose tampering, unit change, frequency), canonical + tampered.
- AC-2: JSON keys identical to en_es (`id/kind/source/target/expected_defects/rationale`).
- AC-3: tests mirror `test_critical_safety_en_es.py` and pass deterministically.

## Test
`tests/evals/test_critical_safety_en_ja.py` + `..._en_de.py` — 22 passed (10 cases each + corpus check).

## Deploy
- [x] Commit: `942a8cf` (pushed to origin/main)
