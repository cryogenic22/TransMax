# TMX-UX-SEG-COUNT — Segment scope summary on the document review surface

**State**: `[Done]`
**Owner**: Reviewer Frontend · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way`.
**Pre-mortem**: if this fails, an auditor reviewing a long document has no up-front sense of scope (how many segments, how many translated, how many need review) and can silently miss segments.
**Blast radius**: `frontend/app/workspace/documents/[id]/page.tsx` (Segments view header).

**Gates**: G1 PASS (small derived summary from data already loaded). G3 PASS (the segments tab now shows total + translated + needs-review counts).

## 1. Task
The Segments view rendered column headers but no totals. Add a scope summary bar.

## 2. Spec
- AC-1: shows `N segment(s)`.
- AC-2: shows `M translated` (segments with `translated_text`).
- AC-3: shows `K need review` (segments with ≥1 gate violation), reusing the same `gate_results.violations` access the rows already use.

## 3. Design
A flex summary bar inserted above the grid header, derived inline from `segments` (no new state). Singular/plural on "segment".

## 4. Code
| File | Change |
|---|---|
| `frontend/app/workspace/documents/[id]/page.tsx` | scope summary bar above the segments grid |

## 5. Eval / Test
typecheck/lint/vitest(123)/build green. (Derived presentational counts; covered by typecheck + manual reasoning.)

## 6. Red team
Counts derive from the same `segments` array + the same `gate_results?.violations` access used per-row (consistent definition of "needs review"). Empty doc → "0 segments". Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: f4ad0b1 (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | review scope visible up front |
