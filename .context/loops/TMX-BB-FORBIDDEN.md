# TMX-BB-FORBIDDEN — forbidden glossary terms enforced (clean-up + regression lock)

**State**: `[Done]` — pending commit
**Owner**: Quality & Regulatory
**Sprint**: 2 (next-10 batch)
**Reversibility**: `two-way` — removed dead think-aloud comments; behavior unchanged; added tests.
**Pre-mortem**: a regression silently stops forbidding deprecated terms → two regression tests pin the gate firing + the constraint mapping.
**Blast radius**: `app/services/db_service.py` (forbidden-term constraint block), `tests/test_forbidden_glossary_enforcement.py` (new).

**Gates**: G1 ✅ robustness/stability — the enforcement already shipped (TMX-TERMLOCK-WB); this loop is entropy reduction (broken-window: 11 lines of confused dead comments + a dead `t_dict["term"]` assignment) + a missing regression guard, NOT new behavior. G2 ✅ — the gate-fires path is reproduced in test. G3 ✅.

## Spec
- AC-1: `GlossaryTerm.is_forbidden=True` → `get_constraints()['forbidden_terms']` carries the forbidden target string.
- AC-2: the gate fires a defect when the forbidden term appears in the translation; silent when absent.
- AC-3: the confused dead-code block in `get_constraints` is removed (Tier-0 entropy).

## Test
`tests/test_forbidden_glossary_enforcement.py` — 3 passed (gate fires / gate silent / constraint mapping).

## Deploy
- [ ] Commit: <sha>
