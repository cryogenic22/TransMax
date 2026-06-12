# Loop Backend Pytest Report — 2026-06-12

Agent 2 of the 4-agent verification audit. Observation only.

## Invocation

```
python -m pytest tests/ -q --tb=short
```

Total runtime: **380.46s (6:20)**.

## Headline

**1160 passed / 0 failed / 2 skipped / 0 errored** (4 warnings).

- The 2 skips are intentional (e.g. `@pytest.mark.e2e` golden-path, and one conditional skip).
- No collection errors. No schema-staleness failures — tests correctly used the
  `tests/conftest.py::fresh_engine_for_db` fixture; the stale committed `transmax.db`
  did not interfere.
- Warnings are non-fatal: an unregistered `e2e` mark and three `datetime.utcnow()`
  deprecation notices (jose + two test files). No action taken (observation only).

## Failures

| Test | File:line | Cause |
|---|---|---|
| _(none)_ | — | — |

## Recently-added regression tests

Run individually: `18 passed in 25.27s`.

| File | Status | Notes |
|---|---|---|
| `tests/test_review_service_pending.py` | PASS | New file (+141), TMX review-service pending coverage |
| `tests/test_tools_confidence_honesty.py` | PASS | New file (+108), TMX-TOOLS-CONF-HONEST — no fabricated trust signals |
| `tests/test_audit_verify_endpoint.py` | PASS | +142 / +5 new cases (status headline x3, org-wide audit verify — TMX-3105a/TMX-VERIFY-ORG) |

All three confirmed green both in the full run and in isolation.

## Ratchet

```
python scripts/ratchet.py check
✓ Ratchet OK — all 17 metrics at or better than baseline.
```

17/17 as expected.

## Import smoke

`python -c "import app.main"` → exit 0, no DB required at import time.

## Health verdict

**GREEN.** The full backend suite passes cleanly (1160 passed, 0 failed, 0 errored)
in 6m20s with only 2 intentional skips; all newly-added regression tests pass both
in-suite and in isolation; the ratchet holds at 17/17. The only residual noise is
benign `datetime.utcnow()` deprecation warnings and one unregistered `e2e` mark,
neither of which is a test failure. No schema-staleness drift observed.
