# TMX-DOC-KNOWNISSUES — Refresh CLAUDE.md "Known issues" (mark resolved)

**State**: `[Done]` — `2a0dad0` on origin/main
**Owner**: Platform & Observability
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — doc-only.
**Pre-mortem**: none — documentation accuracy; the risk it removes is a future agent "re-fixing" an already-fixed issue or treating a fixed path as broken.
**Blast radius**: `CLAUDE.md` (Known-issues section split into Resolved / Still-open).

**Gates**: G1 ✅ (trust — A10 program-brain integrity: stale "known issues" mislead every future session). G2 N/A. G3 ✅ — 6 verified-resolved issues moved to a Resolved subsection with their tickets/SHAs; genuinely-open issues retained verbatim (incl. Kapil-gated `.env`/`transmax.db` warnings).

## Spec
- AC-1: graph.py model/timestamp/iteration_count/output_hash, auto-approval 0.90, and `text.split('.')` segmentation are marked RESOLVED (each verified in code before marking).
- AC-2: open issues (audit-chain hashing C-04, transmax.db, .env key, mega-migration, quality_gate singleton, resilience globals, PII regex) retained, with the .env/db Kapil-gated warnings unchanged.

## Test
Manual verification each "resolved" claim against current code (resolve_model, datetime.now utc, force_finalize, real output_hash, no-threshold learning_service, segmenter).

## Deploy
- [x] Commit: `2a0dad0` (batch B)
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done]` — `2a0dad0` on origin/main | known-issues list reconciled to reality |
