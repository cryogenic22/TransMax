# TMX-TM-2 — Surface translation-memory reuse in the quality report

**State**: `[Verify]`  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  Batch-3 loop 7/10 (2026-06-04)
**Reversibility**: `two-way`. **Blast radius**: `app/agents/nodes/translation_engine.py` (`_build_quality_report`).

## 1. Task
You asked to "store/reuse translations as components and not go through LLMs where not needed" and felt the feature existed. It does — the engine's `_separate_tm_matches` already bypasses the LLM for exact-match (TM) segments — but the reuse was invisible. Surface it: the report now lists which segments were served from TM. Addenda: trust/observability.

## 2. Spec
- [x] AC-1: `quality_report.tm_reused_segments` lists segment ids whose `translation_source == TM_EXACT` (served from TM, not the LLM).
- [x] AC-2: `tm_reused_count` accompanies it.
- [x] AC-3: zero when everything was LLM-translated.

Out of scope: FUZZY/sub-segment TM matching (a similarity-threshold lookup — the bigger TMX-TM-3); populating TM from approved translations (TMX-TM-4); UI rendering of the reuse badge.

## 3. Design
`_build_quality_report` already iterates `units`; add `tm_reused_segments` = ids where `translation_source == SubstitutionType.TM_EXACT.value`, parallel to TMX-CONF-1's `needs_review_segments`. Pure read of existing per-unit state — no new lookup.

## 4. Code
| File | Change |
|---|---|
| `app/agents/nodes/translation_engine.py` | `_build_quality_report` += `tm_reused_segments` / `tm_reused_count` |
| `tests/test_tm_reuse_surface.py` | new — 2 tests (TM-served ids surfaced; none when all-LLM) |

## 5. Test
`pytest tests/test_tm_reuse_surface.py` → 2 passed. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Pure surfacing of existing state — no behaviour change to translation/TM.
- Confirms the reuse feature is live (exact-match bypass) + now observable.

## 7. Fix
Removed an unused test import. No other findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 2 tests
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-TM-3** — fuzzy/sub-segment TM matching (similarity threshold) above exact-match.
- **TMX-TM-4** — populate TM from approved translations (closing the reuse loop).

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~06:40Z | — | `[Verify]` | report surfaces tm_reused_segments; 2 tests; ratchet 17/17; awaiting full suite |