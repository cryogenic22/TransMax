# ADR-0004: Persisting reviewer accept/reject decisions on DOCX revisions

**Date:** 2026-05-09
**Status:** proposed — awaiting Programme Lead sign-off (one-way schema change)
**Loop:** TMX-3702-v2 (sister of TMX-3702-v1 shipped in `a48c2b6`)

## Context

TMX-3700 captured DOCX tracked-change marks (`<w:ins>`, `<w:del>`, `<w:moveFrom>`, `<w:moveTo>`) at ingestion time and persisted them in `Segment.element_meta.revisions`. TMX-3702-v1 surfaced that data in the reviewer surface as a passive indicator pill (`<RevisionIndicator>`).

What's missing: the reviewer needs to **act** on the indicator. Three interaction modes are needed in v2:

1. **Accept all revisions in this segment** — implicitly the case if reviewer approves the segment. We should still record it explicitly so the audit chain can point at the decision.
2. **Reject all revisions** — keep the source as-is, ignore the inserts/deletions/moves. Re-raise the original (pre-revision) text for translation review.
3. **Per-revision accept/reject** — surgical, per `<w:ins>`. Out of scope for v2 (would require TMX-3700 v2 to capture per-revision text bodies; flagged TMX-3703).

So v2 is segment-level accept-all / reject-all. The persistence question is: where do we write the decision?

This ADR exists because the answer involves a **one-way schema change**, and per the loop-driven-dev v1.1 discipline (`Reversibility: one-way → human approval before stage 4`), the call needs explicit sign-off before implementation.

## Decision

**Add a new column `revision_decision` (String, nullable, default null) on `Segment`, with a typed enum value: `pending | accepted | rejected`.** Backfilled to `pending` for any segment that has `element_meta.revisions` and to `null` for those that don't (no revisions = no decision needed).

A new endpoint `PATCH /api/segments/{id}/revision-decision` writes it, with the change captured in `ChangeLog` (existing audit trail).

## Consequences

**Better:**
- Single boolean question (was the revision-set accepted?) lives at the same layer as the rest of the segment state. Queryable, indexable.
- Audit chain inherits the existing `ChangeLog` infrastructure — A1 (audit-by-default) satisfied without new tables.
- Frontend can read the field straight off `Segment` — no separate fetch.

**Worse:**
- Adds a column to the segments table (one of the larger tables in the system).
- Forward migration is fast (nullable column add); rollback is `DROP COLUMN` which is also fast on Postgres but loses the data — call this out explicitly in the migration commit message.
- Mixes "source-side metadata" (`element_meta.revisions`) and "decision-side metadata" (`revision_decision`) at the same row. Slightly less normalised than option B (separate table) but matches how the rest of the system works (`status` and `validation_score` co-locate).

**Becomes possible:**
- Filter the reviewer queue: "show me segments with pending revision decisions". Single indexed-column query.
- Back-translation / re-translation pipeline can branch on the decision (e.g., re-translate from pre-revision source if rejected).

**Becomes hard:**
- Per-revision (not per-segment) decisions. v3 would either (a) blow this column up into JSON, (b) introduce a sibling table (option B below). Either is a bigger migration than today's add-column. We accept this trade-off because v3 is conjecture and v2 is a real ticket.

## Alternatives considered

- **Option A — `revision_decision` String column on Segment (chosen).** Simplest, matches existing patterns. One-way migration but trivial.
- **Option B — Sibling table `segment_revision_decisions(segment_id FK, decision, actor, timestamp)` with a UNIQUE on segment_id**. More normalised; supports a future per-revision decision row pattern by relaxing the unique. Two-way reversibility (drop the table + index, no Segment-row pollution). **Rejected**: heavier per-query (JOIN), and the per-revision case is conjecture.
- **Option C — Reuse `Segment.element_meta.revisions.decision` JSON key (no schema change)**. Two-way. **Rejected**: conflates source-side facts (which authors made marks) with decision-side facts (what the reviewer chose). Querying `WHERE revision_decision = 'pending'` becomes a JSON path traversal, slow at scale, painful to index.
- **Option D — Defer**: skip persistence in v2; accept-all is implicit from `Segment.status='approved'`, reject-all is implicit from leaving the segment in `review_required`. **Rejected**: the implicit mapping conflates "I approved the translation" with "I accepted all source revisions". A reviewer might approve the translation while explicitly rejecting an editorial revision in the source. Audit chain needs both.

## Affected teams / surfaces

- **Pod B (Reviewer Frontend)** — owns the loop, primary impact.
- `app/models/database.py:Segment` — column add.
- New Alembic revision under `migrations/versions/` (one per the project's `no mega-migrations` rule).
- `app/api/schemas.py:SegmentResponse` — adds `revision_decision: Optional[str]`.
- `app/api/segments.py` — new `PATCH /segments/{id}/revision-decision` endpoint (mirrors existing PATCH structure; writes ChangeLog).
- `frontend/lib/api.ts:Segment` — adds the field.
- `frontend/components/ui/RevisionIndicator.tsx` — extend with `decision` prop + Accept / Reject buttons (or extract action UI into sibling `<RevisionActions>`).
- `frontend/app/workspace/jobs/[id]/page.tsx` ReviewView — wires the action handler.
- Audit pipeline (Pod A territory) — verify `ChangeLog` entries flow into the v2 audit chain.

## Implementation gates (loop-driven-dev)

This decision does NOT auto-implement. Per the v1.1 discipline:
1. Programme Lead (Kapil) reviews this ADR and either accepts, rejects, or asks for an alternative.
2. On acceptance, the implementation loop opens as `TMX-3702-v2.md` worksheet with `Reversibility: one-way` clearly marked, the migration revision filed under `migrations/versions/`, and the standard 8-stage flow.
3. The migration commit goes in its own commit (separable from the API + UI work) so a forward-only deploy hazard is isolated.

## Reviewer questions

- Does the implicit `status='approved' = accept-all-revisions` mapping suffice, making this whole ADR unnecessary? (Option D)
- Is per-revision (not per-segment) decision-making in v3 likely enough that we should pre-build option B's sibling table now?
- Should the column be `String` (free-form, future-flexible) or a typed Postgres ENUM (constrained, less flexible)?
- Who is the actor on the ChangeLog entry — the reviewer's user_id, or a fixed `revision-decision-handler` service identity? (TMX-3013 Auth0 wiring affects this; recommend deferring until Auth0 lands.)

## Status

`proposed`. Awaiting Programme Lead's call. Per the loop-driven-dev one-way-decision discipline, no implementation begins until this ADR is `accepted`.
