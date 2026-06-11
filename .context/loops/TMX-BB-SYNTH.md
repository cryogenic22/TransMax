# TMX-BB-SYNTH — Synthetic pharma black book (Veridian Therapeutics)

**State**: `[Done]` — `2bd6ecd` on origin/main
**Owner**: Quality & Regulatory
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — additive data file + import-safe loader script; no schema change, no runtime path touched.
**Pre-mortem**: if the dataset is malformed, a demo seed could claim coverage it lacks → `validate_blackbook` fails loud (A3) before any row is written.
**Blast radius**: `scripts/black_book/veridian_blackbook.json` (new), `scripts/seed_synthetic_black_book.py` (new), `tests/test_synthetic_black_book.py` (new).

**Gates**: G1 ✅ end-user value — a near-real synthetic black book demonstrates term/forbidden/rule enforcement power for pilots. G2 N/A (no failure). G3 ✅ — dataset + idempotent loader, tested.

## Spec
- AC-1: dataset has 3 regulatory pairs (en→fr/de/es), ≥28 terms each, ≥4 forbidden each, ≥15 rules.
- AC-2: `validate_blackbook` rejects duplicate term sources / missing fields.
- AC-3: `seed_blackbook` is idempotent (second run creates 0) and tenant-scoped (A4); forbidden flags persist.

## Code
| File | Change |
|---|---|
| scripts/black_book/veridian_blackbook.json | 3 glossaries (36 terms each), 17 rules, 12 forbidden terms |
| scripts/seed_synthetic_black_book.py | load/validate + find-or-create org + idempotent seed |
| tests/test_synthetic_black_book.py | 6 tests (integrity + idempotency + forbidden persistence) |

## Test
`tests/test_synthetic_black_book.py` — 6 passed.

## Deploy
- [x] Commit: `2bd6ecd` (pushed to origin/main)
