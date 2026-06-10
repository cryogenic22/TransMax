# TMX-OMIT-2 — Max-segment-length cap (prevent LLM truncation)

**State**: `[Done]` — `afd3a83` on origin/main  ·  **Owner**: Document Pipeline  ·  **Sprint**: 2  ·  Batch-3 loop 3/10 (2026-06-04)
**Reversibility**: `two-way`. **Blast radius**: `app/services/segmenter.py` (post-split). **G2**: a 120-author block (>1000 chars) reproduces the over-long segment; the cap splits it with no content loss.

## 1. Task
Remove the ROOT CAUSE behind the dropped author list (TMX-OMIT-1 caught the symptom): a ~1500-char author byline was ONE segment fed whole to the LLM, which truncated it. Cap segment length so over-long blocks are sub-split before the LLM sees them. Addenda A3 (don't feed the model something it'll silently truncate), document-fidelity.

## 2. Spec
- [x] AC-1: a segment > `MAX_SEGMENT_CHARS` (1000) is sub-split; each piece ≤ the cap.
- [x] AC-2: splitting loses NO content (every author present after rejoin).
- [x] AC-3: normal prose sentences (< cap) are unaffected (returned as-is).
- [x] AC-4: a short byline stays one segment (TMX-3801 regression guard).
- [x] AC-5: a long clause with no `; , :` still gets hard-wrapped on whitespace (never one giant segment).

Out of scope: re-joining sub-segments on export (each translates independently — fine for lists; prose coherence across a forced split is a known trade-off, generous threshold minimizes it).

## 3. Design
A post-segmentation cap in `segmenter.py`: `_cap_length` sub-splits any sentence over `MAX_SEGMENT_CHARS` on clause boundaries (`_CLAUSE_RE` = `; , :`), falling back to whitespace hard-wrap. Threshold deliberately generous (1000 chars) so only pathological blocks (lists, mis-merged runs) split — ordinary sentences are well under it. Applied to both `segment()` return paths.

## 4. Code
| File | Change |
|---|---|
| `app/services/segmenter.py` | `MAX_SEGMENT_CHARS` + `_cap_length`/`_split_long`/`_hard_wrap`; applied in both `segment()` returns |
| `tests/test_segment_length_cap.py` | new — 5 tests (split, no-loss, prose-unaffected, short-byline guard, hard-wrap) |

## 5. Test
`pytest segment_length_cap + segmenter_credentials + segmenter` → 30 passed (no regression to the byline test). Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Generous threshold → prose untouched; only over-long blocks split. The short-byline test guards against over-splitting.
- No content loss (asserted) — the whole point vs the LLM's silent truncation.
- Forced splits of long *prose* could affect cross-sentence coherence; the high threshold makes this rare, and lists (the real case) split cleanly on commas. Re-join-on-export is a possible follow-up.
- Pairs with TMX-OMIT-1: cause (this) + symptom (coverage gate) both covered.

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 5 tests (30 incl. segmenter suite)
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~05:05Z | — | `[Verify]` | length cap + 5 tests; no byline regression; ratchet 17/17; awaiting full suite |