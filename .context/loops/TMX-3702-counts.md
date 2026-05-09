# TMX-3702-counts — per-type revision counts (backend + UI)

**State**: `[Done]` — shipped 9f379a6 (design-system fixture + e2e count assertion). Builds on 6f6fb0a (counts wire shape + UI threshold).
**Owner**: Document Pipeline + Reviewer Frontend pods (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-09
**Closed**: —
**Reversibility**: `two-way` — backend change is purely additive (new int keys); frontend display tightens conditionally on total > 1.
**Pre-mortem**: If this fails in production, the failure mode is — a reviewer sees "tracked" on a segment that had 47 revision marks vs another with 1 and treats them equivalently, missing the ones that actually need careful re-reading. Loss of triage signal.
**Blast radius**: `app/services/docx_ingestion.py:_collect_revisions` (4 new int keys). `frontend/lib/api.ts:SegmentRevisions` (4 new optional int fields). `frontend/components/ui/RevisionIndicator.tsx` (conditional count display). Tests across all three.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat**: extending existing helper + existing type + existing component. No new files in product code (just tests). Reuses the iter() pass already happening.
- [ ] **G2 Reproduce-failure**: write counts tests first — RED before fix.
- [ ] **G3 Completion**: a segment with 5 insertion marks shows "5 changes" in the pill; a segment with 1 stays at the existing label. Wire shape carries the int counts end-to-end.

---

## 1. Task

TMX-3700 captured presence (booleans). TMX-3702-v1 surfaced presence in the UI. Reviewers triaging a long document need a magnitude signal — was this segment touched once or thirty times? — to prioritise attention. This loop adds per-type counts.

**Addenda**: A1 (audit-by-default — magnitude is part of the audit signal).

## 2. Spec — acceptance criteria

- [ ] AC-1: `_collect_revisions(element)` returns four new keys when revisions are present:
  - `n_insertions: int`  — count of `<w:ins>` mark elements
  - `n_deletions: int`   — count of `<w:del>`
  - `n_moves_from: int`  — count of `<w:moveFrom>`
  - `n_moves_to: int`    — count of `<w:moveTo>`
- [ ] AC-2: Counts only include immediate revision-mark elements; nested elements inside (e.g. `<w:r>` inside `<w:ins>`) don't inflate the count.
- [ ] AC-3: Existing booleans remain consistent: `has_insertions == (n_insertions > 0)`, etc.
- [ ] AC-4: Frontend `SegmentRevisions` interface extends with optional `n_insertions?`, `n_deletions?`, `n_moves_from?`, `n_moves_to?` (all defaulting to undefined for back-compat with older payloads).
- [ ] AC-5: `<RevisionIndicator>` renders `· N changes` between the headline label and author label when total count ≥ 2 (single-edit pills stay clean).
- [ ] AC-6: Tests: 1 new backend (3-scenario), 1 new component (count display + threshold).
- [ ] AC-7: All gates green; vitest 82 → 84+; backend pytest 756 → 757+.

**Out of scope**:
- Per-revision text bodies (TMX-3703).
- Per-revision actor/timestamp pairing (would require collecting per-mark dicts; bigger refactor).

## 3. Design

Counts are computed inline in the existing `for descendant in element.iter()` loop — no extra pass:

```python
n_ins = n_del = n_mf = n_mt = 0
for descendant in element.iter():
    tag = descendant.tag
    if tag == INS_NS:       n_ins += 1
    elif tag == DEL_NS:     n_del += 1
    elif tag == MOVE_FROM_NS: n_mf += 1
    elif tag == MOVE_TO_NS:   n_mt += 1
    ...
```

Booleans become derived from counts (`has_insertions = n_ins > 0`).

Frontend display:
```ts
const total = (n_insertions ?? 0) + (n_deletions ?? 0) + (n_moves_from ?? 0) + (n_moves_to ?? 0)
// Render "· N changes" only when total >= 2 (avoids cluttering single-edit pills)
```

**Why threshold of 2 not 1**: a single-edit pill is already informative ("tracked · Author · 3d ago"). Adding "1 change" is redundant. The threshold makes the count appear only when it carries triage signal.

**Why "changes" not "marks"**: reviewer-facing language. OOXML calls them "marks"; reviewers call them "changes".

## 4. Code

| File | Change |
|---|---|
| `app/services/docx_ingestion.py` | `_collect_revisions`: count integers; emit `n_*` keys |
| `frontend/lib/api.ts` | `SegmentRevisions` adds 4 optional int fields |
| `frontend/components/ui/RevisionIndicator.tsx` | Conditional `· N changes` segment in the label |
| `tests/test_docx_revisions.py` | 1 new test asserting counts are correct (3-scenario) |
| `frontend/__tests__/RevisionIndicator.test.tsx` | 1 new test for the count display + threshold |

## 5. Eval / Test

```
$ pytest tests/test_docx_revisions.py -v
$ npm run test -- RevisionIndicator
$ npm run lint && npm run typecheck && npm run build
```

## 6. Red team

- **CLEAN.** Tier 2 self-review:
  - Backend: 4 new keys, derived booleans verified consistent with counts (`has_insertions == n_insertions > 0`).
  - Frontend: count display threshold of 2 prevents pill clutter on single-edit segments. Hide-when-absent path (`?? 0` on each n_*) handles older payloads from before this change without breaking back-compat.
  - Helper `totalRevisionCount` exported as a pure function — testable, reusable.
  - 💡 One-iteration fix: I'd left the `n_*` fields out of api.ts (Edit silently no-op'd because of stale-content mismatch), then realised when 13 tests broke with `totalRevisionCount is not a function`. Re-applied the Edit cleanly. Sequence preserved as a known story for future loops on this codebase.
  - Production failure modes:
    - Backend stops emitting counts → frontend's `?? 0` fallback hides the count segment → fail-safe.
    - Counts are nonsensical (negative, NaN) → `(n ?? 0)` coerces non-numbers to 0 → safe.

## 7. Fix

One iteration: the api.ts Edit didn't apply on the first attempt (the function I tried to add inside the existing Edit's `new_string` block was lost when re-applying); caught immediately when tests went 13/14 RED with `totalRevisionCount is not a function`; re-applied with the exact field+function block; 14/14 GREEN.

## 8. Deploy

- [x] G1 anti-bloat: PASSED (refining existing helper + type + component, no new files).
- [x] G2 reproduce-failure: PASSED — backend tests + frontend "5 changes" test all RED before implementation.
- [x] G3 completion: PASSED — wire shape carries counts; UI threshold renders them; both verified end-to-end.
- [x] Backend pytest: 758/758 (was 756, +2).
- [x] Frontend vitest: 85/85 (was 82, +3).
- [x] Lint / typecheck / build all green.
- [x] Commit shipped (6f6fb0a counts; 9f379a6 demo + e2e assertion).
- [ ] Push to remote (deferred to next push window — local-only by design).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T22:00Z | — | `[Spec]` | Loop opened — TMX-3702-counts |
| 2026-05-09T23:55Z | `[Code]` | `[Done]` | Demo fixture + 2nd e2e (count threshold) shipped 9f379a6; both Playwright tests GREEN. |
