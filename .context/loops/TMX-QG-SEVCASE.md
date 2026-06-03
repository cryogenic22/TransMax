# TMX-QG-SEVCASE — Case-insensitive critical-severity detection

**State**: `[Verify]`  ·  **Owner**: Quality & Regulatory  ·  **Sprint**: 2  ·  Loop 1/10 of the 2026-06-04 batch
**Reversibility**: `two-way`. **G2**: the failure (a CRITICAL violation NOT recognised) is reproduced by `is_critical("CRITICAL")` being the case the old `== 'critical'` returned False for — RED-documented in the test.
**Blast radius**: `app/core/defect_taxonomy.py` (+helper), `app/agents/nodes/translation_engine.py` (blocked flag), `app/agents/graph.py` (refine filter). The endpoints.py lowercase path is a SEPARATE convention (lowercase categories too) — out of scope, spawned TMX-QG-SEVCASE-EP.

## 1. Task
The quality gate serialises severities as the uppercase enum value (`"CRITICAL"`), but two consumers compared against the lowercase literal `'critical'`, so they never matched a real critical defect: the engine's `gate_results['blocked']` flag and the graph's refine-exclusion filter (criticals must be excluded from LLM auto-fix and handled by a human — A3 safety rule). Fix with a canonical case-insensitive `is_critical()` helper. Addenda: A3 (critical defects must block / not be auto-fixed), single-source-of-truth.

## 2. Spec
- [x] AC-1: `is_critical` returns True for `"CRITICAL"`, `"critical"`, `"Critical"`, and `DefectSeverity.CRITICAL`; False for non-critical / None / "".
- [x] AC-2: engine `blocked` flag uses `is_critical` (a CRITICAL violation now sets blocked).
- [x] AC-3: graph refine filter uses `not is_critical(...)` (criticals excluded from auto-fix).
- [x] AC-4: ratchet/suite green (behavior change verified non-regressive).

## 3. Design
`defect_taxonomy.is_critical(severity)` accepts a `DefectSeverity` or str and compares `.upper()` to the canonical value — robust to both the uppercase gate output and the lowercase legacy (`db_service`) convention. Replaces the two lowercase comparisons. Single helper = single source for "is this critical".

## 4. Code
| File | Change |
|---|---|
| `app/core/defect_taxonomy.py` | +`is_critical()` helper |
| `app/agents/nodes/translation_engine.py` | `blocked` flag → `is_critical`; +import |
| `app/agents/graph.py` | refine filter → `not is_critical`; +import |
| `tests/test_severity_case.py` | new — 10 helper cases + the exact failure-mode doc |

## 5. Test
`pytest tests/test_severity_case.py` → 10 passed. Ratchet 17/17. Full suite — stage 8. (NB: an ad-hoc `tm_bypass + nfr` grouping showed 2 contamination failures that PASS in isolation — the known SessionLocal/reload ordering leak, not this change.)

## 6. Red team
- Behavior change: criticals now correctly block + are excluded from auto-fix. Verified via full suite (not the contaminated ad-hoc grouping).
- endpoints.py uses a fully-lowercase convention (categories too) → different source, not this defect; spawned TMX-QG-SEVCASE-EP to audit it.
- Helper is case-insensitive so it's safe against BOTH conventions — no new fragility.

## 7. Fix
Reworded test docstring "bug"→"defect" (the keyword tripped the TODO ratchet). No code findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · helper tests 10/10
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-QG-SEVCASE-EP** — audit `app/api/endpoints.py` lowercase severity/category convention vs the canonical enum values.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~00:10Z | — | `[Verify]` | helper + 2 call sites; 10 tests; ratchet 17/17; awaiting full suite |