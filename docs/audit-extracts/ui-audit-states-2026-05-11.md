# Frontend state-handling audit — 2026-05-11

Scope: every page under `frontend/app/workspace/*` and every component in
`frontend/components/ui/*` (plus `frontend/components/control_views/*`) that
consumes async data. Out of scope: the fetch-error and mutation-error sweeps
already closed in fires 22–37 (see `loop-frontend-snapshot-2026-05-10.md`).

This pass looks specifically at the four async states **loading / empty /
error / success**, plus mid-action progress, optimistic vs pessimistic UX,
retry affordances, and stale-data handling on pollers.

---

## Summary

- **No skeleton loaders anywhere.** Every loading path is a centred
  spinner with the literal string "Loading…". For the two heaviest
  reviewer surfaces (`/workspace/jobs`, `/workspace/jobs/[id]`,
  `/workspace/documents/[id]`) this is the biggest UX gap — a regulator
  watching the page sees nothing of the eventual layout until the fetch
  resolves.
- **Success acknowledgement is patchy.** Only two surfaces fire
  `toast.success` today (Black Book correction in
  `tools/page.tsx:207` and the background-translation completion in
  `useTranslationNotifications.ts:47`). HITL segment edits, rule
  approve/reject votes, jobs delete, and the regulator-facing
  `Approve All` button all save silently or are dead code.
- **Pollers degrade silently when stale.** Both `useActivityFeed` and
  `useAgentActivityByJob` resolve to `{ data: null, error }` on a single
  failed poll, dropping all previously rendered events. A regulator
  staring at the dashboard cannot tell "feed is up to date but empty"
  from "feed has been stale for 30 minutes because the backend is
  down". A consecutive-failure threshold + stale-data banner is needed
  before this surface is GxP-defensible.
- **`/workspace/documents/[id]` ships a non-functional `Approve All`
  button.** No `onClick`, no audit event, no toast. This is the worst
  finding in the file: the most visible regulator action on the
  document review page is a no-op.
- **Several empty states are dead ends.** The audit log
  (`/workspace/audit`), Compliance audit list, Recent Documents sidebar
  block, and the Trust Center Glossaries tab (hardcoded mock!) have no
  CTA pointing the user to the action that would populate them.

---

## P0 — regulator-trust gaps

### P0-1. `Approve All` button on document review is a dead no-op

- **File**: `frontend/app/workspace/documents/[id]/page.tsx:377-392`
- **Current state**: The most prominent green CTA in the document
  review header has no `onClick` handler, no disabled state, no
  loading spinner, no toast, no audit-event emission. Clicking does
  nothing. There is also no success acknowledgement because the action
  never fires.
- **What's missing**: A real handler that batch-approves all
  un-blocked segments, writes the per-segment audit events (A1), shows
  inline progress (`Approving 32/120…`), and fires `toast.success` on
  completion with a verification link.
- **Suggested fix**: New backend endpoint
  `POST /api/v1/documents/{id}/approve-all` that emits one audit event
  per segment; on the frontend, wire to the button with optimistic
  in-place status update of segments to `approved`, rollback on error,
  toast on success with `View audit trail` action.
- **Ticket size**: M (backend endpoint + frontend wiring + e2e). This
  is regulator-facing and **must not** be left as a visible-but-dead
  control — even shipping a `disabled` state until the endpoint exists
  is preferable.

### P0-2. Activity feed and agent-activity polls drop history on a single failed poll

- **File**: `frontend/hooks/useActivity.ts:46-56` (`useActivityFeed`)
  and `:99-111` (`useAgentActivityByJob`) and `:147-160`
  (`useAgentActivity`)
- **Current state**: Each successful poll replaces `data` with the new
  array; a failed poll replaces `data` with `null` and the error
  banner shows. The previously rendered events vanish from the DOM.
  No threshold, no staleness indicator. A flaky network or brief 502
  empties the audit-style feed even though the events still exist
  server-side.
- **What's missing**: Two things — (a) retain the last known-good
  `data` on transient failure so the user keeps seeing the events,
  and (b) a "stale since 11:42 — last refresh failed" pill so the
  reviewer knows the events are not up to date. Only after N
  consecutive failures (suggested: 3) should the data be cleared and
  the full error banner replace it.
- **Suggested fix**: Track `consecutiveFailures` and `lastSuccessAt`
  in the hook; keep `data` on first/second failure with a status flag
  the consumer can render as a stale pill; only null-out after N
  failures. Add this once in `useActivity.ts`; consumers
  (`DashboardView`, `WorkspaceJobDetailPage`) just render the new
  flag.
- **Ticket size**: S (hook change + two consumer banner tweaks +
  vitest). Critical for regulator-trust because stale audit signals
  in a green UI is the worst-case state.

### P0-3. HITL segment save lacks success acknowledgement

- **File**: `frontend/app/workspace/documents/[id]/page.tsx:144-161`
- **Current state**: Error path fires `toast.error` (TMX-3604-save-toast,
  closed). Success path closes the editor and refetches segments. No
  toast, no inline "Saved · audit event recorded" chip, no audit-id
  surfaced to the reviewer.
- **What's missing**: HITL corrections are A1 audit events. The
  reviewer needs an unambiguous "this correction landed" signal —
  ideally with the audit-event ID so it is traceable from the toast.
- **Suggested fix**: After `api.segments.update` resolves, fire
  `toast.success("Correction saved — audit event " + audit_id)` with
  a `View audit trail` action. Requires the segment update API to
  return the audit-event ID (it likely already does; if not, that's a
  one-line server change).
- **Ticket size**: S. Aligns with A1 "audit-by-default" — the user
  must see proof the audit event was written.

### P0-4. Trust Center rule approve/reject votes save silently with no acknowledgement and no error path

- **File**: `frontend/app/workspace/trust/page.tsx:99-102`
- **Current state**: `handleVote` calls `api.knowledge.updateRule(...)`
  and immediately `fetchRules()`. No try/catch, no toast on success or
  failure. The reviewer clicks ✓ on a rule; the row eventually
  disappears (or doesn't, on error) with no confirmation. This is the
  twin of the jobs-delete and tools-vote toasts closed in the mutation
  sweep, but on a Black Book regulator-facing surface.
- **What's missing**: Try/catch with `toast.error` on failure,
  `toast.success("Rule approved" | "Rule rejected")` on success, and
  ideally an optimistic UI update (filter the row immediately, roll
  back on error). Same pattern as `JobsView.tsx` delete (which
  already does optimistic-filter + rollback-on-error toast).
- **Ticket size**: S. Same pattern as TMX-3604-tools-toast.

---

## P1 — visible UX gaps a user would notice in week 1

### P1-1. No skeleton loaders anywhere; everything is a centred spinner

- **Files**:
  - `frontend/app/workspace/jobs/page.tsx:185-211` ("Loading
    translation jobs…")
  - `frontend/app/workspace/jobs/[id]/page.tsx:41-48` ("Loading
    job…")
  - `frontend/app/workspace/documents/[id]/page.tsx:193-208`
    ("Loading document…")
  - `frontend/app/workspace/audit/page.tsx:45-52` ("Loading
    activity…")
  - `frontend/components/control_views/DashboardView.tsx:41-48`
    ("Loading dashboard…")
  - `frontend/components/control_views/JobsView.tsx:159` ("Loading
    jobs…")
  - `frontend/components/control_views/ComplianceView.tsx:123`
    ("Loading audit trail…")
- **Current state**: Every loading path replaces the entire page area
  with `<Spinner /> Loading…`. The post-load layout (stats strip,
  filter row, table) flashes in suddenly, causing layout shift and a
  perception of slowness.
- **What's missing**: Skeleton placeholders matching the post-load
  layout (skeleton rows in the jobs table, skeleton stat cards in the
  dashboard, skeleton segment rows in the document review). Grep
  confirms zero `Skeleton` components and zero `animate-pulse`
  containers in app code today. Tailwind's `animate-pulse` is enough;
  no new dep needed.
- **Suggested fix**: New `components/ui/Skeleton.tsx` (10 LOC) and
  per-page skeleton components matching layout. Highest leverage on
  the jobs list and document review page, which are the heaviest and
  most-visited reviewer surfaces.
- **Ticket size**: M (one ticket, ~6 surfaces). Worth pulling out as
  a thematic ticket: `TMX-360x-skeleton-loaders`.

### P1-2. Sidebar "Recent Documents" empty state lacks a CTA

- **File**: `frontend/components/Sidebar.tsx:207-209`
- **Current state**: When the user has zero documents the sidebar
  block reads just "No documents yet" with no link. The user has to
  find the "Upload & Translate" button elsewhere on the page.
- **What's missing**: Inline `Link` to `/workspace/upload` such as
  "Upload your first document →".
- **Suggested fix**: Trivial. Replace the `.sidebar-empty` div with a
  styled `<Link>` to `/workspace/upload`.
- **Ticket size**: XS.

### P1-3. Audit log page has no CTA in its empty state

- **File**: `frontend/app/workspace/audit/page.tsx:77-104`
- **Current state**: When `logs.length === 0` the page shows a clock
  icon, "No activity yet", and a passive sentence. A new user
  reaching this page is told to wait, but isn't pointed at the
  actions that would generate events (upload, translate, edit).
- **What's missing**: A "Upload a document" CTA, or at minimum two
  links: "Upload" and "Run a test translation".
- **Suggested fix**: Add two `<Link>` buttons under the paragraph.
- **Ticket size**: XS.

### P1-4. Compliance / audit-trail list silently swallows fetch errors

- **File**: `frontend/components/control_views/ComplianceView.tsx:88-103`
- **Current state**: `fetchLogs` has `catch { setLogs([]) }`. On a
  500 the user sees the legitimate-empty rendering ("No activity
  recorded · Actions perform will appear here") and has no way to
  distinguish "truly empty" from "API down". Exactly the A3 silent-
  fallback class the fetch-error sweep already closed elsewhere — this
  one was missed.
- **What's missing**: Same pattern as
  `JobsView.tsx`/`AssetsView.tsx` — `setError(getErrMessage(...))`
  and surface an `amber role="status"` banner above the list.
- **Suggested fix**: Identical to TMX-3604-assets-err / TMX-3603-jobs-id-err.
- **Ticket size**: S. **This is the same A3 violation as the closed
  sweep**; flag as a missed surface, not a new pattern.

### P1-5. Workspace dashboard view also swallows the stats fetch error

- **File**: `frontend/components/control_views/DashboardView.tsx:31-39`
- **Current state**: `api.dashboard.stats().catch(() => null)`. The
  page then renders the global "Unable to connect to backend" banner
  when `!stats` but uses `window.location.reload()` as the retry —
  heavy-handed compared to a per-call refetch and loses the user's
  scroll position / open tabs.
- **What's missing**: A targeted `Retry` that just re-calls
  `api.dashboard.stats()` rather than reloading the whole page.
- **Suggested fix**: Hoist the loader into a callback the Retry
  button can re-invoke; keep the rest of the page state.
- **Ticket size**: S.

### P1-6. Upload-page error banner sticky across state transitions

- **File**: `frontend/app/workspace/upload/page.tsx:397-421`,
  cleared only by the X or by `resetFlow`
- **Current state**: A translation timeout writes
  `setError("Translation timed out…")` and demotes state to
  `"uploaded"`. If the user clicks `Translate` again the error banner
  stays visible above the new translating spinner until they X it
  out. Mixing a stale error message with a live progress state is
  confusing in an audit context.
- **What's missing**: Auto-clear `error` at the start of
  `startTranslation` and `handleFileUpload` (the latter already does;
  the former does not for the case where the user retries).
- **Suggested fix**: Add `setError("")` at the top of
  `startTranslation`. One line.
- **Ticket size**: XS.

### P1-7. Translating progress shows generic batch info but not which agent is running

- **File**: `frontend/app/workspace/upload/page.tsx:680-742` (the
  `state === "translating"` block)
- **Current state**: `LiveIsland` and `pipelineSteps` advance through
  5 derived steps (validate → constraints → translate-batches →
  reflexion → finalizing). The text is helpful, but the derived
  state is heuristic (it reads `done === 0`, `done > 0 && done <
  total`, etc.) and does not show which actual agent
  (Translator/Reviewer/Fixer/Auditor) is in flight. The
  `AgentLanes` component renders that info on `/workspace/jobs/[id]`
  but is not used on the upload page during the active translate.
- **What's missing**: Either drop the heuristic
  `LiveIsland` and embed the real `AgentLanes` (which already polls
  via `useAgentActivityByJob`), or keep `LiveIsland` and clearly
  label it as "pipeline progress" not "agent activity".
- **Suggested fix**: Replace the `LiveIsland` block on the upload
  translating-state with the live `AgentLanes` driven by
  `useAgentActivityByJob(document.id)`. Lower entropy: one source of
  truth for agent state.
- **Ticket size**: S–M.

### P1-8. Jobs delete is optimistic but no success acknowledgement

- **File**: `frontend/components/control_views/JobsView.tsx:98-117`
- **Current state**: Optimistic filter (`setJobs(prev =>
  prev.filter(...))`), dialog closes, deletion-log refresh fires.
  Error path has the toast.error (TMX-3604-delete-toast, closed).
  The success path is silent — the row vanishes but the user has no
  toast confirming the audit-trail tombstone was written. For an A9
  audit-bearing path the user should see "Document deleted · audit
  record #abc12345".
- **What's missing**: `toast.success("Document deleted",
  description: "Audit tombstone recorded — view in Deletion Log")`
  with a one-click action to expand the deletion log panel.
- **Suggested fix**: Add the toast after the optimistic filter; if
  the response includes the deletion-record id, surface it.
- **Ticket size**: S.

### P1-9. Document review download button has no progress or success toast

- **File**: `frontend/app/workspace/documents/[id]/page.tsx:324-342`
  and the duplicated logic in `JobsView.tsx:272-291`
- **Current state**: Error path is `toast.error` (closed). Success
  path triggers a synthetic `<a>` click. Large DOCX files can take
  several seconds — no loading state on the button (it does not
  even disable while in flight), no "Download started" toast, no
  click-debounce. A double-click triggers two downloads.
- **What's missing**: Disable the button while the fetch is in
  flight, swap icon to a spinner, fire a non-blocking
  `toast.success("Translated DOCX downloaded")` when the synthetic
  click fires.
- **Suggested fix**: Local `downloading` state per button; trivial.
- **Ticket size**: XS–S (two duplicated sites; ideally extracted
  into a shared hook `useDownloadTranslated`).

---

## P2 — polish

### P2-1. Trust Center Glossaries tab is hardcoded mock data

- **File**: `frontend/app/workspace/trust/page.tsx:189-224`
- **Current state**: The Glossary tab renders three static cards
  (FDA, EMA, TransMax Exclusion List) with hardcoded version and term
  counts. It is not wired to the real `api.knowledge.listGlossaries`
  endpoint that the upload page consumes (and that `AssetsView`
  counts). There is no loading, empty, or error state — it's static
  marketing copy on a regulator surface.
- **What's missing**: Wire to real data with the four canonical
  states; the empty state should CTA to an import flow.
- **Suggested fix**: Mirror the `BlackBookView` pattern with
  `api.knowledge.listGlossaries`. Empty: "No glossaries loaded yet.
  Import a glossary →" linking to `/workspace/tools?tab=import-export`.
- **Ticket size**: M (and a Tier-0 entropy fix — mock data on a
  regulator-trust surface is a broken window).

### P2-2. AssetsView lacks "next action" CTAs in empty states

- **File**: `frontend/components/control_views/AssetsView.tsx:62-80`
- **Current state**: When `ruleCount === 0` (legitimate empty), the
  card just shows `0 · Active in Black Book`. There is no "Add your
  first rule" inline link on the card itself — the user must scan
  down to the action buttons row. Same for `pendingCount` and
  `glossaryCount`.
- **What's missing**: A small "Add rule →" link inside each card
  when the count is zero (and only zero), pointing at the relevant
  tools-page tab.
- **Suggested fix**: Pass an optional `cta?: { label: string; href:
  string }` to `SummaryCard` and render it under the subtitle when
  the value is `"0"`.
- **Ticket size**: XS.

### P2-3. Deletion Log empty state is bare

- **File**: `frontend/components/control_views/JobsView.tsx:328-329`
- **Current state**: "No deletion records found." with no context.
  For a regulator opening this expander, "what does this mean?" is
  not obvious. Could read as "API failed" or "feature disabled".
- **What's missing**: A one-liner: "Documents you delete will appear
  here with the reason, segment count, and tombstone timestamp (A9
  audit policy)."
- **Suggested fix**: Replace the centred italic text with a small
  illustration + context paragraph.
- **Ticket size**: XS.

### P2-4. Stats strip on dashboard renders "—" without explanation when stats fail

- **File**: `frontend/components/control_views/DashboardView.tsx:115-124`
- **Current state**: When `stats` is null (backend down), every
  value in the stats strip is `—`. The amber connection banner at
  the top explains why, but a user who scrolls past it sees six dash
  marks with no context. A11y users reading the strip via screen
  reader hear "Documents dash, Active dash, Quality dash" etc.
- **What's missing**: Either hide the strip entirely when `!stats`,
  or render each value as "Unavailable" with `aria-label`. The
  amber banner is already there; the duplicate dashes are noise.
- **Suggested fix**: Wrap the strip in `{stats ? (...) : null}` or
  show a single "Stats unavailable while backend is offline" row.
- **Ticket size**: XS.

### P2-5. `WorkspaceShell` recent-documents loader has no loading state

- **File**: `frontend/components/WorkspaceShell.tsx:9-40`
- **Current state**: The sidebar's `recentDocuments` starts as `[]`
  and is populated when the fetch resolves. During the loading
  window the sidebar shows "No documents yet", which is also the
  empty state. The user can't tell if it's still loading or
  genuinely empty.
- **What's missing**: A loading flag (`recentDocumentsLoading`) and
  a small skeleton (three pulse-grey rows) while it's true. Same
  P1-1 skeleton story, applied here.
- **Suggested fix**: Three-line state change; render skeletons via
  the P1-1 component.
- **Ticket size**: XS (bundled with P1-1).

### P2-6. Document review preview view has no empty/loading distinction when segments are still being translated

- **File**: `frontend/app/workspace/documents/[id]/page.tsx:864-906`
  (the `viewMode === "preview"` block)
- **Current state**: Segments without `translated_text` render as
  greyed italic source text in brackets. That's the empty cell
  rendering. There is no signal whether the segment is still being
  translated by the pipeline, has failed, or genuinely has no
  translation.
- **What's missing**: A status pill per segment in the preview view
  matching the segment status (pending / translating / blocked /
  approved). The data is in `seg.status` already; just not used in
  the preview renderer.
- **Suggested fix**: Add a small status indicator next to each
  paragraph that lacks `translated_text`.
- **Ticket size**: S.

### P2-7. No retry on transient failures across the app

- **File**: app-wide pattern in `api.*` calls — checked across
  `frontend/app/workspace/**` and `frontend/components/control_views/**`
- **Current state**: All catches go to `toast.error(getErrMessage(...))`
  or a full-page error block. None of them debounce-retry the
  request before surfacing the error. For a flaky network this means
  every transient blip becomes a user-visible error.
- **What's missing**: A thin `withRetry(fn, { attempts: 2, baseMs:
  300 })` helper in `lib/utils.ts` for idempotent GETs only (never
  mutations). Apply selectively on the polling fetches in
  `useActivity.ts` and the initial loads on jobs and document
  review.
- **Suggested fix**: Pure-function helper; wrap selected GETs.
- **Ticket size**: S. Low priority because the toasts and banners
  are already in place; this is a smoothing improvement, not a
  correctness fix.

### P2-8. Translation matrix loading state is non-skeleton text under a sibling spinner

- **File**: `frontend/app/workspace/tools/page.tsx:569`
- **Current state**: While `matrixLoading` is true a plain string
  "Generating parallel translations…" is rendered below the form.
  The button itself shows "Generating Matrix…". No skeleton cards
  for the 5 target languages.
- **What's missing**: Render five `Generating…` placeholder cards
  with each language label, so the user sees the shape of the
  output before the data arrives.
- **Suggested fix**: While `matrixLoading`, render
  `langs.map(l => <SkeletonCard lang={l} />)` matching the result
  grid.
- **Ticket size**: S.

---

## Notes on existing strengths

To avoid the audit reading as relentlessly negative, three things are
notably well-handled and should be the template for the gaps above:

1. `useTranslationNotifications.ts` is the gold standard: background
   poll → `toast.success` with `View` action when the document
   completes; `toast.error` if it reverts to `uploaded`. Mirror this
   pattern for all long-running mutations.
2. `AgentLanes` (`components/ui/AgentLanes.tsx`) is presentation-only
   and accepts an empty array as a real state, with the wrapper
   surface (`WorkspaceJobDetailPage`) rendering the error banner
   above it. Clean separation; reusable elsewhere.
3. The post-sweep error-banner pattern (`role="status"
   aria-label="… failed to load"`) is consistent across the five
   surfaces it landed on. Reuse the exact same banner JSX for P1-4
   (Compliance audit list) to keep the language uniform.

---

## Suggested ticket grouping

| Theme | Findings | Estimated effort |
|---|---|---|
| Approve-All real handler | P0-1 | M (backend + frontend) |
| Poller staleness + last-good retention | P0-2 | S |
| Mutation-success toasts (HITL save, rule vote, jobs delete) | P0-3, P0-4, P1-8 | S |
| Skeleton-loader pass | P1-1, P2-5 | M |
| A3 missed surface (ComplianceView audit fetch) | P1-4 | S |
| Sidebar / audit / glossary / assets CTA polish | P1-2, P1-3, P2-1, P2-2, P2-3 | S |
| Upload-page progress polish | P1-6, P1-7 | S–M |
| Download UX polish | P1-9 | S |
| Misc polish | P2-4, P2-6, P2-7, P2-8 | S |

Total: ~9 tickets, mostly S/XS; two M tickets (P0-1 Approve-All, P1-1
skeletons). Recommended ticket order — P0-2 first (silent stale data
on regulator dashboards is the worst-case state today), then P0-1
(visibly dead button on a regulator surface), then P0-3 / P0-4
together as the mutation-success-toast follow-on to the
TMX-3604 sweep.
