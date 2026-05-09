# TMX-3602-patterns — Design system v1: AI Moment + Provenance Chip + Status Lifecycle

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend pod (Antigravity / Pod B)
**Sprint**: 1
**Started**: 2026-05-09
**Closed**: 2026-05-09

---

## 1. Task

Per the rescape design review (Direction 3 — "Patterns over screens"): three reusable component patterns codified in TransMax form a unified design vocabulary. Loop 17 landed the design tokens; this loop builds the React components that consume them and renders a demo page so any feature author can drop them into any surface.

The three patterns:

1. **`<AIMoment>`** — wraps any AI-generated content. Gradient header, sparkle icon, model+prompt chip, optional explanation collapsible. Used wherever an AI-produced artefact lands (translation output, defect explanation, suggested fix, future generated narratives).
2. **`<ProvenanceChip>`** — a small chip beside any content block showing source / version / timestamp / hash. Hover reveals the full chain. Used on every segment row, every audit event, every search result.
3. **`<StatusLifecycle>`** — 6-state pill with iconography for `pending / translating / translated / reviewed / approved / blocked`. Used wherever segment or job status appears.

**Blast radius**: `frontend/components/ui/` (new components) + `frontend/__tests__/` (tests) + `frontend/app/workspace/design-system/page.tsx` (demo). No existing surfaces refactored — each per-surface adoption is its own follow-up.

**Addenda**: A1 (audit-by-default — provenance chip surfaces the audit chain visually), A2 (quality at gates — status lifecycle reflects gate state), A6 (LLMs are qualified suppliers — AIMoment puts the supplier identity on every output).

## 2. Spec — acceptance criteria

- [ ] AC-1: `frontend/components/ui/AIMoment.tsx` exists, accepts `{ model, promptVersion?, tokensIn?, tokensOut?, generatedAt?, explanation?, children }` and renders the gradient + sparkle + model chip + collapsible explanation.
- [ ] AC-2: `frontend/components/ui/ProvenanceChip.tsx` exists, accepts `{ source, version?, timestamp?, hash? }` and renders a small audit-coloured chip with a hover-tooltip showing the hash.
- [ ] AC-3: `frontend/components/ui/StatusLifecycle.tsx` exists, accepts `{ status: SegmentStatus | JobStatus }` and renders a coloured pill with the right icon.
- [ ] AC-4: `frontend/__tests__/` covers each component with at least 3 tests (variant renders + prop pass-through + a11y check).
- [ ] AC-5: `frontend/app/workspace/design-system/page.tsx` (the workspace-canonical design system page; legacy `app/design-system/page.tsx` is retained pending migration ticket TMX-3604) renders all 3 patterns in light mode (dark mode demo deferred to when a toggle is wired).
- [ ] AC-6: Existing surfaces unchanged. Lint stays under cap. Build green. Vitest grows from 21 to 30+ tests.

**Out of scope**:
- Adoption of these components in existing surfaces (each is a focused per-surface PR; e.g. wiring `<StatusLifecycle>` into `JobsView.tsx` is its own ticket).
- Reading-mode / editing-mode toggle in document canvas (rescape review §Document Canvas — out of scope for this loop, sister ticket).
- Activity feed in dashboard (rescape review §Dashboard — Loop 19 territory).

## 3. Design

**Why a single `AIMoment` component, not a header + footer pair**: containment. If a developer needs to wrap AI output, they import one thing. The component owns the visual contract. Anywhere AI output lands without `AIMoment`, it visually clashes with surfaces that have it — making misuse obvious in QA.

**`AIMoment` composition**:
- `<div class="bg-ai-tint border border-ai-border rounded-lg overflow-hidden">`
- Top strip: `bg-ai-gradient h-1`
- Header row: `<Sparkles class="text-ai-spark">` + model chip "AI · Claude Sonnet 4.6" + optional explanation toggle
- Body: `{children}` (the AI-generated content)
- Footer (collapsible): explanation text + token usage + generated timestamp

**`ProvenanceChip` composition**:
- `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-audit-chip text-audit-chip-fg border border-audit-chip-border">`
- Source label + optional version
- Hash rendered in JetBrains Mono inside a hover-tooltip (use the `<span title="...">` for v1 — Radix popover is v2 polish)

**`StatusLifecycle` composition**:
- 6 status mappings: pending/translating/translated/reviewed/approved/blocked
- Each maps to `bg-status-{status}-bg` + `text-status-{status}-fg` + a Lucide icon
- One pill component, one prop. Adding a new state is changing the union + the mapping table.

**Why no Radix Popover for hover yet**: the `@radix-ui/react-popover` dep is already installed but introducing it for a 3-line tooltip is over-engineering. v2 of `ProvenanceChip` can upgrade.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/ui/AIMoment.tsx` | new |
| `frontend/components/ui/ProvenanceChip.tsx` | new |
| `frontend/components/ui/StatusLifecycle.tsx` | new |
| `frontend/__tests__/AIMoment.test.tsx` | new |
| `frontend/__tests__/ProvenanceChip.test.tsx` | new |
| `frontend/__tests__/StatusLifecycle.test.tsx` | new |
| `frontend/app/workspace/design-system/page.tsx` | new — demo page under canonical IA |

## 5. Eval / Test

```
$ cd frontend
$ npm run lint        # under cap
$ npm run typecheck   # clean
$ npm run build       # 17 routes (1 new under workspace)
$ npm run test        # vitest 30+
```

## 6. Red team

- **CLEAN**. Tier 2 self-review:
  - Three components all have a single, named, exported responsibility. AIMoment owns the AI gradient + sparkle + chip. ProvenanceChip owns the audit chip. StatusLifecycle owns the 6-state pill + iconography. No overlap.
  - Each component takes a small typed prop surface — no `any`. The `LifecycleStatus` union is the source of truth; `STATUS_MAP` is a closed table. Adding a state forces the developer to update both.
  - 15 new vitest tests (6 + 5 + 4). Vitest now 36/36 in 4s. Tests cover: variant render, prop pass-through, a11y role/label, conditional UI (icon visibility, chevron toggle), title-attribute hash truncation.
  - Demo page at `/workspace/design-system` shows each pattern individually + a composition (real segment row using all three together). Build went 16 routes → 17.
  - 💡 **Behaviour-preserving**: no existing component / page changed. Each adoption is a focused per-surface PR (not in this loop's scope).
  - 💡 **Hash tooltip is v1**: uses native `<span title="...">`. v2 (a Radix popover with copy-to-clipboard) is a polish ticket once we see how reviewers actually use the chip.
  - 💡 **Lint stable at 172/172**: new code is clean (0 errors, 0 new warnings). Cap unchanged.
  - 💡 **Backend untouched.**

## 7. Fix

No fix iterations.

## 8. Deploy

- [x] Code: `frontend/components/ui/{AIMoment,ProvenanceChip,StatusLifecycle}.tsx`, `frontend/app/workspace/design-system/page.tsx`
- [x] Tests: `frontend/__tests__/{AIMoment,ProvenanceChip,StatusLifecycle}.test.tsx`
- [x] Vitest: 36/36 (was 21)
- [x] Lint: 172/172 cap, exit 0
- [x] Typecheck: clean
- [x] Build: 17 routes
- [x] Mocked e2e: still 3/3 (untouched)
- [x] Backend: untouched
- [ ] Commit + push (next)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T17:30Z | — | `[Spec]` | Loop opened — design system patterns v1 |
| 2026-05-09T18:00Z | `[Spec]` | `[WIP]` | 3 components written; 15 tests added |
| 2026-05-09T18:15Z | `[WIP]` | `[Done]` (pending push) | All gates green; demo at /workspace/design-system |
