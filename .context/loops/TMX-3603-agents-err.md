# TMX-3603-agents-err — surface agent-activity poll errors on jobs page

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: If this fails in production, the failure mode is — an operator monitoring a translation job mid-flight sees the AgentLanes panel empty. They can't tell whether (a) no agents are running yet, (b) all agents finished, or (c) the agent-activity endpoint is returning 500 and the polling has been failing silently for 5+ minutes. They wait, refresh, eventually open a support ticket.
**Blast radius**: `frontend/app/workspace/jobs/[id]/page.tsx` (read existing error from the hook; one new conditional banner). `frontend/e2e/segments-revisions.spec.ts` (1 new test). No backend, hook, or wire change — the hook already surfaces `error`.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — completes the same page's error story (doc + segments + agents triad). (a) needed: yes — same A3 class on the same page; (b) <5 callers: 1 file; (c) bundle: negligible; (d) reuses existing hook return shape (error already there) + same banner pattern; (e) test fails without it: yes — agent-activity 500 currently shows empty lanes silently.
- [ ] **G2 Reproduce-failure** — Playwright stub of agent-activity → 500 RED before fix.
- [ ] **G3 Completion** — when the agent-activity endpoint fails, an inline banner with the actual error renders near AgentLanes; when it succeeds (empty array OR with data), no banner renders.

---

## 1. Task

`useAgentActivityByJob(jobId)` returns `{data, loading, error}`. The jobs page consumer at line 66 destructures only `data`:

```ts
const { data: agentActivities } = useAgentActivityByJob(jobId)
```

`AgentLanes activities={agentActivities ?? []}` then renders an empty (or stale) panel on any failure mode. The `error` field is silently dropped. Note: this is the SAME class as the doc/segments fetch issue I just fixed in TMX-3603-jobs-id-err — the page now has an inconsistent error story (doc/segments shout, agent-activity stays silent). This loop completes the triad.

**Addenda**: A3 (no silent fallbacks), A1 (audit-by-default — agent activity is part of the audit signal).

## 2. Spec — acceptance criteria

- [ ] AC-1: When the agent-activity-by-job endpoint returns 500, an inline `role="status"` banner renders near AgentLanes (in Overview and Translate modes — Review mode doesn't show lanes, so no banner needed there) with text containing the actual server error.
- [ ] AC-2: When the endpoint returns successfully (empty array or with activities), no banner renders.
- [ ] AC-3: Banner uses `aria-label="Agent activity feed failed to load"` to distinguish from the segments-error banner already on this page.
- [ ] AC-4: All existing 4 e2e tests on this page still pass.
- [ ] AC-5: 1 new e2e test in `frontend/e2e/segments-revisions.spec.ts`:
  - "renders agent-activity error banner when poll fails" — stubs doc + segments OK, agent-activity → 500, navigates to `?mode=translate` (where lanes show), asserts banner visible with stub-supplied detail.

**Out of scope**:
- Retry button (defer).
- Distinct UI for transient (one fetch) vs persistent (10 polls) failures — too clever; surface the latest error.
- Toast notifications.

## 3. Design

```ts
const { data: agentActivities, error: agentError } = useAgentActivityByJob(jobId)
```

Render a banner above AgentLanes in the Overview and Translate views (NOT Review — AgentLanes doesn't appear there):

```tsx
{agentError ? (
  <div role="status" aria-label="Agent activity feed failed to load" className="...amber...">
    <strong>Agent activity feed unavailable.</strong> {agentError.message}
  </div>
) : null}
<AgentLanes activities={agentActivities ?? []} />
```

The `useAgentActivityByJob` hook keeps polling on each interval. So if the endpoint comes back, the next poll clears the error (the hook resets `error: null` on success). Banner auto-dismisses — no extra logic needed.

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/jobs/[id]/page.tsx` | Destructure `error` from the hook; render a banner above each `<AgentLanes>` instance. |
| `frontend/e2e/segments-revisions.spec.ts` | 1 new test for the failure mode. |

## 5. Eval / Test

```
$ cd frontend && npm run e2e -- segments-revisions.spec.ts --workers=1
$ npm run lint && npm run typecheck && npm run build
```

Expected: 5/5 e2e (was 4, +1), lint/typecheck/build clean.

## 6. Red team

- **Banner placement and helper extraction**: created a small `AgentErrorBanner` component and rendered it in BOTH Overview and Translate views (the two modes that show AgentLanes). Review mode doesn't show lanes, so no banner there — correct scoping.
- **Auto-dismissal**: the hook polls every 10s and resets `error: null` on a successful response, so the banner naturally disappears when the endpoint comes back up. No extra logic needed.
- **Aria-label distinguishability**: "Agent activity feed failed to load" is distinct from the segments banner "Segments failed to load" so a screen reader user with both errors would hear two distinct labels rather than ambiguous repeats.
- **Anti-pattern check (sticky errors)**: an old transient error from a previous fetch wouldn't linger because `setState` always replaces the full state object (data + loading + error), not merges. Verified by re-reading the hook.
- **Agent-activity 4xx vs 5xx**: hook throws `Error("HTTP ${status}")` for any non-OK; banner shows whatever message the hook synthesises. Acceptable — the user can ask ops what HTTP 401/403/500 means in context.

CLEAN — no findings.

## 7. Fix

No iterations needed. RED on first test, GREEN after the consumer change + AgentErrorBanner extraction.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — completes the page's error story; small helper extraction.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: agent-activity 500 visible in both Overview and Translate modes.
- [x] e2e: 5/5 in segments-revisions.spec.ts (was 4, +1).
- [x] Lint / typecheck / build all green.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T02:55Z | — | `[Spec]` | Loop opened — TMX-3603-agents-err |
| 2026-05-10T03:05Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T03:10Z | `[Code]` | `[Test]` | AgentErrorBanner helper + consumer changes; e2e 5/5 GREEN |
| 2026-05-10T03:15Z | `[Test]` | `[Done]` | Lint / typecheck / build clean |
