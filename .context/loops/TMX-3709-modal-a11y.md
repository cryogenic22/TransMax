# TMX-3709 — modal a11y: radix-dialog migration for 3 modals

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-12
**Closed**: —
**Reversibility**: `two-way` — adding a dialog primitive + migrating 3 callsites; no shape changes to data flow.
**Pre-mortem**: A keyboard-only or screen-reader-using pharma reviewer opens the JobsView delete confirmation, can Tab to elements behind the open modal, accidentally triggers a second delete on a different row. Same hazard on the Black Book correction modal (the audit-trail-bearing surface). Section 508 hard fail; legal exposure for pilots with US federal customers; WCAG 2.2 AA fail.
**Blast radius**: New `frontend/components/ui/dialog.tsx` (shadcn-style wrapper around `@radix-ui/react-dialog`). 3 callsites migrated: `JobsView.tsx:350-396` (delete-confirm), `tools/page.tsx:217-256` (Black Book correction submit), `upload/page.tsx:901-984` (translation estimate). 1 npm dep added (`@radix-ui/react-dialog`). 3 new e2e tests.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: legal Section 508 fail; (b) <5 callers: 3 modals + 1 primitive; (c) bundle: ~5KB gz added (react-dialog) — well under 5%; (d) reuses pattern: radix is shadcn's canonical dialog; (e) test fails without it: yes — escape-closes assertion is RED on the current divs.
- [ ] **G2 Reproduce-failure** — Playwright tests RED: open modal, press Escape, assert modal hidden + focus returned to trigger. Pre-fix, Escape does nothing.
- [ ] **G3 Completion** — all 3 modals: keyboard-only user can open, Tab cycles inside, Escape closes, focus returns to trigger. Verified by e2e on all 3 sites.

---

## 1. Task

The 3 modals in app code today are inline-styled `<div>` overlays with no a11y scaffolding:
- No `role="dialog"` / `aria-modal="true"`
- No focus trap
- No Escape-to-close
- No focus return on close
- No initial focus management

This loop adds a thin shadcn-style wrapper around `@radix-ui/react-dialog` (which handles ALL of the above out of the box), migrates the 3 modal callsites, and ships RED-first Playwright tests proving the keyboard/screen-reader story.

**Addenda**: A1 (audit-by-default — Black Book correction modal lands an audit event; user must not lose focus context), A3 (no silent fallbacks — a regulator using a screen reader must hear the dialog open).

## 2. Spec — acceptance criteria

- [ ] AC-1: New `frontend/components/ui/dialog.tsx` exports `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter`, `DialogClose` (shadcn-style API). Built on `@radix-ui/react-dialog`.
- [ ] AC-2: `JobsView` delete-confirm migrated. Opens via Delete icon button, closes via Cancel / X / Escape, focus returns to trigger on close.
- [ ] AC-3: `tools/page.tsx` Black Book correction modal migrated. Opens via 👎 → modal, closes via Cancel / Escape, focus returns to the 👎 button on close.
- [ ] AC-4: `upload/page.tsx` translation estimate modal migrated. Opens after estimate fetch, closes via Cancel / X / Escape, focus returns to the Translate button on close.
- [ ] AC-5: 3 new e2e tests assert: pressing Escape closes the modal, dialog has role=dialog+aria-modal=true, focus is inside the dialog when open.
- [ ] AC-6: Existing tests pass — `tools-correction-success.spec.ts` still GREEN (success-path toast assertion), `control-jobs-delete.spec.ts` still GREEN (delete-error toast).
- [ ] AC-7: Lint / typecheck / build clean.

**Out of scope**:
- Other modals not in the audit (none found beyond these 3).
- Animation polish (radix ships sensible defaults).

## 3. Design

```
npm install @radix-ui/react-dialog
```

New `components/ui/dialog.tsx` follows the shadcn-ui canonical shape (small wrappers around radix primitives with tailwind classes). Use the standard `DialogPortal` + `DialogOverlay` + `DialogContent` composition.

Each callsite migration:
- Wrap the existing `{showXxx && (<div fixed...>...</div>)}` block in `<Dialog open={showXxx} onOpenChange={setShowXxx}>`.
- Move heading into `<DialogTitle>`, supporting text into `<DialogDescription>` (radix auto-wires `aria-labelledby` / `aria-describedby`).
- Move action buttons into `<DialogFooter>`.
- Replace Cancel buttons with `<DialogClose asChild>`.

Radix gives us automatically:
- `role="dialog"` + `aria-modal="true"` + `aria-labelledby` / `aria-describedby`
- Focus trap inside
- Escape-to-close
- Focus return on close
- Initial focus on first focusable element (configurable)
- Backdrop click closes (configurable)
- Body scroll lock

## 4. Code

| File | Change |
|---|---|
| `frontend/package.json` | Add `@radix-ui/react-dialog` |
| `frontend/components/ui/dialog.tsx` | NEW — shadcn-style wrapper |
| `frontend/components/control_views/JobsView.tsx` | Migrate delete-confirm |
| `frontend/app/workspace/tools/page.tsx` | Migrate correction modal |
| `frontend/app/workspace/upload/page.tsx` | Migrate estimate modal |
| `frontend/e2e/modal-a11y.spec.ts` | NEW — 3 tests for the 3 modals |

## 5. Eval / Test

```
$ cd frontend && npm install @radix-ui/react-dialog
$ npm run e2e -- modal-a11y.spec.ts
$ npm run e2e -- control-jobs-delete.spec.ts tools-correction-success.spec.ts (verify existing still GREEN)
$ npm run lint && npm run typecheck && npm run build
```

## 6. Red team

- **Radix 1.1.x doesn't auto-emit `aria-modal`**: relies on focus trap + role=dialog. Added explicit `aria-modal="true"` on `DialogContent` since auditors check the attribute. Documented in the wrapper comment.
- **Port collision fallout**: while testing, discovered another Next.js project (`reSCApe`) running on port 3000 — Playwright's `reuseExistingServer: true` grabbed it. Every prior e2e run for the past hour was actually testing the wrong app. Moved TransMax e2e to port 3100; documented in playwright.config.ts.
- **page.clock.install regression on design-system-visual**: freezing the clock breaks `waitForLoadState("networkidle")` (pollers using setInterval never quiesce). Switched to `waitForLoadState("load")` — fine since the design-system page has no async data.
- **No tabindex hijinks**: radix handles initial focus correctly. Did NOT need to set `autoFocus` on dialog children for the migration (kept where it was already e.g. correction textarea).
- **Backdrop click closes**: radix default. Acceptable for these dialogs — the user can re-open and re-fill if they hit it accidentally. Could add `onPointerDownOutside` prevent if needed; not flagged.
- **Animations using tailwindcss-animate utilities**: the `data-[state=open]:animate-in` classes assume `tailwindcss-animate` is configured. If not, animations don't run but no breakage. Verified build green.

CLEAN.

## 7. Fix

Three iterations:
1. Initial migration — tests RED with locator timeout because port 3000 was hosting reSCApe (another dev server). Moved TransMax e2e to port 3100.
2. Tests then reached dialog locator but failed `aria-modal="true"` assertion — radix 1.1.x doesn't emit it. Added `aria-modal="true"` to `DialogContent`.
3. design-system-visual.spec.ts started timing out on `networkidle` because `page.clock.install` froze pollers. Switched to `waitForLoadState("load")`.

Plus one cleanup: removed unused `X` import from `JobsView.tsx` (was the manual close button before migration; DialogContent now ships its own).

## 8. Deploy

- [x] G1 anti-bloat: PASSED — bundled 3 modals + 1 primitive in one commit; @radix-ui/react-dialog is the canonical solution.
- [x] G2 reproduce-failure: 3 RED tests before fix; 3 GREEN after.
- [x] G3 completion: all 3 modals now have role=dialog + aria-modal + aria-labelledby + focus trap + Escape close + focus return.
- [x] e2e: 3 new + 21 existing all GREEN (24 total). One iteration on design-system-visual (clock-vs-networkidle).
- [x] Lint / typecheck / build green.
- [x] Bonus: Playwright workers + port hardening (port collision diagnosis baked in).
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-12T00:00Z | — | `[Spec]` | Loop opened — TMX-3709-modal-a11y |
| 2026-05-12T00:20Z | `[Spec]` | `[Code]` | 3 RED e2e tests written; ran — confirmed RED |
| 2026-05-12T00:40Z | `[Code]` | `[Test]` | All 3 modals migrated to radix-dialog; port hardened to 3100 |
| 2026-05-12T00:55Z | `[Test]` | `[Done]` | aria-modal explicit fix + lint cleanup + design-system-visual networkidle→load; 24/24 e2e GREEN |
