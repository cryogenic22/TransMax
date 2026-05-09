# TMX-3704-pairing — capture w:id for cross-block move correlation

**State**: `[Done]` pending push
**Owner**: Document Pipeline (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-09
**Closed**: —
**Reversibility**: `two-way` — purely additive (two new optional list[str] keys on the revisions dict; existing consumers untouched).
**Pre-mortem**: If this fails in production, the failure mode is — a reviewer sees "moved out" on §3 and "moved in" on §7 with no way to correlate them, treating two halves of the same edit as two independent move events. The audit trail loses the pairing relationship that DOCX explicitly encoded.
**Blast radius**: `app/services/docx_ingestion.py:_collect_revisions` (2 new keys: `move_from_ids`, `move_to_ids`). Tests in `tests/test_docx_revisions.py`. No frontend wiring in this ticket — pure data-preservation pass so consumers (UI, audit ledger, export) can pair when ready.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat**: extending the existing iter() pass; no new helper, no new module, two new keys on the existing return dict. Reuses the AUTHOR_ATTR / DATE_ATTR pattern (just `w:id` instead).
- [ ] **G2 Reproduce-failure**: write tests asserting `move_from_ids` / `move_to_ids` appear with the correct values BEFORE the implementation lands.
- [ ] **G3 Completion**: a doc with `<w:moveFrom w:id="3">` in para A and `<w:moveTo w:id="3">` in para B yields blocks where both carry id `"3"` in the appropriate list, so a downstream consumer can pair them by intersection.

---

## 1. Task

OOXML pairs `<w:moveFrom>` and `<w:moveTo>` via a shared `w:id` attribute. TMX-3704 (shipped) split the boolean flags into `has_moves_from` / `has_moves_to`, but the `w:id` was never captured — so a consumer can see "this block had text leave" and "this block had text arrive", but cannot correlate them when they're in different paragraphs (the common case). This loop captures the IDs.

**Addenda**: A1 (audit-by-default — pairing IDs are part of the audit signal), A5 (stable IDs end-to-end — `w:id` is an ID the source document gave us; we should not throw it away).

## 2. Spec — acceptance criteria

- [ ] AC-1: `_collect_revisions(element)` returns two new keys when revisions are present:
  - `move_from_ids: list[str]` — IDs of `<w:moveFrom>` marks within the element (deduplicated, ordered by first occurrence)
  - `move_to_ids: list[str]` — IDs of `<w:moveTo>` marks within the element
- [ ] AC-2: When a moveFrom or moveTo lacks the `w:id` attribute (malformed input), it is skipped silently — the corresponding count still increments, but no entry is added to the IDs list. (Don't crash on noisy DOCX inputs.)
- [ ] AC-3: Existing keys remain unchanged: `has_moves_from`, `has_moves_to`, `has_moves`, `n_moves_from`, `n_moves_to` all keep their current semantics.
- [ ] AC-4: When neither moveFrom nor moveTo is present, `move_from_ids` and `move_to_ids` are both `[]` (not omitted, not None) — so callers can rely on shape stability.
- [ ] AC-5: Tests: 3 new — (a) capture moveFrom IDs only; (b) capture moveTo IDs only; (c) malformed mark without `w:id` is skipped without crashing.
- [ ] AC-6: All 14 existing `tests/test_docx_revisions.py` tests still pass — the addition is non-breaking.

**Out of scope**:
- Cross-block correlation logic itself (compute the pairing). That belongs in a downstream consumer (audit ledger, UI overlay) — this loop just preserves the data.
- Wiring `move_from_ids` / `move_to_ids` into the wire format (`SegmentRevisions` interface). Defer until a consumer asks. Avoid speculative API surface.
- DOCX export round-tripping the IDs (TMX-3701 export is in-flight; pairing through round-trip is its concern).

## 3. Design

The current iter() pass in `_collect_revisions` already visits every revision mark — adding ID capture is a single line addition per branch:

```python
W_ID_ATTR = f"{{{W}}}id"  # already implicit; add to docx_utils

# in the loop:
if tag == MOVE_FROM_NS:
    n_move_from += 1
    move_id = descendant.get(W_ID_ATTR)
    if move_id and move_id not in seen_move_from_ids:
        move_from_ids.append(move_id)
        seen_move_from_ids.add(move_id)
elif tag == MOVE_TO_NS:
    # symmetric for moveTo
```

Why dedup by ID: a single move event can manifest as multiple sibling `<w:moveTo>` marks within the same paragraph (Word splits across runs). Same `w:id` appearing twice should be one entry, not two — matching the dedup semantics already used for authors and dates.

**Why list[str] not list[int]**: OOXML `w:id` is technically `xs:integer` in the schema, but treating it as opaque string is safer (forward-compat with future extensions, no surprise on weirdly-formatted docs). Consumers can `int(x)` if they need it.

## 4. Code

| File | Change |
|---|---|
| `app/services/docx_utils.py` | Add `W_ID_ATTR = f"{{{W}}}id"` constant alongside AUTHOR_ATTR/DATE_ATTR. |
| `app/services/docx_ingestion.py` | `_collect_revisions`: capture `move_from_ids` + `move_to_ids` lists; emit in dict; update docstring. |
| `tests/test_docx_revisions.py` | 3 new tests for the ID capture (positive moveFrom, positive moveTo, malformed-no-id). |

## 5. Eval / Test

```
$ pytest tests/test_docx_revisions.py -v
```

Expected: 17 passed (was 14, +3).

## 6. Red team

- **Same w:id present in both moveFrom and moveTo within a single element** (malformed doc): both lists capture independently — `move_from_ids = ["3"]`, `move_to_ids = ["3"]`. A consumer interpreting that as "intra-block move" handles it sensibly. Safe.
- **Empty-string w:id**: `descendant.get(W_ID_ATTR)` returns `""` which is falsy → `if move_id and ...` skips it. Treated as missing, same as the no-attr case. Safe.
- **Back-compat**: existing 11 keys preserved unchanged. Two new keys added. Existing 12 tests still pass.
- **Performance**: same single O(n) iter() pass — added two set lookups + two list appends per move mark. Negligible.
- **Frontend impact**: `SegmentRevisions` interface untouched in this loop (deferred per spec). FE consumers see no change. ✓ A1.

CLEAN — no findings.

## 7. Fix

No findings — clean.

## 8. Deploy

- [x] G1 anti-bloat: PASSED (additive to existing helper, no new files in product code).
- [x] G2 reproduce-failure: PASSED — 3 tests RED with KeyError before fix; GREEN after.
- [x] G3 completion: PASSED — pairing IDs visible in revisions dict; consumer can intersect `move_from_ids` (block A) with `move_to_ids` (block B) to pair across blocks.
- [x] Backend pytest: 15/15 in `tests/test_docx_revisions.py` (was 12, +3). Wider tests/ run: 753 passed (the 2 unrelated TMX-3012c tenant-injection failures are pre-existing — confirmed by stash-and-rerun on clean main).
- [x] Lint / typecheck: ruff clean on changed files.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T23:58Z | — | `[Spec]` | Loop opened — TMX-3704-pairing |
| 2026-05-10T00:15Z | `[Spec]` | `[Code]` | RED tests written; 3 KeyError failures confirmed before fix |
| 2026-05-10T00:18Z | `[Code]` | `[Test]` | Fix applied; 15/15 GREEN |
| 2026-05-10T00:25Z | `[Test]` | `[Done]` | Red-team clean; ready to commit |
