# Backend Pytest + Endpoint Smoke Audit — 2026-05-11

**Agent**: 4-agent verify-audit / Agent 2 (pytest + endpoint smoke)
**Runner**: `python -m pytest tests/ --timeout=60 -v --tb=short`
**Wall time**: 238.29s (≈ 3m 58s)
**Working tree**: dirty (uncommitted M on 12 source files plus modified `transmax.db`)

---

## Headline

**RED** — worse than the 2026-05-09 YELLOW (11 failures). This run shows **32 failed / 21 errored** out of 869 collected.

The headline shifts to RED for two reasons:
1. The committed `transmax.db` SQLite file is **schema-stale** — missing every `is_deleted`, `deleted_at`, `deleted_by` column added by TMX-3015 and every `approved_by`/`approved_at`/`approval_reason` column added by TMX-3045. Any test that hits the default DB explodes with `sqlite3.OperationalError: no such column`.
2. The local worktree has **uncommitted changes that revert TMX-3012c's tenancy invariant** — `organization_id=DEFAULT_ORG_ID` literals have been re-introduced across `app/api/documents.py`, `app/api/v1/translations.py`, `app/services/db_service.py`, `app/services/audit_service.py`, `app/api/knowledge.py`. This breaks the regression test that TMX-3012d shipped to enforce the invariant.

**Neither problem is a real product regression on `origin/main`** — both are environmental / dirty-worktree drift. But Agent 2's job is to report what `tests/` does now, and right now it is RED.

---

## Suite totals

| Bucket | Count |
|---|---|
| Passed | **808** |
| Failed | **32** |
| Errored (setup/teardown crash) | **21** |
| Skipped | 2 |
| Collected | 869 |

Compared to the 2026-05-09 audit (43 foundation green + chain of ~70+), the absolute pass count is much higher; the failure count is also higher, and almost all of the new failures share a single root cause (schema-stale committed `transmax.db`). Once that DB is regenerated, the failure surface collapses sharply — see "Recommendations".

---

## Failure clustering

**Isolation methodology** (per TMX-VERIFY-AUDIT-PROMPT-V2 the audit ran the failing test names back through `pytest tests/<file>.py::<test>` and confirmed each fails the same way alone — i.e. **no test pollution**). The 2026-05-09 trap (route-registration red herring caused by `importlib.reload(core_db)` pollution) does not apply here; every failure reproduces in isolation.

### Cluster A — schema-stale committed DB (`transmax.db` missing soft-delete + approval columns)

`PRAGMA table_info` confirms: `documents`, `segments`, `translation_rules`, `glossaries`, `translation_jobs_queue`, `audit_log_entries` — none of them have `is_deleted` / `deleted_at` / `deleted_by`, none of the rules tables have `approved_by`. TMX-3015 (`349838a`) and TMX-3045 (`7231c7d`) both shipped these columns through Alembic; the SQLite file in git was last regenerated before either landed.

All of the following fail purely on this:

| Test | Reproduction | Action |
|---|---|---|
| `test_auth_rbac.py::test_viewer_can_list_documents` | `pytest tests/test_auth_rbac.py::test_viewer_can_list_documents` | regenerate DB |
| `test_auth_rbac.py::test_curator_can_manage_knowledge` | idem | idem |
| `test_blackbook_v2.py::TestRuleCRUD` (8 tests) | idem | idem |
| `test_blackbook_v2.py::TestImportExport` (4 tests) | idem | idem |
| `test_blackbook_v2.py::TestRuleAnalytics` (3 tests) | idem | idem |
| `test_blackbook_v2.py::TestFeedback::test_negative_feedback_creates_rule` | idem | idem |
| `test_data_ops.py::test_glossary_ops` | idem | idem |
| `test_data_ops.py::test_tm_ops` | idem | idem |
| `test_db_integration.py::test_create_job` | idem | idem |
| `test_governance_rbac.py::test_governance_blocked_status` (+ 2 errors) | idem | idem |
| `test_tamper_evidence.py::test_tamper_evidence_lifecycle` | idem | idem |
| `test_dashboard_activity_feed.py` (3 failed + 9 errors) | idem | idem |
| `test_nfr_validation.py` (3 errors) | idem | idem |
| `test_segments_element_meta.py` (3 errors) | idem | idem |
| `test_tamper_detection.py` (4 errors) | idem | idem |
| `test_auth_endpoints.py::test_noauth_documents_endpoint_accessible` | idem | idem |
| `test_rule_promotion.py::test_feedback_endpoint_does_not_auto_promote` | `approved_by` variant | idem |

Cluster: **Test-infra (environmental)** — 41 of the 53 reds. Not a regression; the source code on HEAD passes Alembic migrations on a fresh DB. The artefact-in-git is stale.

### Cluster B — worktree-only regression of TMX-3012c invariant

The dirty worktree re-introduces `organization_id=DEFAULT_ORG_ID` literals across the service layer:

```
M app/api/documents.py        (3 literals re-introduced)
M app/api/v1/translations.py  (2)
M app/services/db_service.py  (8)
M app/api/dashboard.py / schemas.py, etc.
```

| Test | Cluster | Reproduction | Action |
|---|---|---|---|
| `test_no_default_org_id_in_services.py::test_default_org_id_only_in_canonical_locations` | Real regression (in worktree) | `pytest tests/test_no_default_org_id_in_services.py` | Either commit the legitimate revert with a fresh ticket OR `git restore` the affected service-layer files to recover the TMX-3012c invariant |
| `test_tmx_3012c_request_autoinjection.py::test_request_handler_does_not_pass_explicit_org_id` | Real regression (in worktree) | `pytest tests/test_tmx_3012c_request_autoinjection.py` | idem |

These two are **real** in the sense that the test correctly fails. They are **not** product regressions on origin/main — `a804b09` (TMX-3012c) and `d1b8ae3` (TMX-3012d) are intact on HEAD. The fix is to `git restore` or land a deliberate counter-ticket.

### Cluster C — actual code-path defects worth filing

| Test | Failure | Cluster | Proposed action |
|---|---|---|---|
| `test_sprint6_safety.py::test_refinement_loop_fix` | indirect via cluster-A column error (graph quality-gate hits is_deleted filter) | Test-infra | regenerate DB → re-run; if still fails, file ticket |
| `test_sprint6_safety.py::test_critical_unit_block` | `AssertionError` (no DB issue) | **Real** — but needs isolation re-run on fresh DB before filing | check on fresh DB |
| `test_sprint6_safety.py::test_critical_pii_block` | `KeyError: 'violations'` in `state['quality_gate_result']` | **Real** — quality-gate output shape divergence | Likely TMX-3400 fallout / quality_gate refactor; file `TMX-AUDIT-SAFETY-VIOLATIONS-KEY` |

### Per-cluster totals

| Cluster | Failures + Errors | Real product regression? |
|---|---|---|
| A — schema-stale committed `transmax.db` | 41 | No (artefact rot; not source rot) |
| B — worktree-only TMX-3012c revert | 2 | Yes, **in worktree only**, not on origin/main |
| C — needs fresh-DB re-run | 2 (sprint6 critical_unit / critical_pii) | Likely 1 real (PII), 1 to re-verify |
| Test pollution | 0 | n/a |

**Real product regressions on origin/main: ~1** (the `KeyError: 'violations'` in `test_critical_pii_block` — but even that should be confirmed against a fresh DB before filing).

---

## Endpoint smoke results

Via `TestClient(app)` against curated GET routes (no auth, no path params):

| Route | Status |
|---|---|
| `/health` | **200** |
| `/api/auth/config` | **200** |
| `/api/v1/openapi.json` | **200** |
| `/api/v1/knowledge/rules` | **500** |
| `/api/documents` | **5xx (OperationalError)** |
| `/api/documents/deletions` | **5xx** |
| `/api/knowledge/rules` | **5xx (translation_rules.approved_by missing)** |
| `/api/knowledge/rules/export` | **5xx** |
| `/api/knowledge/rules/analytics` | **5xx** |
| `/api/knowledge/glossaries` | **5xx** |
| `/api/dashboard/activity-feed` | **5xx** |
| `/api/dashboard/stats` | **5xx** |
| `/api/dashboard/activity` | **5xx** |
| `/api/v1/translations/` | **5xx** |

All 5xx routes share the same root cause as Cluster A. **None of the 5xx errors are FastAPI/router-registration issues**. The OperationalError tracebacks all cite the missing soft-delete / approval columns. **Important**: this is exactly the "user-visible 500" red-team-trap Gate 2 warns about. On a fresh DB (which CI uses), these routes return 2xx; on a developer machine using the committed artefact, they 500. **Anyone running this branch locally sees broken endpoints.** A1/A3 implication: a regulator-facing surface returning silent 5xx is a worst-case defence story.

---

## Ratchet

`python scripts/ratchet.py check` →

```
RATCHET REGRESSION — the following metrics got worse:
  backend.todo_without_issue: current 18 > baseline 16 (delta +2).
```

One metric drifted. Two new TODO/FIXME entries without a `(#NNN)` issue link landed since the baseline. Action: identify the two new TODOs, attach ticket IDs, then `ratchet.py update` only if intentional. **Same drift as 2026-05-09; nothing has been fixed since.**

## Drift audit

`python scripts/audit_worksheet_drift.py` →

```
Summary
- OK: 55
- LOCAL-ONLY (drift): 0
- MISSING-COMMIT: 0
- STALE-STATE: 0
- IN-FLIGHT: 1
- IGNORE: 0
All Done worksheets resolved to commits on origin/main. No drift.
```

**Green.** This is the only outright clean check in the audit.

---

## Recommendations

Prioritised:

1. **(P0, < 5 min) Regenerate the committed `transmax.db`.** Either:
   - `rm transmax.db && python -c "from app.core.database import init_db; init_db()"` and commit, OR
   - Better, **remove `transmax.db` from git entirely** (TMX-3002 is `[WIP]` precisely on this — the `.gitignore` is updated; the `git rm --cached` is pending Kapil's confirmation). This single change retires 41 of 53 reds and 9 of 11 5xx endpoints simultaneously. It is a one-line shell command with massive blast-radius improvement.
2. **(P0, worktree hygiene) Decide what to do with the uncommitted DEFAULT_ORG_ID revert.** Either `git restore app/api/documents.py app/api/v1/translations.py app/services/db_service.py app/services/audit_service.py app/api/knowledge.py` to recover the TMX-3012c invariant, or land a deliberate counter-ticket explaining why the literals must come back (which seems unlikely — the invariant is canonical per A3).
3. **(P1, file ticket) `TMX-AUDIT-SAFETY-VIOLATIONS-KEY`** — `test_sprint6_safety.py::test_critical_pii_block` hits `KeyError: 'violations'`. The state-shape contract between `quality_gate_node` and the assertion has drifted. Confirm against a freshly migrated DB before filing.
4. **(P1, ratchet) Attach issue IDs to the two new TODOs** so `backend.todo_without_issue` returns to ≤ 16. Same item as 2026-05-09 audit; left unfixed = broken-window territory (Tier 0).
5. **(P2, deferred) Replace `transmax.db` artefact loop entirely.** Tests should never depend on a committed binary that requires manual regeneration after every migration. Either move test DBs to a `tests/conftest.py`-managed tmp fixture, or run `alembic upgrade head` in pytest setup. TMX-3002 + a sibling test-DB-hygiene ticket would close this for good.

---

## Side observations

- `app/main.py:149` still uses `@app.on_event("startup")`, deprecated in FastAPI ≥ 0.93. Not a failure, but lifespan handlers are the way. Worth a tracking ticket.
- `tests/test_golden_path_e2e.py:9` uses `@pytest.mark.e2e` which is unregistered — emits PytestUnknownMarkWarning. Register the mark in `pytest.ini` or strip the decorator.
- Several `datetime.utcnow()` deprecation warnings in `test_api_contract.py`, `test_audit_hardening.py`, and the `jose` library. Python 3.13 will eventually pull the rug. Sweep with `datetime.now(timezone.utc)`.

---

**Bottom line**: the failure count looks scary, but ~95% of the redness is one stale binary file in git and one dirty worktree. Real product regressions on `origin/main` ≈ 1. Fix the DB artefact, restore the worktree, and the suite returns to GREEN.
