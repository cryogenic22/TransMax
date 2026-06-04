# TMX-CONF-1 — Per-segment confidence + needs-review surface

**State**: `[Verify]`  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  Fidelity step 3/3 (2026-06-04)
**Reversibility**: `two-way`. **Blast radius**: `app/services/review_flags.py` (new), `app/api/tools.py` (universal_translate response), `app/agents/nodes/translation_engine.py` (doc quality_report).

## 1. Task
Stop the misleading "all OK". The surface showed `recommendations: []` + a high band even with real defects, because `universal_translate` only flagged `band=="Low"` / Glossary / formulas — ignoring every other violation. Lower the bar and point users at exact issues. Addenda A3 (never imply a regulated translation is "perfect/done"), A2.

## 2. Spec
- [x] AC-1: `summarize_issues(violations, confidence, band)` → `{needs_review, issue_count, issues:[{category,severity,message,segment_id}], note}`; issues come from ALL violations + a LOW_CONFIDENCE flag below threshold.
- [x] AC-2: a clean translation (no violations, high confidence) is NOT flagged but carries a note that human sign-off is still required (never "perfect").
- [x] AC-3: low confidence (<85) is flagged even with zero violations.
- [x] AC-4: `universal_translate` returns `needs_review` + structured `issues` + `review_note` (and `recommendations` derived from issues, for back-compat).
- [x] AC-5: the document `quality_report` gains `needs_review_segments` (ids with a violation OR low confidence) + `needs_review_count`, pointing reviewers at exact segments.

Out of scope: persisting per-segment confidence to a new column (the engine already stores it on the unit/scorecard); the reviewer-frontend rendering of the list (UI follow-up).

## 3. Design
New `review_flags.py`: `summarize_issues` (text/single-segment surface) + `needs_review_segment_ids(units)` (document surface). `universal_translate` builds issues from the real `violations` (not just band/Glossary). The engine's `_build_quality_report` adds `needs_review_segments`. The "clean" case still returns a GxP sign-off note so nothing reads as done.

## 4. Code
| File | Change |
|---|---|
| `app/services/review_flags.py` | new — `summarize_issues`, `needs_review_segment_ids`, `LOW_CONFIDENCE_THRESHOLD` |
| `app/api/tools.py` | `universal_translate` surfaces `needs_review`/`issues`/`review_note` from all violations + confidence |
| `app/agents/nodes/translation_engine.py` | `quality_report` += `needs_review_segments` / `needs_review_count` |
| `tests/test_review_flags.py` | new — 5 tests (clean-still-signoff, violations→issues, low-conf flagged, threshold, segment-id flagging) |

## 5. Test
`pytest tests/test_review_flags.py` → 5 passed. Ratchet 17/17. Full suite — stage 8. (Pre-existing tools.py ruff lint — unused imports + 2 baseline bare-excepts — untouched; my additions are clean; ratchet stayed green.)

## 6. Red team
- "Clean" never reads as perfect — always the GxP sign-off note (A3).
- Issues carry segment_id where present, so users jump to the exact problem.
- Threshold 0.85 is explicit + tunable; at-threshold is not flagged (boundary tested).
- Doc surface flags both violations AND low-confidence segments (the engine already scores per-segment).

## 7. Fix
None — clean. (Pre-existing tools.py lint left for a dedicated cleanup ticket.)

## 8. Deploy
- [x] Ratchet 17/17 · 5 tests · added-code ruff-clean
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-CONF-1-UI** — render `needs_review_segments` + per-segment confidence/issues in the reviewer frontend (jump-to-segment).
- **TMX-TOOLS-LINT** — clean pre-existing unused imports + bare-excepts in `app/api/tools.py`.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~03:55Z | — | `[Verify]` | summarizer + universal_translate + doc report; 5 tests; ratchet 17/17; awaiting full suite |