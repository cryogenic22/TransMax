# TMX-BB-STRICT — enforce is_strict (locked) Black-Book rules

**State**: `[Done, pending push]` · **Owner**: Quality & Regulatory · **Sprint**: Phase 0 (honesty)
**Reversibility**: `two-way`. **Pre-mortem**: a strict rule now BLOCKS where it was silently ignored — intended, but it changes verdicts for tenants with strict rules (only those they explicitly marked strict). **Blast radius**: `db_service.get_constraints` (carry flag), `quality_gate` (`_create_defect` severity override + glossary loop).

**Gates**: G1 ✓ (closes a real vacuous-green trap; reuses `_create_defect`; ships tests) · **G2 ✓ reproduce-the-failure** — the audit found `is_strict` editable but dropped at `db_service.py:137-143` and never enforced; the new tests assert a strict violation is CRITICAL (red before fix) · G3 ✓ (a "block if violated" rule now blocks).

## 1–3. Task / Spec / Design
The audit (A4) found `is_strict` ("Strict mode: block if violated", `models.py:38`) was dropped at constraint assembly and never read by the gate — a curator's strict rule did nothing. Fix end-to-end: carry `is_strict` through `get_constraints`; the gate escalates a violated strict rule to CRITICAL (blocks) instead of MAJOR. AC-1 strict violation → CRITICAL; AC-2 non-strict → MAJOR (unchanged). Out of scope: the full enforcement-level ladder (suggested/preferred/required/locked) — Phase 3.

## 4. Code
`app/services/db_service.py` (`is_strict` in the active-rules constraint dict); `app/services/quality_gate.py` (`_create_defect(..., severity=)` optional override; glossary loop branches strict→CRITICAL).

## 5. Test
`pytest tests/test_bb_strict.py -q` → strict→CRITICAL, non-strict→not-CRITICAL. 53-test quality regression green.

## 6–7. Red team / Fix
Risk: verdict change surprises a tenant — only fires on rules explicitly marked strict; documented. Risk: false-fire from substring match — uses the existing glossary match (`src in source_text and tgt not in target_text`). No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | is_strict enforced end-to-end |
