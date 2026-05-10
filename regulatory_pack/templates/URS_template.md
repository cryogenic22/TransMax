---
document_type: URS
title: User Requirements Specification - TransMax
release: $release
version: 1.0.0
generated_at: $generated_at
generator: regulatory_pack.generators.pack_builder (TMX-3500)
signed_by: []
traceability_keys:
  - ticket_id
  - ac_id
---

# User Requirements Specification (URS)

**Release:** $release
**Generated:** $generated_at
**Document type:** URS (User Requirements Specification)
**Standard:** GAMP 5 + EU Annex 11 + 21 CFR Part 11

> **STATUS:** Scaffold v0. Functional content is auto-extracted from the
> repo at generation time. Signature blocks below are intentionally empty -
> humans sign at release-readiness review.

## 1. Scope

TransMax is an auditable AI translation agent for pharmaceutical
documentation. This URS captures the user-facing requirements TransMax must
satisfy, traceable forward through the FS, IQ, OQ, and PQ documents.

The release this URS describes: **$release**.

## 2. Functional requirements (FR)

Numbered functional requirements derived from the active backlog. Each FR
maps forward to one or more FS-Req entries in the FS document.

The current authoritative source is `.context/active_tasks.md` plus the
`.context/loops/*.md` worksheets. The following tickets have shipped under
this release tag:

$ticket_summary

## 3. Non-functional requirements (NFR)

- **NFR-1 Auditability**: every state change in the translation pipeline
  emits a chained audit event before any external side effect (addendum
  A1).
- **NFR-2 Determinism at gates**: deterministic quality gates are
  separate from creative LLM-driven translation (addendum A2; PRD section 5).
- **NFR-3 No silent fallbacks**: regulator-facing artefacts never
  substitute mock content (addendum A3).
- **NFR-4 Stable IDs**: `segment_id`, `doc_id`, `audit_event_id` are
  stable across REST, MCP, SDK, webhooks, and UI (addendum A5).
- **NFR-5 Qualified-supplier provenance**: every LLM call records
  provider, model, model version, prompt version, and token usage in the
  JobConfigSnapshot (addendum A6; EU AI Act technical documentation).
- **NFR-6 Prompt versioning**: every prompt edit increments the prompt
  version (addendum A8).
- **NFR-7 Soft-delete only**: domain code never issues `DELETE FROM`;
  removals write tombstones (addendum A9).

## 4. Acceptance criteria summary

The detailed acceptance criteria per ticket are captured in the
`.context/loops/TMX-XXXX.md` worksheets and surfaced in the FS document's
traceability matrix.

Total acceptance criteria recorded in this release: **$ac_count**.

## 5. References

- Programme PRD: `research/draft_PRD.md`
- v3.0 release plan: `research/v3_pilot_ready_release_plan.md`
- Project addenda (A1-A10): `CLAUDE.md`
- Backlog: `.context/active_tasks.md`

## Signatures

This document is not valid until signed by the role(s) below. The
signature blocks are intentionally empty; the Programme Lead signs at
release-readiness review and the signature is appended (or recorded in
`signed_by` front-matter) by the release-management workflow.

- [ ] **Programme Lead** ........................ Date: ............ Signature: ............

(Programme Lead is the URS signing authority because URS captures
business-level user requirements, not implementation detail.)
