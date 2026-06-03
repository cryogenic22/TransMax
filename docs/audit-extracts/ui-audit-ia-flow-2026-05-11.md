# UI audit — IA & user-flow — 2026-05-11

Auditor: read-only sweep of `frontend/app/workspace/*` + landing/login. Scope: IA consistency, dead ends, primary-action clarity, agentic-forward signals, trust-center surfacing, A7 (`/workspace/*`) drift. Error/toast sweep is OUT OF SCOPE (covered in `loop-frontend-snapshot-2026-05-10.md`).

---

## Summary

- **Two parallel job-detail surfaces exist.** `/workspace/jobs/[id]` is the canonical agentic-forward detail page (AgentLanes + ProvenanceChip + StatusLifecycle), but every list that links to a job — sidebar "Recent Documents", `/workspace/jobs` table, `/workspace/control?tab=jobs` table, upload "View Details" — pushes to the legacy `/workspace/documents/[id]`. The agentic detail surface is effectively orphaned. This is the single highest-impact IA finding and a direct A7 violation.
- **Audit-chain / policy-snapshot / model-version chrome is missing from every surface where a translation appears**, except `/workspace/jobs/[id]`. `ProvenanceChip` is used in exactly one page. Workspace landing, upload "done" state, tools page results, and the legacy documents/[id] all render translations with no provenance affordance — a regulator landing there cannot tell what model / prompt / glossary produced the text.
- **Trust signals are decorative, not live.** ComplianceView's "Policy Active: NO_STORE", "Scrubber Active: NER_V2_EN", "US-EAST-2", "AES-256", "SHA-256 Chained" are hardcoded JSX. DashboardView's "Audit Chain · Integrity verified" is `status="ok"` if `/dashboard/stats` returns 200. A pharma reviewer reading these badges would assume they reflect live posture; they don't. This is an A3 violation in spirit (silent default) on a regulator-facing surface.
- **Tab patterns are inconsistent across pages**: `/workspace/control` uses styled pill-buttons with `?tab=` URL state; `/workspace/jobs/[id]` uses underlined tabs with `?mode=`; `/workspace/tools` uses pill-buttons with local React state only (no URL persistence) and ignores `?tab=` deep links written by AssetsView. Three chrome variants, three state strategies.
- **Orphan / mock-data pages remain in the tree**: `/workspace/audit` (no nav link in), `/workspace/trust` (parallel "Trust Center" to "Control Tower"), `/workspace/projects/[id]` (hardcoded fake project + dead "Add Document" button). These either need wiring or removal.

---

## P0 findings — must-fix before pilot (block trust)

### P0-1. Job-detail rendering routes to legacy surface, bypassing AgentLanes/Provenance

- **Where**: `frontend/app/workspace/jobs/page.tsx:605,622`; `frontend/components/control_views/JobsView.tsx:305`; `frontend/components/Sidebar.tsx:200`; `frontend/app/workspace/upload/page.tsx:863`.
- **Why it matters**: The canonical `/workspace/jobs/[id]` (which has the four-agent swim lanes, ProvenanceChip, lifecycle status) is unreachable through normal navigation — users land at `/workspace/documents/[id]`, a 918-LOC parallel surface with no agent lanes, no provenance, no audit chain affordance. The agentic-forward signal investment is invisible to the end user.
- **Suggested fix**: Replace all four `/workspace/documents/{id}` Link/router calls with `/workspace/jobs/{id}` and inline a 308 redirect in `documents/[id]/page.tsx` pointing to `/workspace/jobs/[id]` while the document-review-specific affordances (Quality Scorecard, segment editor, defect panel) are folded into a `?mode=review` view on the jobs detail page.
- **Size**: **M** (route flip is XS; deciding how to merge documents/[id]'s scorecard panel into jobs/[id] is M and may want its own ticket).

### P0-2. Compliance / privacy / audit chrome is hardcoded, not bound to live posture

- **Where**: `frontend/components/control_views/ComplianceView.tsx:30-86` (entire `PrivacyCards` block); `frontend/components/control_views/DashboardView.tsx:104-108` (System Health rows fake-derived from `stats != null`); `frontend/app/workspace/trust/page.tsx:189-282`.
- **Why it matters**: A pharma auditor / regulator opening Control Tower / Compliance & Audit sees five trust signals (zero-retention, PII redaction, residency, encryption, chain immutability) presented as real-time status pills. None of them query backend state. "Audit Chain · Integrity verified · SHA-256 Chained" is a particularly load-bearing claim that is fabricated chrome until the v3.0 ledger v2 ships (CLAUDE.md A1). A reviewer signing off on this surface is being shown a green light that has no sensor behind it — failure mode equivalent to the mock-translation-as-real anti-pattern A3 was written to prevent.
- **Suggested fix**: Either (a) wire each badge to a real backend health endpoint (`/api/health/policy`, `/api/audit/chain/verify`, etc.) and render `unknown` / `unverified` until the backend confirms, or (b) demote the badges to "Configured policy" copy with an explicit "Live verification not yet wired (TMX-3xxx)" note. Until the audit-ledger-v2 lands per CLAUDE.md A1, the "Integrity verified" claim must not be hardcoded green.
- **Size**: **M** (per-badge wiring across three components; or **S** if the demote-to-config-copy path is taken as a stopgap).

### P0-3. Provenance / model / prompt-version absent on every surface that renders a translation except jobs/[id]

- **Where**: `frontend/app/workspace/page.tsx:191-225` (Trusted Translate result panel); `frontend/app/workspace/upload/page.tsx:791-815` (done-state segment preview); `frontend/app/workspace/documents/[id]/page.tsx:864-906` (Preview view); `frontend/app/workspace/tools/page.tsx` (audit/back-trans/matrix outputs).
- **Why it matters**: CLAUDE.md A6 + A8: every LLM call is a qualified-supplier interaction and every prompt has a pinned version. The UI must reflect that wherever translated text appears — model name, prompt version, glossary version, audit-event ID. None of these surfaces render any of it. A reviewer copy-pasting from Trusted Translate or downloading from upload cannot answer "which model / which prompt produced this?" — exactly the regulator-asked question A6/A8 exist to defend against.
- **Suggested fix**: Lift `ProvenanceChip` (or a sibling `TranslationProvenanceBar`) into every surface that renders `translated_text`. Backend should attach `{model, model_version, prompt_version, glossary_id, audit_event_id}` to every segment / translation response; the chip renders them as a compact pill row.
- **Size**: **M** (frontend surface lift is S; the backend contract addition for surfaces that don't currently return provenance is M-ish — Trusted Translate's `api.tools.universal` does not return it today).

### P0-4. Quality Dashboard fabricates category scores when API omits them

- **Where**: `frontend/app/workspace/page.tsx:260-263` — `accuracy: (confidence ?? 0) > 90 ? 98 : 85, fluency: ... 95 : 88, terminology: ... 100 : 92, formatting: 100`.
- **Why it matters**: This is the exact A3 anti-pattern the mutation/fetch sweep just closed elsewhere: silently substitute a default on a regulator-facing surface. A reviewer sees "Terminology 100%" / "Formatting 100%" derived from a hardcoded ternary on `confidence`, not from any backend signal. Worse, the values look plausible enough to be mistaken for real.
- **Suggested fix**: Either (a) backend must return real per-category scores via `score_breakdown` and the UI renders only what's present (greyed "not measured" otherwise), or (b) collapse QualityDashboard's four bars down to just `confidence` until the deterministic gate per-category scores are wired through.
- **Size**: **S**.

### P0-5. Tools/Knowledge surface has no deep-link state and is misrouted to from Assets

- **Where**: `frontend/app/workspace/tools/page.tsx:37` defines `'audit' | 'backtrans' | 'matrix'` purely as React state, ignores `?tab=`. `frontend/components/control_views/AssetsView.tsx:92,99` push to `/workspace/tools?tab=glossaries` and `/workspace/tools?tab=import-export` — both query strings the tools page never reads, and neither tab exists. `frontend/components/Sidebar.tsx:122-139` defines two sidebar entries ("Black Book" and "Toolkit") that both link to `/workspace/tools` with no tab discrimination.
- **Why it matters**: Two sidebar entries land at the same default tab. Two Trust Center buttons claim to land on glossary / import-export panels that don't exist. The user clicks "View Glossaries" and lands on Quality Auditor. Broken affordance, broken trust.
- **Suggested fix**: Either (a) add `glossaries` + `import-export` tabs to `tools/page.tsx` and wire `?tab=` deep-linking, or (b) point AssetsView's two buttons at `/workspace/control?tab=assets` (where they already are) / a future `/workspace/glossaries` and collapse Sidebar's Black-Book/Toolkit dupes to one.
- **Size**: **S** (route fix + sidebar dedupe). **M** if the missing tabs are actually built out.

---

## P1 findings — should-fix (visible UX gaps)

### P1-1. AgentLanes is absent on the surface that needs it most: `/workspace/upload`

- **Where**: `frontend/app/workspace/upload/page.tsx:680-743` (translating state).
- **Why it matters**: The upload page is the primary place a user kicks off async work and watches it run, but the translating-state UI shows only a generic progress bar + LiveIsland pipeline stages — no swim lanes, no four-agent identity. CLAUDE.md positioning is "multi-agent activity visible"; here it's reduced to a percent bar.
- **Suggested fix**: Render `AgentLanes` below LiveIsland in the translating state, fed by the same `useAgentActivityByJob(document.id)` hook used by jobs/[id].
- **Size**: **S**.

### P1-2. Legacy documents/[id] "Approve All" button has no handler

- **Where**: `frontend/app/workspace/documents/[id]/page.tsx:377-392`.
- **Why it matters**: The most visually prominent green CTA on a regulator-facing surface fires nothing. Either it's vestigial or the most important workflow primitive on the page is unimplemented. Either way it's a credibility-breaker on a demo path.
- **Suggested fix**: Wire to `api.segments.bulkApprove(docId)` (creating the endpoint if absent) with a confirmation modal that captures reviewer attestation, OR remove the button. Don't leave a stub.
- **Size**: **S** (remove) / **M** (wire with attestation modal — preferred per A1).

### P1-3. Upload "done" state pushes to legacy doc-review surface

- **Where**: `frontend/app/workspace/upload/page.tsx:863` — `router.push('/workspace/documents/{id}')`.
- **Why it matters**: The user finishes their first translation, clicks "View Details", and lands on the legacy surface (no AgentLanes, no provenance) — the worst-possible first impression of where the actual agentic work lives. Same root cause as P0-1, but worth ticketing separately because the "first-translation" demo path is high-leverage.
- **Suggested fix**: Change to `/workspace/jobs/{id}`. (Part of P0-1's batched fix.)
- **Size**: **XS**.

### P1-4. Two near-duplicate Jobs list implementations diverging

- **Where**: `frontend/app/workspace/jobs/page.tsx` (665 LOC, inline-styled) and `frontend/components/control_views/JobsView.tsx` (used at `/workspace/control?tab=jobs`).
- **Why it matters**: Same `EnrichedJob` shape, same `api.documents.list()` traversal, two implementations. JobsView has delete + deletion-log affordances; the standalone /jobs page doesn't. Long-term the standalone page is redundant once Control Tower is the canonical operator view.
- **Suggested fix**: Either redirect `/workspace/jobs` → `/workspace/control?tab=jobs` (and delete the standalone), or factor the EnrichedJob transform + table into a `<JobsTable>` component used by both. Don't carry two for v3.
- **Size**: **M**.

### P1-5. `/workspace/audit` and `/workspace/trust` are orphan parallel surfaces

- **Where**: `frontend/app/workspace/audit/page.tsx:1-165`, `frontend/app/workspace/trust/page.tsx:1-285`.
- **Why it matters**: Neither is reachable from `Sidebar.tsx` or `TopNavigation.tsx`. `/workspace/trust` calls itself "Trust Center" and contains its own Black Book / Glossaries / Privacy tabs that overlap with Control Tower (the actual "unified command center"). `/workspace/audit` shows raw audit logs with the same `formatTime` bug pattern as `app/agents/graph.py:149` (no UTC ISO). Two surfaces a session never reaches but the routes are crawlable.
- **Suggested fix**: Delete `/workspace/audit` (its content is duplicated in `ComplianceView.AuditLogList`) and `/workspace/trust` (its content is duplicated in `ComplianceView.PrivacyCards` + `AssetsView`). Or, if either has unique content, lift it into `/workspace/control` as a new tab.
- **Size**: **S**.

### P1-6. Sidebar "Recent Documents" status dot has no legend and uses raw backend status strings

- **Where**: `frontend/components/Sidebar.tsx:202-205` — `<span className="sidebar-status-dot {doc.status}" />`. Status strings flow through unmapped (`uploaded`, `processing`, `translated`, `in_review`, `approved`, `blocked`).
- **Why it matters**: Five colour dots with no key. A reviewer scanning the sidebar can't tell `processing` from `in_review` from `blocked`. The StatusLifecycle component already exists and has the right vocabulary.
- **Suggested fix**: Replace the raw dot with a tiny `<StatusLifecycle compact />` variant, OR add a tooltip showing the human-readable lifecycle label.
- **Size**: **S**.

### P1-7. `/workspace/projects/[id]` is a pure mock page

- **Where**: `frontend/app/workspace/projects/[id]/page.tsx:1-52`.
- **Why it matters**: Hardcoded `documents: [{id: "mounjaro-pil", ...}, {id: "ozempic-spc", ...}]`, dead "Add Document" button with no handler. The route is reachable by anyone who guesses or saves the URL; it's a credibility hole on any demo.
- **Suggested fix**: Either build real project grouping (likely M+, out of scope here) or delete the route entirely. Per CLAUDE.md anti-bloat gate it should not exist until projects are a real concept.
- **Size**: **XS** to delete.

### P1-8. Hardcoded model name and language defaults

- **Where**: `frontend/app/workspace/upload/page.tsx:948` — `Model: {estimate.model || "gpt-4o-mini"}`; `frontend/app/workspace/documents/[id]/page.tsx:280,689,885` — `doc.target_language || "de"`.
- **Why it matters**: A6 (qualified-supplier model name must come from the JobConfigSnapshot, never a UI default). A reviewer reading "Model: gpt-4o-mini" when the backend returned nothing is being shown a fabricated supplier identity. Target-language defaulting to German is benign-looking but ships the same anti-pattern A3 calls out — fail loud, don't substitute.
- **Suggested fix**: Render `Model: —` / `Target: —` when the field is missing; surface a small inline warning. Never default supplier identity on a regulator-facing surface.
- **Size**: **XS**.

---

## P2 findings — nice-to-have (polish)

### P2-1. Inconsistent tab chrome across pages

- **Where**: `/workspace/control/page.tsx:42-75` (pill buttons in a grouped container); `/workspace/jobs/[id]/page.tsx:185-209` (underlined tabs); `/workspace/tools/page.tsx:73-92` (pill buttons but no container); `/workspace/trust/page.tsx:24-61` (underlined); `/workspace/page.tsx:94-106` (underlined). Three visual languages for the same affordance.
- **Why it matters**: A user navigating between pages re-learns the tab affordance each time. Token-discipline drift relative to TMX-3601.
- **Suggested fix**: Promote one of these (recommend the `/workspace/control` styled-button container) into a shared `<TabBar>` component in `components/ui/`. Adopt across the four surfaces.
- **Size**: **M**.

### P2-2. Inline `fontFamily` references a font that isn't loaded

- **Where**: `frontend/app/workspace/upload/page.tsx:299`, `frontend/app/workspace/documents/[id]/page.tsx:235` use `'Outfit', ...`. `frontend/app/globals.css:1` imports DM Sans + JetBrains Mono only. `frontend/components/TopNavigation.tsx:69` claims `'Google Sans', 'Outfit', ...`.
- **Why it matters**: Inconsistent font stacks per page that all fall back to the OS default → visual page-to-page break and a small reproducibility hit on snapshot tests.
- **Suggested fix**: Pick the canonical body font in `globals.css` (DM Sans is already imported), remove inline `fontFamily` from these three files, let Tailwind / globals carry the chrome.
- **Size**: **XS**.

### P2-3. Jobs-list column labelled "Risk Score" renders `ConfidenceMeter` labelled "Trust"

- **Where**: `frontend/app/workspace/jobs/page.tsx:496` (header) vs `frontend/components/ui/ConfidenceMeter.tsx:35` (chip says "Trust"). Same column also labelled differently in `JobsView.tsx`.
- **Why it matters**: Three names for the same value (Risk Score / Trust / Confidence) across two list views and a chip. A reviewer flips between the standalone /jobs page and Control Tower's /jobs tab and sees inconsistent vocabulary.
- **Suggested fix**: Pick one term (recommend "Confidence" per backend `confidence_score` field) and use it everywhere. Update the meter's "Trust" label too.
- **Size**: **XS**.

### P2-4. Landing-page footer has placeholder `href="#"` links

- **Where**: `frontend/app/page.tsx:283-292` — Documentation, API Reference, Support, Contact, Privacy all `href="#"`.
- **Why it matters**: Pre-pilot landing-page polish; clicking any of these scrolls to top with no destination. For a regulated product, the missing "Privacy" link in particular reads as careless.
- **Suggested fix**: Either remove the columns or point each at a real anchor / external doc.
- **Size**: **XS**.

### P2-5. `/workspace/audit` formatTime ignores timezone

- **Where**: `frontend/app/workspace/audit/page.tsx:34-43`.
- **Why it matters**: Same root cause as the well-known `app/agents/graph.py:149` bug — `new Date(dateStr)` parses a backend timestamp without explicit UTC handling, then formats with the browser locale. Audit timestamps shown to a reviewer in Sydney won't match what a regulator in the US sees. (Note: page is orphan per P1-5, so this is only material if the page is kept.)
- **Suggested fix**: Folded into P1-5's "delete or fold into ComplianceView" decision. If kept, switch to a UTC-explicit `toISOString().replace('T', ' ').slice(0, 19)` style render.
- **Size**: **XS** (only if the page survives).

---

## Findings ledger

| ID | Severity | Size | Title |
|---|---|---|---|
| P0-1 | P0 | M | Job-detail rendering routes to legacy surface, bypassing AgentLanes/Provenance |
| P0-2 | P0 | M | Compliance / privacy / audit chrome is hardcoded, not bound to live posture |
| P0-3 | P0 | M | Provenance / model / prompt-version absent on every surface that renders a translation except jobs/[id] |
| P0-4 | P0 | S | Quality Dashboard fabricates category scores when API omits them |
| P0-5 | P0 | S | Tools/Knowledge surface has no deep-link state and is misrouted to from Assets |
| P1-1 | P1 | S | AgentLanes absent on `/workspace/upload` translating state |
| P1-2 | P1 | S/M | Legacy documents/[id] "Approve All" button has no handler |
| P1-3 | P1 | XS | Upload "done" state pushes to legacy doc-review surface |
| P1-4 | P1 | M | Two near-duplicate Jobs list implementations diverging |
| P1-5 | P1 | S | `/workspace/audit` and `/workspace/trust` are orphan parallel surfaces |
| P1-6 | P1 | S | Sidebar "Recent Documents" status dot has no legend |
| P1-7 | P1 | XS | `/workspace/projects/[id]` is a pure mock page |
| P1-8 | P1 | XS | Hardcoded model name and language defaults |
| P2-1 | P2 | M | Inconsistent tab chrome across pages |
| P2-2 | P2 | XS | Inline `fontFamily` references a font that isn't loaded |
| P2-3 | P2 | XS | Jobs-list column "Risk Score" / chip "Trust" / field `confidence_score` — three names |
| P2-4 | P2 | XS | Landing-page footer has placeholder `href="#"` links |
| P2-5 | P2 | XS | `/workspace/audit` formatTime ignores timezone (only if the page survives) |

Total: 18 findings (5 P0, 8 P1, 5 P2). The P0 cluster is dominated by one underlying issue: TMX-3600's IA migration shipped the redirect plumbing and the new `/workspace/jobs/[id]` agentic surface, but did not flip the in-app navigation. The legacy `/workspace/documents/[id]` is reachable from every list view, and most of the agentic-forward investment (AgentLanes, ProvenanceChip, live provenance affordances) is consequently invisible to the user.
