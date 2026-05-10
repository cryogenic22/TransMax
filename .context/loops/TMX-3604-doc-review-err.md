# TMX-3604-doc-review-err — surface fetch errors on document review page

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: If this fails in production, the failure mode is — a reviewer clicks through from JobsView / Sidebar / upload-toast to `/workspace/documents/[id]`. The fetch returns 500. The page renders nothing useful (or the static loading spinner forever, or "Document not found"). Reviewer can't tell if the doc was deleted, the API is down, or something else. Same class as the other four A3 fixes — closes the silent-fallback coverage gap on this surface.
**Blast radius**: `frontend/app/workspace/documents/[id]/page.tsx` (one try/catch reshaped). 1 new e2e test in a new file. No backend, hook, or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — final application of the A3 fix pattern; closes a coverage gap on a regulator-facing surface. (a) needed: yes; (b) <5 callers: 1 file; (c) bundle: negligible; (d) reuses existing pattern; (e) test fails without it: yes.
- [ ] **G2 Reproduce-failure** — Playwright test stubs the failure mode RED before fix.
- [ ] **G3 Completion** — when documents.get fails, the page renders the actual server error message; success path unchanged.

---

## 1. Task

`workspace/documents/[id]/page.tsx:64-117`:

```ts
useEffect(() => {
    const fetchDocument = async () => {
        setLoading(true)
        try {
            const doc = await api.documents.get(docId)
            setDocument(doc)
            const segs = await api.segments.list(docId)
            setSegments(segs)
            // ...compute scorecard from real segments...
        } catch {
            setDocument(null)
        } finally {
            setLoading(false)
        }
    }
    fetchDocument()
}, [docId])
```

The `} catch { setDocument(null) }` silently substitutes `null` for any failure — 500, 404, network, AuthN. The downstream UI shows "Document not found" or a blank page; the user has no way to tell what actually went wrong.

**Addenda**: A3 (no silent fallbacks — primary), A1 (audit-by-default).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.documents.get(docId)` rejects with a 500-flavoured error, the page renders the actual server error message in the error UI — NOT silently rendering an empty state.
- [ ] AC-2: When `api.documents.get(docId)` returns a real 404 ("Document not found"), the page surfaces THAT message — preserving the legitimate not-found case with the actual server detail.
- [ ] AC-3: All existing tests still pass.
- [ ] AC-4: 1 new e2e test in `frontend/e2e/document-review.spec.ts`:
  - "renders real server error when document fetch fails" — stubs documents.get → 500, asserts visible error contains the stub-supplied detail, asserts NOT containing the static fallback.

**Out of scope**:
- Save-segment error surfacing (`console.error("Failed to save", err)` at line 146) — separate ticket; that's a mutation-failure class, not a fetch-failure class.
- The mock-scorecard initial state (line 50) — actually overridden by the useEffect with real data, so not a real "mock-as-real" violation.

## 3. Design

```ts
const [error, setError] = useState<string | null>(null)

useEffect(() => {
    const fetchDocument = async () => {
        setLoading(true)
        setError(null)
        try {
            const doc = await api.documents.get(docId)
            setDocument(doc)
            const segs = await api.segments.list(docId)
            setSegments(segs)
            // ...compute scorecard from real segments...
        } catch (err) {
            setError(getErrMessage(err, "Failed to load document"))
            setDocument(null)
        } finally {
            setLoading(false)
        }
    }
    fetchDocument()
}, [docId])
```

Render-side: distinguish error from "not found" — when `error` is set, render the real message; otherwise (document is null but no error captured, e.g. before fetch completes) keep existing behaviour.

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/documents/[id]/page.tsx` | Add `error` state; capture in catch; render in error UI. |
| `frontend/e2e/document-review.spec.ts` | NEW — 1 test for the failure mode. |

## 5. Eval / Test

```
$ cd frontend && npm run e2e -- document-review.spec.ts --workers=1
$ npm run lint && npm run typecheck && npm run build
```

Expected: 1/1 e2e GREEN.

## 6. Red team

- **`document` shadows the global `window.document`**: this page already uses `document` as a state name (line 41) AND uses `window.document.createElement` (line 167) for CSV export. The shadowing is local-state-only — `window.document` access is correctly qualified. My change reuses the existing `document` state name; safe.
- **Naming collision in active_tasks**: TMX-3604 prefix is used by both `TMX-3604` (Migrate `/design-system` under `/workspace/*` — Done) and now `TMX-3604-doc-review-err`. Same convention bug noted on TMX-3705-glossary-err. Sub-ticket is structurally distinct via the suffix.
- **Build failure was a stale `.next` cache**: typecheck failed because `.next/dev/types/validator.ts` was corrupted from an earlier dev run (had a stray `)` and missing route comment). Cleared `.next/`, re-ran — clean. Not a real regression introduced by my change.
- **Mock-scorecard initial state**: I noted but did NOT touch the `useState<QualityScorecard>({...overall_score: 94, ...})` at line 50. Looking at line 97 more carefully, the useEffect overwrites those defaults with real per-segment computation, so the "94" is never visible to a user — defaults exist only to satisfy the type system during the loading phase. Not an A3 violation.
- **Save-error swallowing**: `console.error("Failed to save:", err)` at line 146 is a separate mutation-error class. Out of scope for this ticket; will return as a follow-up if it surfaces in red team.

CLEAN.

## 7. Fix

One transient: build failed due to stale `.next/dev/types/validator.ts` cache. `rm -rf .next && npm run build` cleaned it. Not code-related.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — fifth and final A3 fix; closes the silent-fallback coverage gap on the workspace document review surface.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: 500/network errors surface the real server message; legitimate not-found preserved.
- [x] e2e: 1/1 in new file.
- [x] Lint / typecheck / build all green (after .next cache clear).
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T03:30Z | — | `[Spec]` | Loop opened — TMX-3604-doc-review-err |
| 2026-05-10T03:35Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T03:40Z | `[Code]` | `[Test]` | error state + render-side conditional landed; e2e GREEN |
| 2026-05-10T03:45Z | `[Test]` | `[Done]` | Stale .next cache cleared; lint/typecheck/build all clean |
