# UI audit — component cohesion & design-token discipline (2026-05-11)

Scope: `frontend/components/ui/*` and `frontend/app/workspace/*`. Read-only. Quantifying drift, not proposing redesigns.

## Summary

- **Two parallel styling worlds.** New surfaces (`/workspace/jobs/[id]`, `/workspace/control`, `/workspace/trust`, `/workspace`, `/workspace/design-system`) are Tailwind-first and consume tokens. Older surfaces (`/workspace/upload`, `/workspace/documents/[id]`, `/workspace/jobs`, `/workspace/audit`, `/workspace/projects/[id]`, parts of `/workspace/tools`) are inline-style-first with hardcoded hex.
- **Quantified drift.** 302 `style={{…}}` JSX usages and 260 hex literals across 6 workspace pages; 17 hardcoded blue gradients; 45 raw `<button>` elements; only 2 importers of the canonical `<Button>`. UI-component layer is clean (3 inline styles total) — the page layer is the entropy source.
- **Tailwind config is correctly wired** to TMX-3601 tokens (`tailwind.config.ts:60-93`), so `bg-ai-gradient`, `bg-status-*-bg`, `text-agent-*`, `bg-audit-chip` are all available — pages just aren't using them.
- **Three components reinvent the status pill.** `StatusBadge` (raw Tailwind palette, no tokens), `StatusLifecycle` (tokens, canonical), and an inline `getStatusBadge` in `/workspace/jobs/page.tsx`. `StatusLifecycle` is already the canonical one (used by `/workspace/jobs/[id]`, `design-system`, `ReviewSegment`); the other two are drift.
- **Orphan code path.** `RichTextEditor.tsx` is imported nowhere; `QualitySummaryPill` is exported but never used. Both ship code, sanitization rules, and tests for a surface that doesn't exist in the product.

---

## P0 — drift that breaks token discipline (dark-mode + redesign regressions)

### P0-1. `/workspace/upload/page.tsx` is 95% inline-styled with raw hex

- File: `frontend/app/workspace/upload/page.tsx` (the entire ~995-line file). Representative drift:
  - `:296` page bg `"#f8f9fa"`, `:299` hardcoded `'Outfit'` font override
  - `:409` error icon `"#dc2626"`, `:411` swap-button `"#dadce0"` border
  - `:456` dragover blue `"#1a73e8"` and `:459` `"#e8f0fe"` panel bg
  - `:497, :555, :661, :717, :845, :969` six different blue-gradient literals (`"linear-gradient(135deg, #4285f4, #1a73e8)"`, `"linear-gradient(135deg, #e8f0fe, #d2e3fc)"`, etc.)
  - `:904` `position: "fixed"` modal overlay with z-index 200
- **Why it matters:** when dark mode lands (TMX-3601 already ships `.dark` token block), this entire page renders in light colours on a dark shell. Token discipline is breached page-wide, not in spots. Visual snapshot tests cannot ratchet because the snapshot itself codifies the drift.
- **Suggested fix:** mechanical sweep — body `bg-bg-secondary` (or `bg-background`), header `bg-card border-border`, gradients → `bg-ai-gradient` or `.gradient-bg` utility from `globals.css:438-440`, error banner → `bg-status-blocked-bg text-status-blocked-fg`. Pull modal into a small `<Dialog>` primitive (shadcn).
- **Ticket size:** M (1-2 days; the file is long but the sweep is mechanical, plus a visual snapshot refresh).

### P0-2. `/workspace/documents/[id]/page.tsx` redefines severity colours inline (93 `style={{}}` blocks)

- File: `frontend/app/workspace/documents/[id]/page.tsx`
  - `:185-191` `getSeverityColor` returns hex tuples `{ bg: "#fef2f2", border: "#fecaca", text: "#dc2626" }` etc. — directly parallel to `--status-blocked-*` tokens.
  - `:421` `conic-gradient(${score >= 90 ? "#1e8e3e" : score >= 70 ? "#f9ab00" : "#dc2626"} …)` — ternary on hex.
  - `:455` status badge backgrounds branch on three hard-coded greens/reds/yellows; `:527, :535, :801, :806` repeat the same three-bucket ternary for category scores and confidence bars.
- **Why it matters:** the file invents an entire severity palette parallel to TMX-3601 `--status-*`. Any redesign or dark-mode flip has to find and update all 8+ ternary blocks.
- **Suggested fix:** replace the local `getSeverityColor` with a helper that returns Tailwind classes (`bg-status-blocked-bg text-status-blocked-fg`, etc.). Severity → status mapping (`critical → blocked`, `major → translating-amber-variant`, `minor → reviewed`) is a 10-line lookup.
- **Ticket size:** M (1 day, plus visual snapshot refresh and DefectTrace alignment from P0-3).

### P0-3. `DefectTrace` uses raw Tailwind colour palette instead of severity tokens

- File: `frontend/components/ui/DefectTrace.tsx:45-50`
  ```ts
  critical: { ring: "ring-red-300",   bg: "bg-red-50",   fg: "text-red-900",   ... },
  major:    { ring: "ring-amber-300", bg: "bg-amber-50", fg: "text-amber-900", ... },
  ```
- **Why it matters:** TMX-3601 has `--status-blocked-bg/fg` for critical and a built-in `.dark` variant. `bg-red-50` does not flip in dark mode (it's a static palette colour). Component is the canonical defect surface — it should drive the token, not the other way around.
- **Suggested fix:** swap to status tokens (`bg-status-blocked-bg text-status-blocked-fg`, plus an "amber" status token if `--status-translating-*` doesn't read as warning enough — add `--status-warning-*` once and use everywhere).
- **Ticket size:** S (≤ half-day; component-local + test refresh).

### P0-4. `ActivityFeed` actor tints duplicate (and contradict) the `--agent-*` tokens

- File: `frontend/components/ui/ActivityFeed.tsx:23-27`
  ```ts
  const ACTOR_TINT = {
    agent:  "text-violet-600 bg-violet-100 dark:bg-violet-900/30 ...",
    user:   "text-blue-600   bg-blue-100   ...",
    system: "text-emerald-600 bg-emerald-100 ...",
  }
  ```
- **Why it matters:** TMX-3601 defines `--agent-translator: #8b5cf6` (violet), `--agent-reviewer: #2563eb` (blue), `--agent-auditor: #059669` (emerald) — the exact three colours hard-coded here. The token's whole purpose is that "agent identity" is one variable; ActivityFeed forked it. When tokens flip in `.dark`, agent identity drifts.
- **Suggested fix:** for `actor.type === "agent"`, tint by `ev.actor.id` against `--agent-translator|reviewer|fixer|auditor`. For `user` / `system`, introduce two small tokens (`--actor-user-fg/bg`, `--actor-system-fg/bg`) and consume those — same shape as `--audit-chip-*`.
- **Ticket size:** S (component + test).

### P0-5. `StatusBadge` exists but isn't the canonical pill — and uses raw palette

- File: `frontend/components/ui/StatusBadge.tsx:15-21`
- **Why it matters:** Three parallel pill components:
  1. `StatusLifecycle` (`components/ui/StatusLifecycle.tsx`) — token-consuming, used in `/workspace/jobs/[id]`, `design-system`, `ReviewSegment`. **Canonical.**
  2. `StatusBadge` (`components/ui/StatusBadge.tsx`) — `bg-green-100 text-green-800 dark:bg-green-900/30 ...` — used in `JobsView` (control tower) only.
  3. Inline `getStatusBadge` (`app/workspace/jobs/page.tsx:149-173`) — uses hex `{ bg: "#dcfce7", color: "#166534" }` — used in only the legacy jobs page.
- All three describe the same domain concept (job/segment lifecycle). The hex inline one is identical *in value* to `--status-approved-bg/fg`, but won't track the token.
- **Suggested fix:** pick `StatusLifecycle` as canonical (it already handles all six lifecycle states, has labels, has icons, is token-driven). Delete `StatusBadge` and the inline `getStatusBadge`; map the JobsView/jobs-page status strings through the existing `LifecycleStatus` mapping that `/workspace/jobs/[id]` already defines (`DOC_STATUS_TO_LIFECYCLE`).
- **Ticket size:** M (touch 3 call-sites + remove component + delete test; ~half-day).

---

## P1 — inconsistencies a designer would flag in 30 seconds

### P1-1. Two parallel "Jobs" pages with completely different visual language

- Files:
  - `frontend/app/workspace/jobs/page.tsx` — heavy inline styles, hex palette, custom stat cards (lines 325-363 mix Tailwind cards INTO the same file as inline-styled toolbar at 366-432).
  - `frontend/components/control_views/JobsView.tsx` — Tailwind, used by `/workspace/control?tab=jobs`.
- **Why it matters:** the same business object renders with different palette, different status pill, different action affordances depending on which nav entry the user clicked. Both routes are reachable.
- **Suggested fix:** decide which is canonical (`/workspace/control?tab=jobs` is the newer, ratcheted-up version). Redirect `/workspace/jobs` to it, or strip `/workspace/jobs/page.tsx` to a thin wrapper that renders `<JobsView />`. Keeps the `/workspace/jobs/[id]` detail page (which is fine — Tailwind, token-driven).
- **Ticket size:** S (decide + redirect + delete the inline page).

### P1-2. `/workspace/audit/page.tsx` reinvents `ActivityFeed`

- File: `frontend/app/workspace/audit/page.tsx:108-153`
- The page renders a list of audit events with avatar circle, action, target, relative time. **`ActivityFeed` (`components/ui/ActivityFeed.tsx`)** does precisely this, has a `formatRelativeTime` helper, has actor-type theming, and is already tested.
- **Why it matters:** audit log is the regulator-facing surface (A1). Two implementations means two surfaces to validate. The bespoke one uses hex `"#666"` / `"#999"` throughout, which doesn't dark-mode-flip.
- **Suggested fix:** map `AuditLog` → `ActivityEvent` and render `<ActivityFeed items={…} />`. Drop the bespoke list.
- **Ticket size:** S (~half-day).

### P1-3. `/workspace/projects/[id]/page.tsx` is mock data with hardcoded gradients

- File: `frontend/app/workspace/projects/[id]/page.tsx` (52 lines; all inline styled)
  - `:22, :31` two `linear-gradient(135deg, #4285f4, #1a73e8)` literals
  - `:10-17` hardcoded mock `project` object — only "pharma-translations" returns a useful name
  - `:44` ternary on hex `"#dcfce7" / "#fef3c7"` for status pill
- **Why it matters:** this is either a tracer that should be wired to the projects API or dead code shipping to users. Either way, the visual style is out of family.
- **Suggested fix:** confirm whether projects is a real feature (matches `.context/active_tasks.md`?). If real, wire to API + use `Card`, `StatusLifecycle`, `bg-ai-gradient`. If not real, route to a coming-soon empty state under the workspace shell.
- **Ticket size:** XS if delete; S if real (~half-day to wire).

### P1-4. `getSeverityColor` returns hex tuples instead of class names

- File: `frontend/app/workspace/documents/[id]/page.tsx:185-191`
- Specifically the `border: "#fecaca"` hex is used at `:636` to compose a CSS string `border: \`1px solid ${colors.border}\`` — composing tokens via string concatenation.
- **Why it matters:** A8 says don't compose prompts from runtime variables; the same hygiene applies to design tokens. Any redesign breaks this.
- **Suggested fix:** return `{ bgClass, textClass, borderClass, Icon }` objects. Pair with P0-2.
- **Ticket size:** XS (folded into P0-2).

### P1-5. Stat cards inside the jobs page mix two systems

- File: `frontend/app/workspace/jobs/page.tsx:325-363`
- The 4 stat cards use Tailwind (`className="bg-white rounded-xl p-5 border border-slate-200"`), but the rest of the same file is inline-styled. The comment at `:323` admits this: `"Re-implementing compact stats cards to ensure file completeness"`.
- **Why it matters:** the boundary between the two systems is *inside one component*. New devs reading this don't know which to follow.
- **Suggested fix:** subsumed by P1-1 (delete the page in favour of `<JobsView />`).
- **Ticket size:** folded into P1-1.

### P1-6. Three sticky/fixed elements compete in `/workspace/upload`

- File: `frontend/app/workspace/upload/page.tsx`
  - `:306` page header `position: "sticky", top: 0, zIndex: 100`
  - `:904` estimate dialog `position: "fixed", inset: 0, zIndex: 200`
  - Also renders `<LiveIsland />` (`components/ui/live-island.tsx:26`) which is `fixed bottom-8 left-1/2 z-50`
- The workspace shell (`components/Sidebar.tsx` + `TopNavigation.tsx`) adds its own sticky chrome.
- **Why it matters:** on viewports < 900px, the LiveIsland (450px wide expanded) sits on top of the workspace sidebar (260px). The sticky page header competes with the TopNavigation. Z-index stack `50/100/200` was picked ad-hoc.
- **Suggested fix:** centralise z-index in a single token block in `globals.css` (`--z-shell: 30; --z-sticky: 40; --z-live-island: 50; --z-modal: 100`). Move LiveIsland out of `fixed` and into a portal targeted at the workspace shell's "live region" slot (in `WorkspaceShell.tsx`).
- **Ticket size:** S (~half-day) — but only worth doing as part of P0-1's sweep.

---

## P2 — polish / DRY opportunities

### P2-1. Two card primitives + an inline `.card` class

- Files: `frontend/components/ui/card.tsx` (shadcn-style, `bg-card text-card-foreground`), `frontend/components/ui/GlassCard.tsx` (`rounded-2xl bg-white dark:bg-slate-950/50`), and `.card` / `.card-static` in `globals.css:277-297`.
- `GlassCard` is misnamed — it doesn't have backdrop-filter or any glass effect (the `.glass` utility at `globals.css:442-445` does; `GlassCard` doesn't import it). It's just a thicker-rounded card.
- **Why it matters:** API divergence — `Card` for shadcn-style content blocks, `GlassCard` for "wider radius marketing surface", `.card` CSS class for legacy. Reviewers don't know which to pick.
- **Suggested fix:** keep `Card` (canonical, shadcn). Rename `GlassCard` to its actual function (e.g. `<Card variant="elevated">`) or fold into `Card` with a prop. Remove `.card` / `.card-static` from `globals.css` after sweeping the 3 remaining call-sites.
- **Ticket size:** M (rename touches `AuditTimeline`, `trust/page.tsx`, `tools/page.tsx`; ~half-day).

### P2-2. `RichTextEditor.tsx` is orphaned

- File: `frontend/components/ui/RichTextEditor.tsx`
- `grep` for `RichTextEditor` returns only the component itself and two `lib/sanitizeHtml.ts` comments. No JSX importer. Pulls Tiptap (`@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-table*`) into the bundle for nothing.
- **Why it matters:** bundle size + entropy. Tests/lint pass for a surface that doesn't exist.
- **Suggested fix:** confirm with the product owner — if no near-term consumer, delete the file + uninstall tiptap deps. If a consumer is queued, file a ticket and reference it from the file header.
- **Ticket size:** XS (delete) or skip.

### P2-3. `QualitySummaryPill` is exported but unused

- File: `frontend/components/ui/QualityDashboard.tsx:46-66`
- Only `QualityDashboard` itself is consumed (in `/workspace/page.tsx`). `QualitySummaryPill` exports but has no caller.
- **Why it matters:** dead code on a shipped path. Also: `QualityDashboard` defines `getStatus` once and the entire RAG-status logic again inline at `:88-101` — same logic, two copies.
- **Suggested fix:** delete `QualitySummaryPill` (or wire it into the segments view if that was the intent) and consolidate the duplicated `getStatus` block.
- **Ticket size:** XS.

### P2-4. Three "raw palette" zones in non-orphan components

- Files:
  - `ConfidenceMeter.tsx:24-27` — `text-red-600 / text-emerald-700 / text-teal-700 / text-amber-700` ternary on score buckets
  - `live-island.tsx:102-107` — `text-blue-400 / text-purple-400 / text-emerald-400 / text-orange-400 / text-green-500` for pipeline steps
  - `QualityDashboard.tsx:38-42, 104-108` — `bg-emerald-50 / bg-amber-50 / bg-rose-50` defined twice in the same file (RAG palette)
- **Why it matters:** the four pipeline-step colours in LiveIsland map cleanly to the four `--agent-*` tokens (`ingest → reviewer-blue`, `pii → auditor-emerald-or-translator-violet`, `translate → translator-violet`, `gate → fixer-amber`). Using the tokens means LiveIsland inherits dark-mode for free.
- **Suggested fix:** introduce a small `confidenceBand(score)` helper that returns status-token classes, applied in `ConfidenceMeter` + `QualityDashboard`. Switch LiveIsland icons to `--agent-*` tokens.
- **Ticket size:** S (~half-day).

### P2-5. Canonical `<Button>` has 2 importers; 45 raw `<button>` in workspace pages

- Files: 45 occurrences of `<button` in `/workspace/**/*.tsx`, vs imports of `Button` only in `components/DocumentUpload.tsx` and `components/review/ReviewSegment.tsx`.
- **Why it matters:** every raw button reimplements padding / radius / focus-ring / disabled state. Disabled states are inconsistent (some pages set `opacity` ad-hoc, some change `background` to `#e0e0e0`).
- **Suggested fix:** canonical is `<Button>` (`components/ui/button.tsx`) — already has variants/sizes/asChild. Migrate page-by-page as part of the inline-style sweeps. Don't rebuild it. The `.btn`/`.btn-primary` CSS in `globals.css:243-274` is a separate parallel button system — consider deleting after sweep.
- **Ticket size:** M, but only as part of broader inline-style sweep (P0-1, P0-2).

### P2-6. `:globals.css` has hardcoded marketing gradient that doesn't reference tokens

- File: `frontend/app/globals.css:249, 432, 438` — `linear-gradient(135deg, #0070bf 0%, #007af0 50%, #00aff0 100%)` repeated three times for `.btn-primary`, `.gradient-text`, `.gradient-bg`. These hexes (`#0070bf` etc.) are not defined as variables and don't match the `--brand-*` palette (`#1a73e8` etc.) defined above.
- **Why it matters:** the design system advertises Google-blue (`--brand-500: #1a73e8`) but the marketing gradient uses a different blue family. Page-level code (`upload`, `jobs`, `documents`) uses **a third** gradient family (`#4285f4 → #1a73e8`).
- **Suggested fix:** add `--gradient-primary-from/via/to` tokens; have `.btn-primary` / `.gradient-text` / `.gradient-bg` consume them; let page-level sweeps drop in the same utility.
- **Ticket size:** XS for the token + utility; the sweep is P0-1/P0-2.

---

## Cross-cutting observations (no ticket, just signal)

- The `/workspace/jobs/[id]` page is the **gold standard** in this codebase: composable Tailwind, consumes `StatusLifecycle` + `ProvenanceChip` + `AgentLanes`, no inline styles, no hex literals, proper degraded-state banners. Use it as the template every other page should migrate toward.
- `/workspace/design-system` is the showcase but its tokens-in-use list is incomplete. After the P0 sweep, every primitive and status pill should appear there with all six lifecycle states.
- Tailwind config (`tailwind.config.ts:60-93`) is well-wired. The blocker is *not* infrastructure — it's six page files that predate the token block.
- The `.dark` block in `globals.css:176-209` is unreferenced by any toggle today. Until the toggle ships (Loop 17.5), token violations are invisible. The audit ratchet should land **before** the toggle, or the first dark-mode user sees a kaleidoscope.
