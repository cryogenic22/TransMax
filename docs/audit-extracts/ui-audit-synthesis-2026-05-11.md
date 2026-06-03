# UI audit synthesis — 2026-05-11

Four parallel agents audited the frontend at `frontend/app/workspace/*` for IA flow, WCAG 2.2 AA accessibility, component-token discipline, and four-state (loading/empty/error/success) handling. Raw reports:

- `ui-audit-ia-flow-2026-05-11.md` — 18 findings (5 P0, 8 P1, 5 P2)
- `ui-audit-a11y-2026-05-11.md` — 22 findings (4 P0, 15 P1, 8 P2)
- `ui-audit-components-2026-05-11.md` — 15 findings (5 P0, 6 P1, 6 P2)
- `ui-audit-states-2026-05-11.md` — 18 findings (4 P0, 9 P1, 7 P2)

**73 findings raw. After dedupe (~6 cross-flagged), ~67 unique.** Synthesized below into a ranked ticket plan for sign-off.

---

## The dominant pattern: TMX-3600's IA migration is half-finished

**Every audit independently surfaces the same root cause.**

`/workspace/jobs/[id]` is the gold-standard surface across all four dimensions:
- IA: agentic, AgentLanes + ProvenanceChip + StatusLifecycle wired
- A11y: clean `role="status"` patterns, dynamic aria-labels (post-TMX-3702-a11y)
- Components: Tailwind-first, consumes TMX-3601 tokens, zero hex literals
- States: doc/segments/agent-activity error story complete

**Six legacy surfaces predate that template** and concentrate the entropy:
- `/workspace/upload` (~995 LOC, 302 inline styles, 260 hex literals, no AgentLanes, dead "Approve All" pattern peer)
- `/workspace/documents/[id]` (918 LOC, 93 inline styles, severity ternaries on hex, dead `Approve All` button)
- `/workspace/jobs` list (parallel to `JobsView`, 665 LOC inline-styled)
- `/workspace/audit` (orphan — not in any nav)
- `/workspace/trust` (orphan parallel "Trust Center" duplicating `/workspace/control`)
- `/workspace/projects/[id]` (pure mock data, hardcoded gradient, dead "Add Document")

**These six files are the source of almost every cross-cut finding.** Sweeping them onto the gold-standard template is the single highest-leverage move.

---

## The four regulator-trust P0s (must-fix before pilot)

These are the audit findings that **break the A1/A3/A6 addenda on regulator-facing surfaces** — fake trust signals, fabricated category scores, silent stale audit data. Fixing these is more important than any visual polish.

### P0-A. Fake live trust signals (A1/A3 violation)

ComplianceView's "Policy Active · NO_STORE / Scrubber · NER_V2_EN / US-EAST-2 / AES-256 / **SHA-256 Chained**" badges are **hardcoded JSX**, no backend query. DashboardView's "Audit Chain · Integrity verified" goes green on any `/dashboard/stats` 200. A regulator reading these sees green lights that have no sensor.

- Sources: IA P0-2, IA P1-8
- **Fix**: Either wire each badge to a real health endpoint, or demote to "Configured policy" copy with explicit "Live verification not yet wired (TMX-31xx audit ledger v2)" note. **The "Integrity verified" claim must not be green-by-default until the audit ledger v2 (TMX-3101) is the live writer.**
- Worst-case failure mode: mock-as-real on a Part 11 compliance surface — the anti-pattern A3 exists to prevent.

### P0-B. Quality Dashboard fabricates per-category scores

`app/workspace/page.tsx:260-263` derives `accuracy / fluency / terminology / formatting` from `confidence > 90 ? 98 : 85` ternaries. The Trusted Translate page renders fake 100% scores per category from a single confidence number.

- Sources: IA P0-4
- **Fix**: Either backend returns real per-category scores via `score_breakdown`, or collapse to confidence-only until deterministic gates wire through.

### P0-C. Activity-feed and agent-activity pollers drop all data on a single failed poll

`hooks/useActivity.ts:46-56` and `:99-111` — every failed poll nulls out `data`. Previously-rendered audit events vanish from the DOM. A regulator staring at the dashboard cannot tell "feed is stable but empty" from "API has been failing for 30 minutes". No staleness pill, no consecutive-failure threshold.

- Sources: States P0-2
- **Fix**: Retain last-known-good `data` on transient failure, track `consecutiveFailures` + `lastSuccessAt`, render a stale-since pill, only null out after N failures.
- Worst-case failure mode: GxP-indefensible — stale audit signals shown in a green UI.

### P0-D. Dead "Approve All" button on regulator-facing document review

`documents/[id]/page.tsx:377-392` — most prominent green CTA on the most regulator-facing surface has no onClick. Clicking does nothing.

- Sources: IA P1-2, States P0-1
- **Fix**: Either remove (XS) or wire to a real bulk-approve endpoint with per-segment audit events (M). Don't leave visible dead.

---

## The legal-a11y P0 (Section 508 hard fail)

### P0-E. Three modals with zero accessibility scaffolding

JobsView delete-confirm, Black Book correction submit (tools), upload translation-estimate dialog — **all three** lack:
- `role="dialog"` + `aria-modal="true"`
- Focus trap (keyboard users can Tab to elements behind the open modal)
- Escape handler
- Focus return on close
- Initial focus management (screen readers don't know the dialog opened)

- Sources: A11y P0-1, P0-2, P0-3
- **Fix**: Wrap all three in a real dialog primitive (radix-ui/react-dialog is the standard; shadcn integrates cleanly). One ticket, three sites.
- **This is a Section 508 hard fail for keyboard-only and screen-reader users.** Regulator-facing pharma SaaS cannot ship with this open.

### P0-F. File-upload input invisible to screen readers

`app/workspace/upload/page.tsx:449-531` drag-drop zone hides `<input type="file">` with `opacity: 0`, no aria-label, no focus indicator.

- Sources: A11y P0-4
- **Fix**: Add `aria-label`, `:focus-within` ring on the drop zone, explicit `<button>Browse</button>` as a discrete focusable target.

---

## The dominant P0: complete the TMX-3600 IA flip

### P0-G. Every job list links to the legacy non-agentic detail surface

`workspace/jobs/page.tsx:605,622` + `JobsView.tsx:305` + `Sidebar.tsx:200` + `upload/page.tsx:863` — all push to `/workspace/documents/[id]`, **bypassing** the agentic `/workspace/jobs/[id]` (AgentLanes + ProvenanceChip + StatusLifecycle).

- Sources: IA P0-1, IA P1-3
- **Fix**: Flip all four link sources to `/workspace/jobs/[id]`. Decide what happens to the legacy doc-review page — either 308-redirect to `/workspace/jobs/[id]?mode=review` (preferred, removes 918 LOC of inline-styled drift) or merge its unique affordances (Quality Scorecard, defect panel) into the canonical detail page.
- **This single fix makes the entire agentic-forward investment visible** to users for the first time.

### P0-H. ProvenanceChip exists on exactly one page

Trusted Translate, upload "done", tools results, legacy documents/[id] all render translations with **zero** provenance affordance — no model name, no prompt version, no glossary version, no audit-event ID.

- Sources: IA P0-3
- **Fix**: Lift `ProvenanceChip` (or `TranslationProvenanceBar`) into every surface that renders `translated_text`. Backend must attach `{model, model_version, prompt_version, glossary_id, audit_event_id}` to translation responses.
- **A6 (qualified-supplier) + A8 (pin every prompt) demand this** on regulator-facing surfaces.

---

## P1 cluster — visible UX gaps a user notices in week 1

The 23 P1 findings collapse into ~8 themed tickets. Roughly ordered by leverage:

1. **Modal+tab a11y semantics** (covers a11y P0-1–3 + P1-1–3 + a11y P1-15 ConfidenceMeter tooltip). One radix migration + one tablist sweep + one tooltip kb fix.
2. **Skeleton loader pass** (states P1-1, P2-5). Zero skeleton components today; every loading path is centred-spinner+text. Highest UX-perception leverage on jobs list and document review.
3. **Mutation-success toast follow-on** to the closed TMX-3604 sweep (states P0-3, P0-4, P1-8): HITL segment save, Trust Center rule approve/reject, jobs delete success — all save silently. Trust/page mutations have no try/catch at all (missed twin of the sweep).
4. **Inline-style → token sweep on the six legacy pages** (components P0-1, P0-2; cross-cuts IA P0-1's flip). The big lift — ~1–2 days mechanical per page.
5. **Status-pill consolidation** (components P0-5): `StatusBadge` + inline `getStatusBadge` + canonical `StatusLifecycle`. Pick the canonical, delete the other two.
6. **Token alignment** (components P0-3 DefectTrace, P0-4 ActivityFeed): swap raw red/amber/violet palettes onto TMX-3601 `--status-*` / `--agent-*` tokens.
7. **Orphan-route deletion** (IA P1-5, P1-7; components P1-2, P1-3): `/workspace/audit`, `/workspace/trust`, `/workspace/projects/[id]` either rolled into Control Tower or deleted.
8. **Form-labelling sweep** (a11y P1-7–11): search box, glossary select, segment-edit textarea, icon-only buttons (download/trash/copy/swap-language/bell). All XS individually; one ticket covers them all.

---

## Recommended ticket plan (signed-off-by-Kapil before any code)

Suggested sprint slicing — ordered by regulator trust first, then user-visible UX, then polish. **No code lands until you pick which to ship.**

| ID (suggested) | Title | Sources | Size | Sprint |
|---|---|---|---|---|
| **TMX-3705-trust-signals** | Demote / wire fake trust badges (A1/A3) | IA P0-2 | M | Sprint 2 P0 |
| **TMX-3706-quality-dashboard-real** | Stop fabricating category scores; show only what backend returns | IA P0-4 | S | Sprint 2 P0 |
| **TMX-3707-poller-stale-pill** | Retain last-good + stale pill on `useActivity` hooks | States P0-2 | S | Sprint 2 P0 |
| **TMX-3708-approve-all-real-or-remove** | Wire or remove the dead Approve All button | IA P1-2 + States P0-1 | S/M | Sprint 2 P0 |
| **TMX-3709-modal-a11y** | Wrap 3 modals in radix-dialog with focus trap + Escape + return-focus | A11y P0-1/2/3 | M | Sprint 2 P0 (legal) |
| **TMX-3710-file-input-a11y** | aria-label + focus-within on drag-drop upload zone | A11y P0-4 | S | Sprint 2 P0 (legal) |
| **TMX-3711-ia-flip** | Flip 4 list-view link sources to `/workspace/jobs/[id]`; 308-redirect or merge legacy doc-review | IA P0-1 + IA P1-3 | M | Sprint 2 P0 |
| **TMX-3712-provenance-everywhere** | Lift ProvenanceChip into every translation surface (A6/A8) | IA P0-3 | M | Sprint 2 P0 |
| **TMX-3713-tab-semantics** | role=tablist + aria-selected + arrow-key nav on 3 tab strips | A11y P1-1/2/3 | S | Sprint 2 P1 |
| **TMX-3714-skeleton-loaders** | New `Skeleton` component + 6 per-page implementations | States P1-1 | M | Sprint 2 P1 |
| **TMX-3715-mutation-success-toasts** | toast.success on save/delete/vote + audit-id surfaced | States P0-3/4 + P1-8 | S | Sprint 2 P1 |
| **TMX-3716-legacy-page-token-sweep-upload** | Migrate `/workspace/upload` onto Tailwind + tokens | Comp P0-1 | M | Sprint 2 P1 |
| **TMX-3717-legacy-page-token-sweep-doc-review** | Migrate `/workspace/documents/[id]` onto Tailwind + tokens (or delete after TMX-3711) | Comp P0-2 | M | Sprint 2 P1 |
| **TMX-3718-status-pill-consolidate** | Pick `StatusLifecycle` canonical; delete `StatusBadge` + inline `getStatusBadge` | Comp P0-5 | M | Sprint 2 P1 |
| **TMX-3719-token-alignment** | DefectTrace + ActivityFeed → status-/agent-tokens | Comp P0-3/4 | S | Sprint 2 P1 |
| **TMX-3720-orphan-route-cleanup** | Delete `/workspace/audit`, `/workspace/trust`, `/workspace/projects/[id]` (or fold) | IA P1-5/7 + Comp P1-2/3 | S | Sprint 2 P1 |
| **TMX-3721-form-labels** | aria-label sweep on search, glossary, segment-edit, icon buttons | A11y P1-7–11 | S | Sprint 2 P1 |
| **TMX-3722-icon-button-labels** | `title=` → `aria-label` on icon-only buttons across app | A11y P1-11 | S | Sprint 2 P1 |
| **TMX-3723-progressbar-semantics** | role=progressbar + aria-value-* on 4 progress bars | A11y P1-14 | S | Sprint 2 P1 |
| **TMX-3724-sidebar-keyboard** | div[role=button] → button; aria-current on nav links | A11y P1-5/6 | S | Sprint 2 P1 |
| **TMX-3725-confidence-tooltip-kb** | Make ConfidenceMeter tooltip keyboard + touch accessible | A11y P1-15 | S | Sprint 2 P1 |
| **TMX-3726-tools-deeplink** | Add ?tab= support to /workspace/tools; fix AssetsView misroutes | IA P0-5 | S | Sprint 2 P1 |
| **TMX-3727-compliance-fetch-err** | Apply TMX-3604-assets-err pattern to ComplianceView audit fetch (missed surface) | States P1-4 | S | Sprint 2 P1 |
| **TMX-3728-trust-glossaries-real** | Wire Trust Center Glossaries tab to real API; kill mock data | States P2-1 | M | Sprint 2 P1 |
| **TMX-3729-agent-lanes-on-upload** | Embed AgentLanes during /workspace/upload translating state | IA P1-1 + States P1-7 | S | Sprint 2 P1 |
| **TMX-3730-polish-pack** | Tab chrome consolidation, fontFamily fix, P2-3 column rename, footer links, heading hierarchy | IA P2-1/2/3/4 + A11y P1-4 + P2-* | S | Sprint 2 P2 |

**26 tickets total**, ~2–3 sprints of focused frontend work to clear the lot. Sprint slicing recommends Sprint 2 P0 first (8 tickets = regulator trust + legal a11y + IA flip), then Sprint 2 P1 (15 tickets), then polish (1 ticket).

---

## What I'd recommend you do next

1. **Read the 4 raw reports** (~30 min total) to confirm the synthesis matches your reading.
2. **Veto any tickets that don't fit** — TMX-3711 (IA flip) is the biggest single piece and depends on whether you want to keep `/workspace/documents/[id]` as a parallel surface or kill it. That's a one-way decision.
3. **Pick which Sprint 2 P0 ticket I start with**. My recommendation in priority order:
   - **TMX-3709 (modal a11y)** — legal blocker, bounded fix, no design judgement calls, ~half day
   - **TMX-3707 (poller stale pill)** — worst regulator-trust failure mode (stale audit signals in a green UI), ~half day
   - **TMX-3705 (trust-signals demote)** — the badge-as-decoration A3 violation, ~1 day
   - **TMX-3711 (IA flip)** — the biggest leverage move (4 link source swaps unblocks the entire agentic surface), depends on legacy-doc-review decision
4. **Optional: spawn a 5th audit** if you want a perspective I missed — performance (re-renders, bundle size) and SEO/structured-data could be a useful round 2.

No commits made this fire — all observation, all gated on your sign-off.
