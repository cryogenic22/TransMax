# TMX-LANG-EU2 — deep language packs: Polish, Greek, Czech, Hungarian

**State**: `[Done]` — pending commit
**Owner**: Document Pipeline / Quality & Regulatory
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — new pack files + registry entries; revert restores GenericLanguagePack fallback.
**Pre-mortem**: as TMX-LANG-EU1.
**Blast radius**: 4 new files under `app/services/language_packs/`, `factory.py` registry (also removed duplicate Tier-2 nl/pl/el entries that would have shadowed the new Tier-1 packs in the dict literal).

**Gates**: G1 ✅ functional depth (EMA official languages). G2 N/A. G3 ✅.

## Spec / Test
Same rubric + test file as TMX-LANG-EU1 (`tests/test_lang_packs_eu.py`). pl/el/cs/hu resolve to dedicated packs; negation + numeric gates verified.

## Deploy
- [ ] Commit: <sha>
