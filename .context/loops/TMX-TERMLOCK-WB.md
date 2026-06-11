# TMX-TERMLOCK-WB — Word-boundary forbidden-term detection

**State**: `[Done — pending SHA record]`
**Owner**: Quality & Regulatory
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — tightens one deterministic check; revert restores substring matching.
**Pre-mortem**: a regex mistake could miss a forbidden term (under-detect) or over-detect — covered by both-direction tests (subword-no-fire + standalone-fire).
**Blast radius**: `app/services/quality_gate.py` forbidden-terms block (~+8 lines, fits after TMX-3400-lite headroom).

**Gates**: G1 ✅ (robustness — E6 term-lock is a regulated quality gate; naive substring matching false-fires on subwords ("ace" in "surface"), eroding reviewer trust in the gate). G2 ✅ — the subword false-positive reproduces with the old substring check. G3 ✅ — forbidden term fires on a standalone word / punctuated phrase but NOT inside a larger word; case-insensitive.

## Spec
- AC-1: a forbidden term that is word-like (alnum edges) matches only on word boundaries (`\b…\b`); does not fire inside a larger word.
- AC-2: terms with non-word edges (punctuated phrases) fall back to substring match (so phrases still detect).
- AC-3: matching stays case-insensitive.

## Test
`tests/test_termlock_wb.py` — subword-no-fire, standalone-fire, case-insensitive (3) + the drift-module test (1) = 4 passed.

## Deploy
- [x] Commit: `<pending>` (bundled with TMX-3400-lite)
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done — pending SHA record]` | substring → word-boundary; both-direction tests green |
