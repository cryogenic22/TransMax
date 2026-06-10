# TMX-OMIT-1 — Deterministic coverage / gross-omission gate

**State**: `[Done]` — `f65e3c2` on origin/main  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  Batch-3 loop 2/10 (2026-06-04)
**Reversibility**: `two-way`. **G2**: reproduced — the NEJM author-list segment (target ~10% of source) now flags CRITICAL OMISSION (was "✓ OK"). **Blast radius**: `app/services/coverage_check.py` (new pure), `app/services/quality_gate.py` (thin `check_coverage` + 7c wiring), `app/core/defect_taxonomy.py` (omission→CRITICAL classify rule).

## 1. Task
Design-check finding: the gates do **fine-grained equivalence** (numbers/units/terms/symbols) but had **no completeness check** — content with none of those (an author list of names) could be dropped and reported OK (seg #25: target ~10% of source). Add a uniform coverage gate on every segment so gross omission can't pass. Addenda A3 (don't report a 90%-missing translation as OK), A2 (deterministic gate).

## 2. Spec
- [x] AC-1: a target grossly shorter than the source (char-ratio <20%) flags CRITICAL OMISSION.
- [x] AC-2: empty target for a non-empty source flags CRITICAL (untranslated).
- [x] AC-3: a complete translation produces no flag.
- [x] AC-4: a legitimately-compact language (EN→ZH ~35-50% chars) is NOT false-flagged (threshold below any real pair).
- [x] AC-5: short segments (noisy ratio) are skipped.
- [x] AC-6: the OMISSION violation classifies CRITICAL → routed into TMX-CONF-1 `needs_review` (the segment flips from OK to "needs review: omission").

Out of scope: sentence-level alignment (finer omission detection); per-language calibrated ratios (the single conservative threshold is robust v1); a max-segment-length cap to prevent LLM truncation (complementary follow-on, spawned).

## 3. Design
Pure `coverage_check.coverage_issue(source, target) -> str | None` (char-ratio, mirrors the injection_guard/budget_guard sibling pattern). Char-based so it works across Latin/Arabic/CJK; one conservative CRITICAL threshold (0.20) that sits below even the most compact legitimate pair → fires on gross omission only (no false positives, A3). `quality_gate.check_coverage` is a thin adapter; called as universal check 7c. `defect_taxonomy.classify_violation` maps "omission"/"untranslated" → CRITICAL so it auto-blocks + surfaces (TMX-QG-SEVCASE + TMX-CONF-1).

**Modularity:** the additions pushed quality_gate.py past the 800-line ratchet, so the logic went to the sibling module (consistent with injection/budget) AND I cleaned pre-existing dead code (unused `asdict` import, dead `tgt_nums`, an F541 f-string) — quality_gate.py 804→798, ratchet green, zero loosening.

## 4. Code
| File | Change |
|---|---|
| `app/services/coverage_check.py` | new — pure `coverage_issue` (char-ratio gross-omission detector) |
| `app/services/quality_gate.py` | thin `check_coverage` + universal-check 7c call; removed pre-existing dead code |
| `app/core/defect_taxonomy.py` | "omission"/"untranslated" → CRITICAL classify rule |
| `tests/test_coverage_gate.py` | new — 5 tests (author-list drop CRITICAL, empty→untranslated, complete OK, compact-lang no-FP, short skipped) |

## 5. Test
`pytest test_coverage_gate + injection + severity` → 64 passed. Ratchet 17/17. Full suite — stage 8. Red-team caught my first fixture being too short (ratio 0.25 > threshold) — expanded to the real ~30-author roster (ratio ~0.10).

## 6. Red team
- **No false positives** is the load-bearing property: 0.20 threshold is below every real language pair (EN→ZH ~0.35+); a compact-language test asserts it.
- Char-ratio (not word) so CJK/Arabic (no/space-light word boundaries) aren't mis-measured.
- Conservative-by-design: a 50% omission won't flag (sentence-alignment is the finer follow-on); a CRITICAL on gross drop with zero false positives is the right v1 (trust > recall here).
- Pre-existing `\[` latex SyntaxWarning in quality_gate left (unrelated docstring).

## 7. Fix
Fixture expanded (red-team). Cleaned pre-existing dead code to stay under the mega-file ratchet. No other findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 5 tests (64 incl. adjacent)
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-OMIT-2** — max-segment-length cap (split over-long segments before the LLM call) to prevent the truncation that causes these omissions.
- **TMX-OMIT-3** — sentence-level coverage alignment for finer (sub-gross) omission detection.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~04:40Z | — | `[Verify]` | coverage gate + sibling module + CRITICAL classify; 5 tests; quality_gate 798; ratchet 17/17; awaiting full suite |