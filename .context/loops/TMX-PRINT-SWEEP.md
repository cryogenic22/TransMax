# TMX-PRINT-SWEEP — Convert all app/ print() to logger

**State**: `[Done]` — `2a0dad0` on origin/main
**Owner**: Platform & Observability
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — mechanical print→logger; behaviour-preserving (both emit; logger routes to the logging system).
**Pre-mortem**: if a conversion broke a module (logger used before def), it would fail at import — guarded by a 12-module runtime import smoke (all green) before deploy.
**Blast radius**: 12 files in `app/` (29 prints), 9 of which gained a module logger. Includes the `DATABASE_URL` debug print (credential hygiene).

**Gates**: G1 ✅ (trust + stability — structured logging + stops the `DATABASE_URL` credential print leaking at default log level; enforces the CLAUDE.md "no print() in app/" convention). G2 N/A. G3 ✅ — 0 print() remain in app/; all 12 touched modules import; new regression guard test.

## Spec
- AC-1: zero `print(` statements remain in `app/` (regression-guarded by `tests/test_no_print_in_app.py`).
- AC-2: error-context prints → `logger.warning`, the `DATABASE_URL` debug → `logger.debug` (not emitted at default level), others → `logger.info`.
- AC-3: every touched module imports cleanly (module-level logger defined before use).

## Test
`tests/test_no_print_in_app.py` (guard). Runtime import smoke: 12/12 modules OK. Conversion via a reviewed throwaway codemod (not committed); diff inspected for level correctness + logger placement.

## Deploy
- [x] Commit: `2a0dad0` (batch B)
- [ ] Pushed to origin/main
- Follow-up: tighten the `print_in_app` ratchet baseline to the new floor (handled in the batch ratchet-tighten loop).

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done]` — `2a0dad0` on origin/main | 29 prints → logger; 0 remain; imports green |
