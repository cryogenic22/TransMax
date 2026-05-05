# Handoff to parallel team — Sprint 1 batch (2026-05-05)

This is a coordination doc, not a memory. Once the team has acknowledged + acted, archive or delete.

---

## TL;DR

Your proposed Sprint 1 batch (TMX-3010 → 3011 → 3015 → 3012 → 3212 → 3100) is **approved with two adjustments**:

1. **Drop TMX-3212 from your batch.** I'm closing it now (code + tests committed locally; closing red-team + commit within ~30 min).
2. **TMX-3100 is yours.** Your dependency chain (3010 → 3011 → 3100) makes you closer to it; landing 3100 without `organization_id` FK would be wasted work. I'm dropping it from my queue.

Your revised batch: **TMX-3010 → 3011 → 3015 → 3012 → 3100** (5 tickets).

You can start now. No further sign-off needed.

---

## My queue (so we don't collide)

After dropping TMX-3212 (closing) and TMX-3100 (yours):

1. ~~TMX-3212~~ — closing today
2. eval `number_001` — `app/services/quality_gate.py` + `app/services/language_packs/`
3. eval `good_001` — `app/services/language_packs/` (Spanish frequency check)
4. TMX-3600 — `frontend/next.config.ts` + redirect map + `docs/ia_migration.md`
5. TMX-3200 + 3201 — `app/agents/prompts/` (new dir) + `app/agents/prompts.py` migration

**File paths I will touch:** `app/agents/`, `app/services/quality_gate.py`, `app/services/language_packs/`, `frontend/`, `docs/ia_migration.md`. **File paths you will touch:** `app/models/`, `app/services/db_service.py`, `app/services/audit_service.py`, `alembic/versions/`, plus the audit endpoint + RBAC plumbing. We don't overlap.

The one shared file is `app/agents/graph.py` — I'm in there for TMX-3212 and (later) TMX-3600's frontend wiring won't touch it. You'd only touch it if TMX-3012's tenant-scoped session changes the way `get_db_service()` is invoked from the graph nodes — if so, please rebase on my closed TMX-3212 commit (will be on `main` before you start 3012).

---

## Coordination protocol — the loop board

The handoff mechanism is `.context/loops/`. Three rules (see `.context/loops/README.md`):

1. **Worksheet-first locking.** Before starting each ticket, create `.context/loops/TMX-XXXX.md` from `_template.md` with `Owner:` filled in (something like `parallel-team` or your agent name).
2. **Pod boundaries = file-tree boundaries.** CODEOWNERS encodes them.
3. **Red-team is independent.** When your ticket reaches stage 6, append to your worksheet's status log with `red-team requested from <name>`. I'll do the same in reverse.

Use `_template.md` as your starting point. Fill stages as you go; never edit a stage retroactively without an `Updated:` note.

---

## Your two design judgement calls — both approved

### A4 dual-model layer

**Approved**: add `organization_id` to **both** `app/models/database.py` and `app/models/translation.py`.

Rationale: per addendum A4, the translation layer is Postgres-only with UUIDs; per addendum A1, the audit chain in that layer needs org-scoping to verify per-tenant. Adding the column to `database.py` only would create a verifiable-only-globally audit chain — that's a regression of the differentiator.

**Constraint**: in the migration commit message, explicitly note that TMX-3017 will rationalise the two layers. Don't deepen the divergence elsewhere — if a new column or table addition would only need to live in one layer, only add it to one.

### Backfill default-org

**Approved**: `id=00000000-0000-0000-0000-000000000001`, `name='default'`, `slug='default'`. Backfill all existing rows to that org, then `ALTER COLUMN organization_id SET NOT NULL`. Standard pattern.

**Addition**: also add `org_kind='system'` (or equivalent enum) on the row so it's filterable from real customer orgs in dashboards. When the first real customer lands they get `org_kind='customer'` and the system org never accidentally surfaces in tenant-listing UIs.

---

## D-3 IdP — Kapil decision still open

`.context/active_tasks.md` line 73 carries Auth0 as the recommendation. TMX-3013 is intentionally **not** in your batch. Schema work (3010-3015) is IdP-agnostic, so you can land it without D-3 resolved.

When your batch is ~50% done (i.e. 3010 + 3011 landed), please flag back to Kapil so he has time to decide before TMX-3013 surfaces. Append a status-log line to your active worksheet with `D-3 reminder posted YYYY-MM-DD`.

---

## What I deliberately did not change in your batch

- Order: 3010 → 3011 → 3015 → 3012 → 3100. Correct dependency ordering.
- Sizing: ETA 1.5-2 days of focused work. Sounds right for 5 tickets including migrations.
- Per-ticket commit cadence: yes, commit per ticket (not per batch). Pre-commit red-flag-attestation + ratchet runs each time.

---

## What you owe me back

Acknowledge (a status-log line in any new worksheet you create works) and proceed. Specifically:

- [ ] Create `.context/loops/TMX-3010.md` with `Owner:` field set
- [ ] Confirm you are NOT touching TMX-3212 or TMX-3100-as-of-this-moment
- [ ] Begin TMX-3010

I'll close TMX-3212 and start eval `number_001` shortly. Status will be visible in `.context/loops/`.
