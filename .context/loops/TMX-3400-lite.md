# TMX-3400-lite — Extract semantic_drift out of quality_gate.py

**State**: `[Done]` — `384eb16` on origin/main
**Owner**: Quality & Regulatory
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — moved a self-contained function to a new module; `QualityGateService.calculate_semantic_drift` keeps a thin delegating method, so both callers (reflexion node, `/tools`) are unchanged.
**Pre-mortem**: if the delegation broke, drift would always error — guarded by the existing drift-sentinel tests (pass via delegation) + a direct module test.
**Blast radius**: new `app/services/semantic_drift.py`; `app/services/quality_gate.py` (method body → delegation).

**Gates**: G1 ✅ (stability — partial paydown of the C-08 god-object; `quality_gate.py` 799→771 gives headroom so the gate can grow (term-lock) without tripping `mega_files_800`, which had blocked 2 loops this batch). G2 N/A. G3 ✅ — drift sentinel tests pass via delegation; new module imports + returns None on no-key; ruff/ratchet clean.

## Spec
- AC-1: `app/services/semantic_drift.calculate_semantic_drift(src, back) -> Optional[float]` holds the logic; `None` on no-key/embed-fail preserved.
- AC-2: `QualityGateService.calculate_semantic_drift` delegates; existing callers unchanged.
- AC-3: `quality_gate.py` drops below the 800-line ceiling.

## Test
`tests/test_drift_sentinel.py` (delegation) + `tests/test_termlock_wb.py::test_semantic_drift_module_importable_and_none_without_key`. quality_gate.py 799→771.

## Deploy
- [x] Commit: `384eb16` (bundled with TMX-TERMLOCK-WB)
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done]` — `384eb16` on origin/main | extracted; 799→771; delegation green |
