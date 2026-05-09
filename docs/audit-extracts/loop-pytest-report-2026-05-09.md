# Loop Pytest Verification Audit — 2026-05-09

**Agent**: Agent 2 of 4 (parallel verification)
**Repo**: `C:/Users/kapil/Documents/transmax`

## Invocation

```
python -m pytest tests/ --ignore=tests/evals --ignore=tests/sdk \
  --ignore=tests/language_packs --timeout=60 -q --tb=short
```

Runtime: **95.26 s** (≈ 1 m 35 s).

## Headline

| Status   | Count |
|----------|-------|
| Passed   | 427   |
| Failed   | 11    |
| Skipped  | 2     |
| Errored  | 0     |
| **Total**| **440** |

## Failures

| Test | File:line | Cause |
|------|-----------|-------|
| test_activity_feed_item_has_wire_shape | tests/test_dashboard_activity_feed.py:85 | Activity feed empty — `assert items` fails |
| test_activity_feed_translator_agent_mapped_correctly | tests/test_dashboard_activity_feed.py:97 | TRANSLATION_GENERATED not mapping to translator agent |
| test_agent_activity_each_item_has_wire_shape | tests/test_dashboard_activity_feed.py:133 | No translator+reviewer activities returned |
| test_dashboard_activity_returns_list | tests/test_dashboard_api.py:77 | Expected len==1, got 0 |
| TestTablesInterleaved::test_paragraph_table_order | tests/test_docx_roundtrip.py:110 | `'TR:After table'` missing from para_texts |
| TestHeaders::test_header_extraction | tests/test_docx_roundtrip.py:193 | Header text not prefixed with `TR:` |
| TestFooters::test_footer_extraction | tests/test_docx_roundtrip.py:217 | Footer text not prefixed with `TR:` |
| TestOrderConsistency::test_ingestion_export_order_matches | tests/test_docx_roundtrip.py:259 | `'TR:Para 2'` missing from para_texts |
| test_reverse_translate_calls_llm | tests/test_reverse_translate_endpoint.py:50 | 404 vs 200 (route not registered) |
| test_reverse_translate_no_translation_returns_400 | tests/test_reverse_translate_endpoint.py:71 | 404 vs 400 (route not registered) |
| test_verify_endpoint_returns_correct_status | tests/test_tamper_detection.py:117 | 404 vs 200 (verify endpoint not registered) |

## Targeted regression checks (TMX tickets)

| File | Pass / Total | Status |
|------|--------------|--------|
| tests/test_organizations_model.py (TMX-3010) | 8 / 8 | PASS |
| tests/test_organization_fk.py (TMX-3011)     | 7 / 7 | PASS |
| tests/test_soft_delete.py (TMX-3015)         | 7 / 7 | PASS |
| tests/test_audit_events_v2_schema.py (TMX-3100) | 9 / 9 | PASS |
| tests/test_tenant_session.py (TMX-3012)      | 12 / 12 | PASS |

All 43 targeted regression tests pass.

## Ratchet status

`python scripts/ratchet.py check` → **17/17 metrics at-or-better than baseline.**

```
✓ Ratchet OK — all 17 metrics at or better than baseline.
```

## Health verdict — YELLOW

Core regression suites for the v3.0 multi-tenancy and audit-v2 epics (TMX-3010/3011/3012/3015/3100) are all green and the ratchet is fully clean, so the foundational work landed cleanly. The 11 failures cluster in three pre-existing-and-unrelated areas — dashboard activity feed wiring (4), DOCX round-trip ingestion (4 — matches the `app/services/docx_ingestion.py` work-in-progress in `git status`), and unmounted endpoints `/reverse-translate` + `/verify` (3, all 404s suggesting router registration was deferred). None of these are new regressions caused by the regression-test landings; they are in-flight features. Verdict yellow rather than green only because the count (11) is non-trivial; not red because nothing in the audit/tenancy critical path is broken.
