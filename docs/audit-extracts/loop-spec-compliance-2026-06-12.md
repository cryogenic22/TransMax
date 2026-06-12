# Loop Spec-vs-Delivery Audit — 2026-06-12 (Agent 4)

**Scope:** tickets shipped in `2d2a800..e06c9a2` (HEAD~25..HEAD). Observation only.

## Headline

**14 Match / 0 Partial / 0 Drift / 0 Tests-only of 14 tickets audited.**

All audited SHAs are on `origin/main` (verified via `git branch -r --contains`). The two A3-honesty loops (TMX-TOOLS-CONF-HONEST, TMX-UX-QDASH-REAL) genuinely remove the fabricated values in *source*, not just in tests. No Gate-2/Gate-3 violations found.

## Verdict table

| Ticket | SHA | Verdict | Rationale |
|---|---|---|---|
| TMX-3105a | a4ec99d | Match | `status` + `chain_head_hash` added to `verify_v2`; `_derive_status` precedence pinned by test. |
| TMX-VERIFY-ORG | a4ec99d | Match | `GET /verify_v2/org` wraps `verify_org_chain`, `all_ok` rollup, route ordering tested. |
| TMX-TOOLS-CONF-HONEST | 4cda63e | Match | Fabricated `90.0`/`"High"` default removed; outage → `confidence=null`/`Unavailable`/`needs_review`. |
| TMX-QDASH-CONTRACT | 4cda63e | Match | `breakdown_reasoning` + real `score_breakdown` surfaced in response. |
| TMX-AUDIT-DB-DOCID-LOOKUP | 4cda63e | Match | `pass`-stub replaced with real `get_doc_id_from_job` + `get_flagged_segments` delegation; `[]`+WARNING on miss. |
| TMX-UX-QDASH-REAL | f4ad0b1 | Match | Accuracy/Fluency/Terminology bars deleted; renders real penalties + N/A unavailable state. |
| TMX-UX-PROV-COPY | f4ad0b1 | Match | CopyButton + aria-label on full hash; no-hash branch unchanged. |
| TMX-UX-JOBS-RETRY | f4ad0b1 | Match | `fetchSegments` split out; Retry on both error states. |
| TMX-UX-SEG-COUNT | f4ad0b1 | Match | Derived total/translated/needs-review summary bar. |
| TMX-UX-STATUS-DRY | f4ad0b1 | Match | Two `getStatusBadge` helpers consolidated to `JobStatusBadge`; no-hex test. |
| TMX-BB-SYNTH / -FORBIDDEN | 2bd6ecd | Match | Synthetic black book + loader + dead-code cleanup; tested. |
| TMX-LANG-EU1/EU2 + 3802 + EVAL | 942a8cf | Match | 8 EMA packs + CJK segmenter + extended golden eval; 33 new tests. |
| TMX-PROJECTS + JOBS-FILTER | 36c5262 | Match | New `projects` tables (additive, A4-safe) + service + filters/metrics. |

## Per-ticket detail

**TMX-3105a / TMX-VERIFY-ORG (a4ec99d).** Asked: machine-stable `status` headline + `chain_head_hash`; org-wide `all_ok` verdict. Shipped: `_derive_status` (sequence-gap precedence over tamper), hex head hash under tenant session, `verify_v2_org_chains` route registered before `/{audit_id}`. Tests +5, cross-tenant exclusion pinned. Gap: none; pagination consciously deferred (TMX-VERIFY-ORG-PAGINATE).

**TMX-TOOLS-CONF-HONEST / -QDASH-CONTRACT (4cda63e).** Asked: stop emitting `confidence=90.0`/`band="High"` on a scoring outage; surface real reasoning. Shipped (diff verified): defaults flipped to `scoring_available=False`/`confidence=None`/`"Unavailable"`; `except` adds a review_note and forces review; success path sets real values + `breakdown_reasoning`. This is a real A3 fix in source, not a test. Gap: none.

**TMX-AUDIT-DB-DOCID-LOOKUP (4cda63e).** Asked: replace the `pass`-bodied stub that silently returned `None`. Shipped (diff verified): `get_doc_id_from_job` (Document-only, A4-safe — no cross-layer query), `get_pending_reviews` now delegates and logs+returns `[]` on miss. Dead imports/var cleaned. Gap: none — genuine Gate-2/3 closure.

**TMX-UX-QDASH-REAL (f4ad0b1).** Asked: remove fabricated Accuracy/Fluency/Terminology bars. Shipped (diff verified): `ScoreItem`/`metrics.accuracy|fluency|terminology` deleted; renders `breakdown` penalties + `breakdownReasoning`; `!scoringAvailable` → amber "scoring unavailable" + `N/A`. The fabricated trust signal is gone at the source. Gap: none.

**TMX-UX-PROV-COPY / -JOBS-RETRY / -SEG-COUNT / -STATUS-DRY (f4ad0b1).** Small reviewer-UX affordances; each AC maps to a concrete diff hunk (CopyButton aria-label, `fetchSegments` retry, segment summary bar, `JobStatusBadge` de-dup). PROV-COPY, QDASH-REAL and STATUS-DRY carry new vitest specs; JOBS-RETRY and SEG-COUNT are presentational and rely on typecheck/build + existing error-state tests — defensible (no new logic to regress), not tests-only. Gap: none.

**TMX-BB-SYNTH / -FORBIDDEN (2bd6ecd).** Asked: synthetic black book demonstrating term/forbidden/rule enforcement. Shipped: `veridian_blackbook.json` (3 pairs, 36 terms each, 12 forbidden, 17 rules), idempotent tenant-scoped loader with fail-loud `validate_blackbook`, dead think-aloud block in `get_constraints` removed. Anti-bloat note: synthetic demo data passes G1 as pilot/demo value and adds no runtime path; acceptable.

**TMX-LANG-EU1/EU2 + 3802 + EVAL (942a8cf).** Asked: deeper EMA language coverage + CJK segmentation. Shipped: 8 official-language packs with negation + decimal-comma gates, CJK segmenter (ideographic full stop), golden eval extended en→ja/de. 33 new tests, suite green. Gap: none.

**TMX-PROJECTS + JOBS-FILTER (36c5262).** Asked: group documents/jobs into projects + richer job query. Shipped: additive `projects`/`project_documents` tables (no Alembic column-add — Kapil-gated columns correctly parked), `ProjectService`, CRUD/membership API, `target_language`/`project_id` filters + `/documents/metrics` rollup. Soft-delete + tenant-scope honoured. Gap: none.

## Proposed follow-up ticket TITLES (not created)

- **TMX-VERIFY-ORG-PAGINATE** — paginate org-wide verify for orgs >~1k jobs (already self-spawned in worksheet).
- **TMX-UX-JOBS-RETRY-TEST** — add a vitest unit pinning the segments-retry clears the banner (close the no-new-test gap on the presentational UX loops).
- **TMX-UX-SEG-COUNT-TEST** — unit-cover the needs-review count derivation against `gate_results.violations`.
- **TMX-PROJECTS-SCHEMA-COLS** — Kapil-gated Alembic loop for the parked priority/due_date/reviewer_id columns (so the TMS workflow isn't left half-built).
- **TMX-QDASH-SCORE-PROVENANCE** — render which model/prompt version produced the confidence score on the QualityDashboard (A6/A8 trust signal), now that real breakdown_reasoning is surfaced.
