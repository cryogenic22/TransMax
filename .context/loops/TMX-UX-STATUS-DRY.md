# TMX-UX-STATUS-DRY — Single source of truth for the job-status badge

**State**: `[Done]`
**Owner**: Reviewer Frontend · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way`.
**Pre-mortem**: if this fails, job-status colours drift between surfaces and a rebrand requires hunting hard-coded hex in multiple files.
**Blast radius**: new `frontend/components/ui/JobStatusBadge.tsx`; `app/workspace/jobs/page.tsx` + `components/control_views/JobsView.tsx` (remove duplicated helpers).

**Gates**: G1 PASS (de-dupes TWO copies into one component; reuses design tokens; new test). G3 PASS (both surfaces use the canonical badge; no hard-coded hex remains).

## 1. Task
`jobs/page.tsx` and `JobsView.tsx` each defined a near-identical `getStatusBadge` — one with hard-coded hex colours (`#dcfce7`…), the other with Tailwind. Consolidate to one component (Single source of truth / config-not-branching).

## 2. Spec
- AC-1: `JobStatusBadge` maps queued/processing/completed/failed → Tailwind colour + icon + capitalised label; unknown → queued (slate).
- AC-2: both Jobs surfaces render `<JobStatusBadge>`; no local `getStatusBadge` remains.
- AC-3: no hard-coded hex colour in the badge output.

## 3. Design
New `JobStatusBadge` (job vocab) kept DISTINCT from `StatusBadge` (document/segment lifecycle vocab) — two status domains, one component each, rather than one branching on both. Removed now-unused lucide icon imports from both consumers.

## 4. Code
| File | Change |
|---|---|
| `frontend/components/ui/JobStatusBadge.tsx` | new canonical badge |
| `frontend/app/workspace/jobs/page.tsx` | drop helper; use badge; trim imports |
| `frontend/components/control_views/JobsView.tsx` | drop helper; use badge; trim imports |

## 5. Eval / Test
`frontend/__tests__/JobStatusBadge.test.tsx` (6, incl. a no-hex regression). typecheck/lint(0 warnings)/vitest(123)/build green.

## 6. Red team
Removed icon imports (Play/AlertCircle from jobs; all four from JobsView) — verified no other usage (lint passes at `--max-warnings 0`). Visual output preserved (icon + capitalised pill). Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: f4ad0b1 (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | one badge, no hex dupes |
