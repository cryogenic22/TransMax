# TMX-GRAPH-DEADCODE — Remove dead draft_translate path; migrate test_tm_bypass

**State**: `[Done]` — `e78b92d` on origin/main  ·  **Owner**: Agent & AI  ·  **Sprint**: 2  ·  Loop 4/10 (2026-06-04 batch)
**Reversibility**: `two-way` (revert restores the functions). **Blast radius**: `app/agents/graph.py` (−130 lines), `tests/test_tm_bypass.py` (re-pointed to the engine).

## 1. Task
`draft_translate` and its helpers (`_process_tm_matches`, `_prepare_translation_payload`, `_build_translation_prompt`) are the *old* translation node — the production workflow uses `translation_engine_node`. They were dead in production but pinned by `test_tm_bypass`. Remove the dead code and migrate the TM-bypass test to the live engine. Addenda: Tier-0 entropy (delete broken windows), engine-first.

## 2. Spec
- [x] AC-1: the 4 dead functions removed from `graph.py`; nothing in `app/` references them.
- [x] AC-2: `test_tm_bypass::test_graph_tm_bypass` verifies the bypass against the LIVE engine (`TranslationEngine._separate_tm_matches`): TM-exact segment is pre-filled + kept out of `llm_units`; non-matched routed to the LLM.
- [x] AC-3: `test_db_service_exact_match` retained unchanged.
- [x] AC-4: now-unused imports removed (`LanguagePackFactory`, `SubstitutionType` in graph.py; `TransMaxState`, `Segment` in the test); graph.py shrinks 763 → 632.

Out of scope: the 2 pre-existing graph.py E402 mid-file imports (TMX-GRAPH-E402) + the test's pre-existing E402.

## 3. Design
Remove the contiguous dead block (between `compile_constraints` and the `defect_taxonomy` import). Re-point `test_graph_tm_bypass`: keep the `compile_constraints` half (still live, populates `tm_match`), then assert the engine's `_prepare_segment_units` + `_separate_tm_matches` route the TM-exact segment to `tm_units` (pre-filled "Bonjour", absent from `llm_units`) and the unmatched one to `llm_units`. This tests the *real* production bypass mechanism rather than a retired node.

## 4. Code
| File | Change |
|---|---|
| `app/agents/graph.py` | removed `draft_translate` + 3 helpers (−130 lines); dropped now-unused `LanguagePackFactory` + `SubstitutionType` imports |
| `tests/test_tm_bypass.py` | `test_graph_tm_bypass` re-pointed to `TranslationEngine._separate_tm_matches`; dropped unused imports |

## 5. Test
`pytest tests/test_tm_bypass.py` → 2 passed (bypass now verified on the engine). Ratchet 17/17. graph.py 632 lines. Full suite — stage 8.

## 6. Red team
- Confirmed (grep) no `app/` reference to the removed functions; only the test pinned them.
- The migrated test exercises the genuine production path (`_separate_tm_matches`), so coverage of "TM-exact bypasses the LLM" is preserved, not lost.
- graph.py headroom restored (632) — reduces future mega_files pressure.

## 7. Fix
Removed unused imports surfaced by the deletion. No findings.

## 8. Deploy
- [x] Ruff clean (2 pre-existing E402 only) · Ratchet 17/17 · tm_bypass 2/2
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~01:00Z | — | `[Verify]` | −130 dead lines; test migrated to engine; ratchet 17/17; awaiting full suite |