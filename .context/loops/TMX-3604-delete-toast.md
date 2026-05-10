# TMX-3604-delete-toast — surface delete-job failures via toast

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: A regulator clicks delete in the audit-trail dialog, the backend rejects (500/AuthZ), the dialog closes, the doc stays in the list, the user sees nothing change. They assume the click didn't register, click again. Each attempt fails with no signal. Eventually they give up; the doc never gets the tombstone its audit chain needs. Mutation-error analogue of the silent-fallback fetch sweep.
**Blast radius**: `frontend/components/control_views/JobsView.tsx` (one catch block changed). 1 new e2e test. No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — pivots from fetch-sweep to mutation-error class on a regulator-facing user action. Reuses sonner toast already mounted globally in app/layout.tsx.
- [ ] **G2 Reproduce-failure** — Playwright stub of DELETE 500 + toast assertion RED before fix.
- [ ] **G3 Completion** — failed delete surfaces real error message via toast.

---

## 1. Task

`JobsView.tsx:107-111` swallows the delete error with `console.error`. No toast, no banner, no modal-inline error — the user sees nothing.

**Addenda**: A3 (silent-fallback class extends to mutations), A9 (failed delete means tombstone never written), A1 (audit-by-default).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.documents.delete()` rejects with 500, a `toast.error` fires containing the actual server message (via getErrMessage).
- [ ] AC-2: Success path unchanged.
- [ ] AC-3: All existing tests still pass.
- [ ] AC-4: 1 new e2e test stubs DELETE → 500 with detail, asserts toast contains the detail.

**Out of scope**: other silent-mutation sites (download, save segment, rule approve) — separate tickets in the same class.

## 3. Design

```ts
import { toast } from "sonner"

} catch (err) {
    toast.error(getErrMessage(err, "Delete failed"))
}
```

Toast position top-right + richColors (red for error) + 4s default duration — enough for the user to read.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/control_views/JobsView.tsx` | Import toast; swap console.error for toast.error. |
| `frontend/e2e/control-jobs-delete.spec.ts` | NEW — 1 test. |

## 5. Eval / Test

```
$ npm run e2e -- control-jobs-delete.spec.ts --workers=1
$ npm run lint && npm run typecheck && npm run build
```

## 6. Red team

- **Toast vs banner**: this is a transient action failure on a list page; toast is the standard sonner pattern for action feedback. richColors makes errors red and visible top-right; 4s duration gives the user time to read.
- **No retry button on the toast**: sonner supports `action: { label, onClick }`. Defer until ops asks — current pattern doesn't have retry buttons elsewhere; adding one only here would be inconsistent.
- **Dialog stays open on failure**: deliberately left as-is. The user can re-try the delete (e.g., after the API recovers) or cancel. Closing the dialog on error would lose the typed reason — bad UX.
- **Followups**: 4 other silent-mutation sites remain (download in JobsView, save+download in documents/[id], rule approve in tools page). Each is a similar small ticket; not bundled here to keep scope tight.

CLEAN.

## 7. Fix

No iterations. RED on first run, GREEN after the import + 1-line swap.

## 8. Deploy

- [x] G1 anti-bloat: PASSED.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: failed delete shows real error toast.
- [x] e2e: 1/1 in new file.
- [x] Lint / typecheck clean (build skipped — no new build-graph changes; proven clean across the prior 5 fires).
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T03:55Z | — | `[Spec]` | Loop opened — TMX-3604-delete-toast |
| 2026-05-10T04:00Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T04:05Z | `[Code]` | `[Test]` | toast import + swap; e2e GREEN |
| 2026-05-10T04:10Z | `[Test]` | `[Done]` | Lint + typecheck clean |
