# TMX-UX-JOBS-RETRY — Retry affordance on the job-detail fetch errors

**State**: `[Done]`
**Owner**: Reviewer Frontend · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way`.
**Pre-mortem**: if this fails, a transient segments/doc fetch failure strands the reviewer on a dead page requiring a full browser reload.
**Blast radius**: `frontend/app/workspace/jobs/[id]/page.tsx`.

**Gates**: G1 PASS (small UI affordance; reuses existing fetch callbacks). G3 PASS (both error states now offer Retry; the auto-polling agent feed already self-recovers).

## 1. Task
The segments fetch is one-shot (TMX-3603-jobs-id-err surfaced the error but offered no recovery); the full-page doc error likewise. Add Retry. The agent-activity feed polls every 10s, so it self-recovers and needs no button.

## 2. Spec
- AC-1: segments error banner has a Retry that re-runs only the segments fetch and clears the error.
- AC-2: full-page (doc) error has a Retry that re-runs `fetchData`.
- AC-3: no behavioural change when there is no error.

## 3. Design
Split `fetchSegments` out of `fetchData`; the banner calls it directly. `fetchData` resets loading/error and reuses `fetchSegments`. Buttons use the existing amber/red banner palette.

## 4. Code
| File | Change |
|---|---|
| `frontend/app/workspace/jobs/[id]/page.tsx` | `fetchSegments` callback + Retry buttons + RefreshCw import |

## 5. Eval / Test
typecheck/lint/vitest(123)/build green. (No new unit test — pure affordance over existing fetch callbacks; behaviour covered by the existing error-state tests + manual reasoning.)

## 6. Red team
`fetchData` now sets `setLoading(true)` on retry — re-shows the loading state, correct. `fetchSegments` clears `segmentsError` first so a successful retry removes the banner. Agent feed intentionally left to auto-poll (documented). Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: f4ad0b1 (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | retry on both fetch-error states |
