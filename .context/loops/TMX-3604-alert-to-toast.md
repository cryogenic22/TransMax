# TMX-3604-alert-to-toast — replace blocking alert() with sonner toasts

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: Reviewer submits a Black Book correction, the modal closes, then a blocking `alert("Feedback submitted to Black Book!")` window pops up — feels antiquated, breaks keyboard flow on the page (alert intercepts focus until dismissed), inconsistent with every other success/failure surface that uses sonner toasts. Same file's failure path now uses toast.error (TMX-3604-tools-toast); the success path's alert is now an outlier.
**Blast radius**: `frontend/app/workspace/tools/page.tsx` (1 line), `frontend/app/workspace/page.tsx` (2 lines including a stale console.error). 1 new e2e test. No backend, hook, or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — completes the toast-pattern consistency arc started by the mutation-error sweep. Removes UX-blocking artifacts.
- [ ] **G2 Reproduce-failure** — Playwright assertion of the toast-success-text visibility RED before fix (alert() still fires; toast.success never called).
- [ ] **G3 Completion** — Black Book correction success surfaces via toast.success; workspace translate failure surfaces via toast.error (no blocking alert).

---

## 1. Task

Two `alert()` sites in app code:

| File | Line | Class |
|---|---|---|
| `frontend/app/workspace/tools/page.tsx` | 203 | success — `alert("Feedback submitted to Black Book!")` |
| `frontend/app/workspace/page.tsx` | 62 | failure — `alert("Translation failed. Please try again.")` paired with stale `console.error(e)` |

The tools-page success migration is the test target; the workspace translate-fail migration follows the same pattern as TMX-3604-tools-toast et al.

**Addenda**: A1 (Black Book corrections feed the audit chain — confirmation UX matters), no specific addendum on alert-vs-toast but matches the project's sonner-everywhere convention.

## 2. Spec — acceptance criteria

- [ ] AC-1: tools/page.tsx — success path of handleSubmitCorrection calls `toast.success("Feedback submitted to Black Book!")` instead of `alert(...)`.
- [ ] AC-2: workspace/page.tsx — failure path of handleTranslate calls `toast.error(getErrMessage(e, "Translation failed. Please try again."))` and the stale `console.error(e)` is removed (toast already surfaces the message).
- [ ] AC-3: 1 new e2e test stubs POST /api/knowledge/feedback → 200, opens the Black Book correction modal, submits, asserts the toast text is visible AND no alert() dialog fires (Playwright `page.on('dialog')` listener counts dialogs).
- [ ] AC-4: All existing tests still pass.

**Out of scope**:
- backend `alert()` cleanup (none — JS/TS only).
- toast.success styling overrides (sonner's defaults are fine).

## 3. Design

```ts
// tools/page.tsx
} catch (...)
setShowModal(false)
toast.success("Feedback submitted to Black Book!")  // was: alert(...)
```

```ts
// workspace/page.tsx
} catch (e) {
    toast.error(getErrMessage(e, "Translation failed. Please try again."))
}
```

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/tools/page.tsx` | alert(...) → toast.success(...). |
| `frontend/app/workspace/page.tsx` | Add toast + getErrMessage imports; alert(...) + console.error(e) → toast.error(...). |
| `frontend/e2e/tools-correction-success.spec.ts` | NEW — 1 test for the Black Book success path (no alert; toast text visible). |

## 5. Eval / Test

```
$ npm run e2e -- tools-correction-success.spec.ts --workers=1
$ npm run lint && npm run typecheck
```

## 6. Red team

- **Anti-alert assertion**: the test sets `page.on('dialog', dialog => dialog.dismiss())` and counts dialog firings. Combined with the toast text assertion, this catches both the regression "still firing alert()" AND a partial regression "alert removed but toast not added" cleanly.
- **Locator collision**: first attempt used `getByRole('button', { name: /issue/i })` which collided with another "Critical Issues" element on the page. Tightened to `button[title="Report issue"]` — the unique title attribute on the FeedbackControls button.
- **Side-effect: stale console.error removed in workspace/page.tsx**: the original handler had BOTH `console.error(e)` AND `alert(...)`. The console.error is now redundant because toast.error renders the message visibly; deleted to avoid double-logging the same failure.
- **getErrMessage fallback**: workspace translate fail uses `getErrMessage(err, "Translation failed. Please try again.")` — preserves the exact original alert string as the fallback when the server returns no detail.
- **Sweep arc complete**: sonner is now the single channel for both success and failure UX in app code. No remaining alert() sites.

CLEAN.

## 7. Fix

One iteration: e2e selector strict-mode collision on `getByRole('button', { name: /issue/i })`. Replaced with `button[title="Report issue"]`. RED → GREEN.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — completes the sonner-everywhere arc.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: success toast visible, no alert dialog fires.
- [x] e2e: 1/1.
- [x] Lint + typecheck clean.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T05:55Z | — | `[Spec]` | Loop opened — TMX-3604-alert-to-toast |
| 2026-05-10T06:00Z | `[Spec]` | `[Code]` | RED test added; first attempt blocked on selector collision |
| 2026-05-10T06:05Z | `[Code]` | `[Test]` | Selector tightened to title attribute; alert→toast.success + alert→toast.error landed; e2e GREEN |
| 2026-05-10T06:10Z | `[Test]` | `[Done]` | Lint + typecheck clean |
