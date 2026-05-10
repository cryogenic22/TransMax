# TMX-3604-save-toast — surface segment-save failures via toast

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: A reviewer/translator opens a document, clicks a segment to edit, types a HITL correction (this becomes part of the audit chain via the `reason` parameter), clicks Save. PATCH /api/segments/:id rejects (500/400/AuthZ). Save button stops spinning, edit mode stays active, no toast, no inline error. Reviewer assumes the save worked (button done), navigates away. The correction was never persisted; the segment still shows the bad translation; the audit chain never recorded the attempt.
**Blast radius**: `frontend/app/workspace/documents/[id]/page.tsx` (one catch block changed). 1 new e2e test. No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — second ticket in mutation-error sweep; reuses sonner toast pattern from TMX-3604-delete-toast.
- [ ] **G2 Reproduce-failure** — Playwright stub of PATCH 500 + toast assertion RED before fix.
- [ ] **G3 Completion** — failed segment save surfaces real error message via toast.

---

## 1. Task

`documents/[id]/page.tsx:151-155`:

```ts
} catch (err) {
    console.error("Failed to save:", err)
} finally {
    setSaving(false)
}
```

User clicks Save → spinner appears → spinner disappears → no other feedback. Edit mode persists (because `setEditingSegmentId(null)` is in the success path, not the catch). User has no signal whether the API call succeeded or failed.

**Addenda**: A3 (silent-fallback class extends to mutations), A1 (audit-by-default — HITL corrections are audit events), A5 (stable IDs end-to-end — segment edits feed the audit chain).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.segments.update()` rejects with 500, a `toast.error` fires containing the actual server message via getErrMessage.
- [ ] AC-2: Edit mode persists on failure (existing behaviour — reviewer can retry without re-typing).
- [ ] AC-3: Success path unchanged.
- [ ] AC-4: 1 new e2e test stubs PATCH segments/:id → 500, asserts toast text visible.

**Out of scope**: download-translated failures (separate sister ticket); inline-banner inside the edit area (toast is fine for transient failures).

## 3. Design

```ts
import { toast } from "sonner"

} catch (err) {
    toast.error(getErrMessage(err, "Failed to save segment"))
}
```

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/documents/[id]/page.tsx` | Add toast import; swap console.error for toast.error. |
| `frontend/e2e/document-segment-save.spec.ts` | NEW — 1 test. |

## 5. Eval / Test

```
$ npm run e2e -- document-segment-save.spec.ts --workers=1
$ npm run lint && npm run typecheck
```

## 6. Red team

- **Edit mode persists on failure** — deliberate. Closing edit mode would lose the typed correction. Reviewer can retry directly.
- **Toast vs inline-banner**: same call as TMX-3604-delete-toast — transient action failure on a list-of-segments view; toast is the standard sonner pattern. Inline-banner above the textarea would help if the user has scrolled the segment off-screen at the moment they clicked save, but that's a rare failure mode.
- **Persistence semantics**: failed save means the prior translated_text and confidence_score are still in state (no React mutation happens before await). Re-clicking save re-attempts cleanly. Cancel still works.
- **Followups**: 3 sister tickets remain in the mutation-error class — JobsView download fail, documents/[id] download fail, tools-page rule approve fail.

CLEAN.

## 7. Fix

No iterations. RED on first run, GREEN after import + 1-line swap.

## 8. Deploy

- [x] G1 anti-bloat: PASSED.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: real toast visible on save failure.
- [x] e2e: 1/1 in new file.
- [x] Lint + typecheck clean.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T04:25Z | — | `[Spec]` | Loop opened — TMX-3604-save-toast |
| 2026-05-10T04:35Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T04:40Z | `[Code]` | `[Test]` | toast import + 1-line swap; e2e GREEN |
| 2026-05-10T04:45Z | `[Test]` | `[Done]` | Lint + typecheck clean |
