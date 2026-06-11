# TMX-LANG-EU1 — deep language packs: Dutch, Swedish, Danish, Finnish

**State**: `[Done]` — pending commit
**Owner**: Document Pipeline / Quality & Regulatory
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — new pack files + registry entries; revert restores GenericLanguagePack fallback.
**Pre-mortem**: a wrong negation marker under/over-detects → both-direction tests (fires when target drops negation, silent when marker present).
**Blast radius**: 4 new files under `app/services/language_packs/`, `factory.py` registry.

**Gates**: G1 ✅ functional depth — EMA QRD package leaflets require these official EU languages; deep packs give real negation + decimal-comma numeric gates instead of universal-only. G2 N/A. G3 ✅ — factory resolves dedicated packs; gates fire correctly.

## Spec
- AC-1: factory resolves nl/sv/da/fi to dedicated packs (not Generic).
- AC-2: negation gate fires on dropped target negation; silent when correct marker present.
- AC-3: numeric gate catches a dropped dose; accepts decimal-comma swap (5.5 ↔ 5,5).

## Test
`tests/test_lang_packs_eu.py` (shared with EU2) — 5 tests across all 8 packs.

## Deploy
- [ ] Commit: <sha>
