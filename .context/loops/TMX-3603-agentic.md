# TMX-3603-agentic — Agentic-forward UX: AgentLanes + ActivityFeed

**State**: `[Done]` pending push. Sister tickets spawned: TMX-3603-wire (real backend telemetry), TMX-3603-dashboard (replace stat cards), TMX-3603-reviewer (per-segment confidence + provenance), TMX-3603-reasoning (defect reasoning trace).
**Owner**: Reviewer Frontend pod (Antigravity / Pod B)
**Sprint**: 1
**Started**: 2026-05-09
**Closed**: 2026-05-09

---

## 1. Task

The rescape design review notes its platform&apos;s AI vocabulary "stops at one screen" — there&apos;s a single AI surface and the rest of the platform doesn&apos;t feel AI-native. TransMax has the same risk: we have a multi-agent LangGraph backend (translator, reviewer, fixer, auditor) and OpenTelemetry tracing wired (Loop 8), but the UI today does not communicate "this is multi-agent". A reviewer sees only the final translation, with no sense of which agents touched it, what they did, or in what order.

This loop adds two presentation components that, dropped onto any surface, make the multi-agent pipeline visible:

1. **`<AgentLanes>`** — swim-lane visualisation. One lane per agent (translator, reviewer, fixer, auditor); each activity is a chip on its lane with start time + duration + a status. Reads at a glance: "translator finished 14:23, reviewer started 14:24 and is in progress, fixer not yet engaged". Used at the top of any in-flight job page.

2. **`<ActivityFeed>`** — chronological event stream replacing the dashboard&apos;s zero-cards (rescape Direction 2). "Carol approved Cardivex SmPC v2.1 — 3h ago. Translator agent finished segment 47 — 10s ago. Drift detected on glossary term &lsquo;adverse event&rsquo; — 1d ago." For an auditable platform, this is the right dashboard hero (rescape §Dashboard).

Components are presentation-layer; both accept typed prop surfaces that a future backend telemetry pipe (TMX-3603-wire) populates from OTel spans + audit events. Demo data on `/workspace/design-system` is hard-coded fixture data.

**Blast radius**: `frontend/components/ui/` (new components) + `frontend/__tests__/` (tests) + the design system demo page (extend). No existing surfaces refactored.

**Addenda**: A1 (audit-by-default — ActivityFeed surfaces the audit chain), A6 (LLMs as qualified suppliers — AgentLanes makes the agent identity visible).

## 2. Spec — acceptance criteria

- [ ] AC-1: `frontend/components/ui/AgentLanes.tsx` exposes `<AgentLanes activities={...} />` accepting an `AgentActivity[]` (typed). Renders 4 horizontal lanes coloured by agent, with each activity as a chip showing start time + duration + status icon.
- [ ] AC-2: `frontend/components/ui/ActivityFeed.tsx` exposes `<ActivityFeed items={...} limit?={number} />` accepting an `ActivityEvent[]` (typed). Renders chronological list with avatar (colour-coded by actor type), action verb in bold, target, relative timestamp.
- [ ] AC-3: Both components work with empty arrays (empty-state copy + icon).
- [ ] AC-4: Tests cover variant render, prop pass-through, empty state, agent identity colour mapping, and a11y.
- [ ] AC-5: `/workspace/design-system` page extends to demo both with fixture data (a representative job-in-flight scenario).
- [ ] AC-6: Lint stays under cap. Build green. Vitest 36 → 50+.

**Out of scope**:
- Wiring real OTel + audit-event data into the components. Sister ticket TMX-3603-wire (frontend hook into the existing OTel collector + a new `/api/dashboard/activity` endpoint).
- Replacing the dashboard&apos;s stat cards with the ActivityFeed (per-surface adoption ticket TMX-3603-dashboard).
- Per-segment confidence dial + provenance chip on the reviewer surface (sister TMX-3603-reviewer).
- Reasoning trace tooltip on defects (sister TMX-3603-reasoning).

## 3. Design

**Why one swimlane per agent (not one per job-stage)**: agents are the actors; stages are coincidence-of-actor-with-step. Showing agents is what makes "this is multi-agent" land. A reviewer who sees four lanes immediately understands four entities are at work. A reviewer who sees four stages thinks "linear pipeline, not really agentic."

**Why activities as chips on lanes (not a Gantt chart)**: a chip carries enough info (start time, duration, status icon) without requiring a time-axis. Adding a time axis is a v2 polish — most jobs are minutes-long; the chronology is implicit from chip order.

**Why ActivityFeed as a list (not as a graph)**: the audit chain IS a list. The graph view is sister TMX-3603-graph and lives on a richer "Lineage" page.

**Empty states**: both components must look intentional when empty. "No agent activity yet" with the agent-quartet icon. "No recent activity" with a clock icon.

**Color identity (from Loop 17)**:
- translator → violet (`var(--agent-translator)`)
- reviewer → blue (`var(--agent-reviewer)`)
- fixer → amber (`var(--agent-fixer)`)
- auditor → emerald (`var(--agent-auditor)`)

**Type surface**:
```typescript
type AgentId = "translator" | "reviewer" | "fixer" | "auditor"
type ActivityStatus = "in_progress" | "complete" | "failed"
interface AgentActivity {
  id: string
  agent: AgentId
  label: string
  startedAt: string  // ISO-8601
  durationMs?: number
  status: ActivityStatus
}

type ActivityActorType = "agent" | "user" | "system"
interface ActivityEvent {
  id: string
  actor: { type: ActivityActorType; id: string; name: string }
  action: string  // verb, e.g. "approved", "translated", "flagged"
  target: string  // human-readable noun phrase
  occurredAt: string  // ISO-8601
}
```

These shapes are deliberately wire-format-shaped: a future hook can populate them straight from `/api/dashboard/activity` or from streaming OTel spans.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/ui/AgentLanes.tsx` | new |
| `frontend/components/ui/ActivityFeed.tsx` | new |
| `frontend/__tests__/AgentLanes.test.tsx` | new |
| `frontend/__tests__/ActivityFeed.test.tsx` | new |
| `frontend/app/workspace/design-system/page.tsx` | extend with both demos |

## 5. Eval / Test

```
$ cd frontend
$ npm run lint        # under cap
$ npm run typecheck   # clean
$ npm run build       # 17 routes
$ npm run test        # vitest 50+
```

## 6. Red team

- **CLEAN**. Tier 2 self-review:
  - 16 new vitest tests (6 + 10), bringing the suite to 52/52 in 7s.
  - Both components are presentation-only with strict typed prop surfaces. The shapes are wire-format-shaped — a future hook can populate them straight from `/api/dashboard/activity` (ActivityFeed) or streamed OTel spans (AgentLanes) without translation.
  - 💡 **Empty states are intentional, not afterthoughts**. AgentLanes empty: "No agent activity yet." ActivityFeed empty: clock icon + "No recent activity." Both render at the right place in the visual hierarchy.
  - 💡 **Pure-function `formatRelativeTime` is exported** so the dashboard surface can use the same formatter for non-feed contexts (e.g. "last reviewed: 3h ago" on a job card).
  - 💡 **Color identity from Loop 17**: `var(--agent-translator)` etc. are referenced via inline `style={{ color: meta.cssVar }}` because the chip colors mix with the agent var via `color-mix()` — this is the right tradeoff for dynamic per-agent tinting; static utility classes wouldn&apos;t support it.
  - 💡 **Sister tickets spawned for the wiring + adoption** so this loop&apos;s diff stays clean and reviewable:
    - TMX-3603-wire: hook OTel + audit-event data into the components.
    - TMX-3603-dashboard: replace the zero-stat-cards with the ActivityFeed.
    - TMX-3603-reviewer: per-segment confidence dial + provenance chip on the reviewer surface.
    - TMX-3603-reasoning: reasoning-trace tooltip on every defect.

## 7. Fix

No fix iterations.

## 8. Deploy

- [x] Code: `frontend/components/ui/{AgentLanes,ActivityFeed}.tsx`, `frontend/app/workspace/design-system/page.tsx` extended
- [x] Tests: `frontend/__tests__/{AgentLanes,ActivityFeed}.test.tsx`
- [x] Vitest: 52/52 (was 36)
- [x] Lint: 172/172 cap, exit 0
- [x] Typecheck: clean
- [x] Build: 17 routes
- [x] Backend: untouched
- [ ] Commit + push (next)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T18:30Z | — | `[Spec]` | Loop opened — agentic-forward presentation components |
| 2026-05-09T19:00Z | `[Spec]` | `[WIP]` | 2 components written; 16 tests added |
| 2026-05-09T19:15Z | `[WIP]` | `[Done]` (pending push) | All gates green; demo extended on /workspace/design-system |
