# TMX-3604-download-toast — surface download failures via toast (2 sites)

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: Translator clicks "Download translated" → backend rejects (500/AuthZ/segment-still-processing) → button click looks like nothing happened → user thinks the browser blocked the download (popup blocker), reloads, tries again, same result. They never learn the API was throwing.
**Blast radius**: `frontend/components/control_views/JobsView.tsx` AND `frontend/app/workspace/documents/[id]/page.tsx` (one catch each). 1 new e2e test.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — third ticket in mutation-error sweep; reuses sonner toast pattern. Covers TWO sites in one commit since the fix is identical.
- [ ] **G2 Reproduce-failure** — Playwright stub of GET /download-translated → 500 RED before fix.
- [ ] **G3 Completion** — both download sites fire toast.error on failure with the actual server message.

---

## 1. Task

Two parallel `console.error("Download failed:", err)` swallows in JobsView (row download button) and documents/[id] (header download button). Identical fix.

**Addenda**: A3 (silent-fallback class extends to mutations).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.documents.downloadTranslated()` rejects, `toast.error(getErrMessage(err, "Download failed"))` fires (both sites).
- [ ] AC-2: Success path unchanged — Blob → object URL → click → download.
- [ ] AC-3: All existing tests still pass.
- [ ] AC-4: 1 new e2e test stubs GET `/api/documents/:id/download-translated` → 500, opens /workspace/control?tab=jobs, clicks the download icon, asserts toast text visible. (Single test covers the pattern; the documents/[id] site uses the same fix and the same code path through `api.documents.downloadTranslated`.)

**Out of scope**: tools-page rule approve sweep (5 sites, separate ticket); WorkspaceShell focus-refresh fire-and-forget (truly informational, low stakes).

## 3. Design

```ts
} catch (err) {
    toast.error(getErrMessage(err, "Download failed"))
}
```

JobsView already has `toast` imported (TMX-3604-delete-toast); documents/[id] also has `toast` imported (TMX-3604-save-toast). No new imports needed in either file.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/control_views/JobsView.tsx` | Swap console.error → toast.error in the row download handler. |
| `frontend/app/workspace/documents/[id]/page.tsx` | Same swap in the header download button. |
| `frontend/e2e/control-jobs-download.spec.ts` | NEW — 1 test for JobsView site (covers the pattern). |

## 5. Eval / Test

```
$ npm run e2e -- control-jobs-download.spec.ts --workers=1
$ npm run lint && npm run typecheck
```

## 6. Red team

- **One test for two identical sites**: both call `api.documents.downloadTranslated(docId)` and follow the same Blob → object URL → click pattern. The endpoint and error path are identical. A second test would be redundant — same code path through `request()` failure → thrown Error → catch → toast.error. Acceptable per "tests over coverage" — synthetic mirror tests are bloat.
- **Toast vs inline notice**: download is initiated by a button click, not a navigation. The user's eye is on the button area; toast at top-right is the standard pattern. Inline notice next to the button would compete with the button's primary affordance.
- **Browser-native popup-blocker false positives**: a real popup blocker would prevent `a.click()` from triggering download — that's a different failure mode. This fix is for *network/server* failures, where the API rejects before the Blob is in hand. The catch only fires for the latter.
- **Followups**: tools-page rule approve sweep (5 sites) is the last sister ticket in the mutation-error class.

CLEAN.

## 7. Fix

No iterations. RED on first run, GREEN after the two 1-line swaps.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — two identical sites bundled per same-fix-same-test rationale.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: real toast on download failure, both sites.
- [x] e2e: 1/1.
- [x] Lint + typecheck clean.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T04:55Z | — | `[Spec]` | Loop opened — TMX-3604-download-toast |
| 2026-05-10T05:05Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T05:10Z | `[Code]` | `[Test]` | Both sites swapped console.error → toast.error; e2e GREEN |
| 2026-05-10T05:15Z | `[Test]` | `[Done]` | Lint + typecheck clean |
