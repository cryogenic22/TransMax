# Ralph loops — per-ticket implementation discipline

**Owner**: Programme Lead (Kapil) + Antigravity
**Status**: Active 2026-05-05 onwards
**Why**: Each ticket goes through every quality stage before the next ticket starts. Scope creep, half-implementations, and "we forgot to test that" all happen when stages run in parallel across many tickets. The loop forces depth-first.

---

## The loop (per ticket)

```
1. Task        → Restate the ticket. What's the change? What's the blast radius?
2. Spec        → Write the acceptance criteria. AC-1, AC-2, ... Each must be falsifiable.
3. Design      → Pick the approach. If non-obvious, file an ADR under docs/decisions/.
4. Code        → Surgical edits. List file:line touched.
5. Eval/Test   → Add or update tests/evals. Run them. Capture the run output.
6. Red team    → Adversarial review: what could break? What did the spec miss?
                 At minimum, run /review (Tier 2 22-item checklist) on the diff.
7. Fix         → If the red team found something, fix it and re-run stage 5.
8. Deploy      → Commit (Self-review block filled), push, verify CI green.
                 Update .context/active_tasks.md status. Update ratchet baseline if metrics moved.
```

A ticket is **done** only when stage 8 closes. Skipping stages is broken-window territory (Tier 0).

---

## Per-ticket worksheet

Every ticket gets one file: `.context/loops/TMX-XXXX.md` (or `eval-<case_id>.md` for eval-driven loops). Use `_template.md` as the starting point. Fill stages as you go; never edit a stage retroactively without an `Updated:` note.

Worksheets are auditable and resumable: a future session (or a different agent) can land mid-loop and pick up from the last filled stage.

---

## Status taxonomy

A worksheet header carries one of:

| State | Meaning |
|---|---|
| `[Spec]` | Stages 1-2 complete; awaiting design. |
| `[Design]` | Stages 1-3 complete; awaiting code. |
| `[WIP]` | Stages 1-4 complete; tests being written. |
| `[Verify]` | Stages 1-5 complete; red-team in progress. |
| `[Fix]` | Red team found something; fixing. |
| `[Done]` | Stages 1-8 complete; commit on main. |
| `[Blocked]` | Waiting on Programme Lead, external dep, or upstream ticket. State why. |

The worksheet's `## Status log` section tracks transitions with timestamps.

---

## Why this is heavier than "just write the code"

- **Audit chain analogue**: each stage is the equivalent of an audit event. If it didn't happen on the worksheet, it didn't happen.
- **Multi-agent durability**: every loop produces an artefact a Lane worker or future session can pick up cold.
- **Reverses the entropy**: skipping red-team / test stages is exactly how the May 2026 review's tech-debt list got long.

If a ticket is genuinely too small to need stages 5-7 (say, a one-line typo fix), record that explicitly in the worksheet (`Stage 5: N/A — typo fix`) so the omission is deliberate, not accidental.

---

## Multi-agent coordination — the loop board IS the lock

When two agents (or a human + an agent, or two pods) are working concurrently, the loop board is the coordination mechanism. There is no separate "ticket lock" or "branch lock" — the worksheet's `Owner:` field is authoritative.

Three rules:

### Rule 1 — Worksheet-first locking

Before starting work on a ticket, create `.context/loops/TMX-XXXX.md` from `_template.md` with the `Owner:` field filled in (your agent name or pod name). The first writer wins. If a worksheet already exists for a ticket with another owner, **you do not take it** — coordinate by appending to that worksheet's `## Status log` section with your name and a request, and proceed to a different ticket.

If you find a worksheet stuck in `[Spec]` or `[Design]` with no progress for >24h and the owner is unreachable, you may take it over — but record the takeover explicitly in the status log with a justification.

### Rule 2 — Pod boundaries are file-tree boundaries

The CODEOWNERS file already encodes pod ownership. Don't reach across pod boundaries without an explicit coordination note. If your ticket needs a change in another pod's path, either (a) hand off that part to the owning pod via a follow-up ticket, or (b) get explicit owner sign-off in the worksheet's status log.

Crossing boundaries silently is the fastest way to land conflicting changes that pre-commit can't see and CI can't catch until they collide.

### Rule 3 — Red-team is independent

When your ticket reaches stage 6 (red team), don't just review your own diff. Request red-team from another agent / pod by appending to your worksheet's status log. Cross-pod red-team catches blind spots a single-author review misses (different mental models, different failure-mode intuitions). Reciprocate when asked.

For loops where cross-pod red-team isn't available (e.g. solo work outside business hours), you may self-review using `/review` (Tier 2 22-item checklist) — but record this explicitly so the asymmetry is visible.

### Concurrent-work example

> Pod A: Auth & Tenancy is running TMX-3010 → 3011 → 3015 → 3012 → 3100.
> Pod B: Agent & AI is running TMX-3212 → eval-fixes → TMX-3600 → TMX-3200/3201.
>
> Pod A's work touches `app/models/`, Alembic, `app/services/db_service.py`, `app/services/audit_service.py`.
> Pod B's work touches `app/agents/graph.py`, `app/services/quality_gate.py`, `app/agents/prompts.py`, `frontend/`.
>
> Worksheets: each pod creates their own `TMX-XXXX.md` files with `Owner: pod-A` or `Owner: pod-B`. Pod B claims TMX-3212 first (already in flight); Pod A drops it from their batch. Pod A claims TMX-3100; Pod B drops it from theirs.
>
> When TMX-3100 reaches stage 6, Pod A requests red-team from Pod B (the audit chain consumer). When TMX-3600 reaches stage 6, Pod B requests red-team from Pod A (cross-cutting infra concern).

---

## Pointers

- Loop output worksheets: `.context/loops/TMX-XXXX.md`
- Backlog: `.context/active_tasks.md`
- Decision log: `.context/lead_decisions.md`
- Plan: `research/v3_pilot_ready_release_plan.md`
- ADR template: `docs/decisions/_template.md`
- CODEOWNERS (pod boundaries): `.github/CODEOWNERS`
