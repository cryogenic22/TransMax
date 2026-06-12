# Loop Quality Review — 2026-06-12 (Agent 1 of 4-agent verification audit)

**Scope:** `HEAD~25..HEAD` on `main` (commits `2d2a800`..`e06c9a2`). Observation-only.

## Overall verdict: **GREEN**

The window is a clean, surgical batch dominated by genuine A3-fabrication removals, audit-chain hardening, and additive feature work. Every behavioural change ships a regression test; the two explicitly-flagged "stop fabricating trust signals" loops are real source-code fixes that delete the fabrication path, not cosmetic. No mega-files, no forked registries, no schema drift. One minor follow-up (drift-gate threshold is a module constant, not per-tenant config — already acknowledged).

## Per-commit verdicts (substantive only; SHA-backfill / handoff / dashboard commits skipped)

| SHA | Subject | Verdict | Rationale |
|---|---|---|---|
| `4cda63e` | TMX-TOOLS-CONF-HONEST + DOCID-LOOKUP | **pass** | Deletes hardcoded `confidence=90.0/"High"` outage path (`app/api/tools.py:253-333`); `review_service.get_pending_reviews` `pass`-stub → real `get_doc_id_from_job` delegation, A4-safe (operational-layer only). +6 tests. Genuine A3 fix. |
| `f4ad0b1` | UX batch: honest QualityDashboard + DRY badges | **pass** | `QualityDashboard.tsx` fabricated accuracy/fluency/terminology bars removed; renders real penalty breakdown + `breakdownReasoning` + honest "unavailable" state. Single `<JobStatusBadge>` kills 2 dupes (one with hardcoded hex). +12 vitest. |
| `a4ec99d` | TMX-3105a + TMX-VERIFY-ORG | **pass** | Additive audit-verify endpoint + status headline; +141 test lines; new route/schema only, A1-aligned. |
| `36c5262` | TMX-PROJECTS + JOBS-FILTER | **pass** | New `Project`/`ProjectDocument` models are `TenantScopedMixin + SoftDeleteMixin` (A4/A9). Filters are additive query-param composition, no domain branching. +194 test lines. |
| `2bd6ecd` | TMX-BB-SYNTH + TMX-BB-FORBIDDEN | **pass** | Real `db_service` forbidden-term enforcement (A2 gate-side) + synthetic black book; +222 test lines. Not tests-only. |
| `942a8cf` | TMX-LANG-EU1/EU2 + TMX-3802 + LANG-EVAL | **pass** | 8 new EU language packs via `_packs` dict registry (`factory.py:get_pack`, config-not-branching). CJK segmenter + eval JSONL. Strong test discipline. |
| `384eb16` | TMX-3400-lite + TERMLOCK-WB | **pass** | Extracts `semantic_drift.py` out of `quality_gate.py` (-54/+39 → modularity win); word-boundary forbidden match; +45 tests. |
| `2a0dad0` | TMX-LIFESPAN + PRINT-SWEEP | **pass** | `print()`→`logger` sweep across `app/`; `test_no_print_in_app.py` ratchet test (regression lock). |
| `a987c3d` | TMX-DRIFT-SENTINEL | **pass** | `calculate_semantic_drift` returns `None` (not `0.0`) when unavailable — A3 no-signal honesty; +`test_drift_sentinel.py`. |
| `5f04b44` | TMX-3213 + DRIFT-GATE | **pass (minor follow-up)** | Real sha256 `output_hash` on both chain sinks (A1); back-translation drift now holds job `TRANSLATED→IN_REVIEW` (A3 fail-toward-review), 0.0 keyless-sentinel excluded. +13 tests. Follow-up: threshold is module constant. |
| `085aa94` | TMX-FEEDBACK-1/2 | **pass** | `Feedback` model TenantScoped+SoftDelete; dedicated Alembic revision (org_id FK + `is_deleted`, no mega-migration); auth-adaptive routes; +19 tests; A1 absence justified (no job_id). |
| `2d2a800` | TMX-TM-2 | **pass** | Surfaces TM-reuse in quality report (read-side surfacing). |

## Wins

- **Two real A3 fabrication kills, verified.** `TMX-TOOLS-CONF-HONEST` (`tools.py`) and `TMX-UX-QDASH-REAL` (`QualityDashboard.tsx`) both *delete* the path that rendered a fabricated green "90% / High" on a scoring outage and replace it with an explicit `scoring_available=false` / "Unavailable" state. These are source fixes with passing regression tests, not the tests-only anti-pattern Gate 2 guards against.
- **Audit chain hardened (A1).** `TMX-3213` replaced the terminal `output_hash:"placeholder_hash"` with a deterministic order-stable sha256 on legacy + v2 sinks — closes the last non-evidential link.
- **Drift gate now acts** (A3 fail-toward-review) instead of measuring-and-ignoring.
- **Modularity wins:** `semantic_drift.py` extracted from `quality_gate.py`; one canonical `JobStatusBadge` replaces 2 dupes; language packs use a registry dict.
- **Test discipline:** every behavioural commit carries a fail-without-fix regression test; ratchet held 17/17 with no baseline loosening throughout.

## Concerns

Low severity only — nothing blocks GREEN.

1. **Drift-gate threshold is a hardcoded module constant.** `REFLEXION_REVIEW_THRESHOLD = 70.0` (`app/agents/nodes/reverse_translate.py:18`) is a regulator-relevant quality gate baked into source. The commit acknowledges "one edit away from per-tenant config." For a pharma pilot, the hold/release boundary should be tenant-configurable and audit-logged.
   - *Proposed ticket title:* "TMX-DRIFT-THRESHOLD-CONFIG: move back-translation review threshold to per-tenant config + record in JobConfigSnapshot"

2. **`get_pending_reviews` identifier model conflates job_id and doc_id.** `get_doc_id_from_job` resolves an identifier only iff a `Document` with that id exists (A4-safe by design, well-documented), but the reviewer/job surface treats `Document.id` and job-id as interchangeable. A genuine non-document job-id will silently return `[]`. Acceptable today; worth a stable-ID hardening once TMX-3803 lands.
   - *Proposed ticket title:* "TMX-REVIEW-JOBID-STABLE: distinguish job-id vs doc-id in review queue once stable segment IDs ship (A5)"

3. **`FeedbackWidget.tsx` at 517 lines** is the largest new file. Below the `mega_files_800` threshold and ratchet stayed green, so no action required — flagging only as a watch item if it grows.
   - *Proposed ticket title (watch-only):* "TMX-FEEDBACK-WIDGET-SPLIT: extract form/state hooks if FeedbackWidget crosses 800 lines"

## Modularity / single-source drift check

No new forks or `if domain == X` chains introduced. Positive signals: (a) `semantic_drift` extracted to its own module (`384eb16`), removing logic from the thread-unsafe `quality_gate` singleton's surface; (b) language packs added through the existing `_packs` registry dict via `factory.get_pack`, not branch-per-language; (c) job/document filters are additive SQLAlchemy query composition; (d) `JobStatusBadge` consolidates two duplicated `getStatusBadge` helpers (one carrying hardcoded hex) into one canonical component — a single-source-of-truth win. New `Project`/`ProjectDocument`/`Feedback` tables correctly land in the operational `database.py` layer with `TenantScopedMixin + SoftDeleteMixin`, not deepening the A4 dual-model divergence, and the Feedback schema arrives as a discrete Alembic revision rather than a mega-migration. No re-introduction of the known-issue literals (`DEFAULT_ORG_ID`, `gpt-4o` hardcode, `placeholder_hash`) observed in the window.
