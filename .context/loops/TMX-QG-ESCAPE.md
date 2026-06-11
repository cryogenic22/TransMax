# TMX-QG-ESCAPE — Fix invalid-escape SyntaxWarning in quality_gate.py

**State**: `[Done]` — `7602de8` on origin/main
**Owner**: Quality & Regulatory
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — one docstring made raw.
**Pre-mortem**: none material — a docstring-only change; behaviour identical.
**Blast radius**: `app/services/quality_gate.py` (`check_complexity` docstring → raw string).

**Gates**: G1 ✅ (stability — a Python 3.12+ SyntaxWarning that becomes a SyntaxError in future versions; fixing it keeps the module importable). G2 ✅ — the warning reproduces under `py_compile … doraise` + `-W error::SyntaxWarning`. G3 ✅ — module compiles with no SyntaxWarning.

## Spec
- AC-1: `app/services/quality_gate.py` compiles with `warnings.simplefilter("error", SyntaxWarning)` (no invalid-escape `\[`).

## Test
`tests/test_engine_hardening.py::test_quality_gate_compiles_without_syntax_warning`.

## Deploy
- [x] Commit: `7602de8` (bundled under the TMX-3211 commit subject)
- [x] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done — pending SHA record]` | docstring → raw; warning cleared |
