# TMX-3603-jobs-id-err — surface real fetch errors on workspace jobs page

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-09
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement, no API or data shape changes.
**Pre-mortem**: If this fails in production, the failure mode is — a reviewer hits the workspace jobs page during a 500 / network blip, sees "Job not found." (a definitive negative claim), assumes the document was deleted, opens a support ticket, gets pointed at the correct doc that's still right there. Worse: a real 404 on a deleted job blends with a real 500 on a healthy job — the reviewer has no way to tell them apart, can't make a triage decision.
**Blast radius**: `frontend/app/workspace/jobs/[id]/page.tsx` (one fetchData function rewritten, one new state field, one conditional banner). `frontend/e2e/segments-revisions.spec.ts` (1-2 new tests). No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — fixing a real A3 violation on a regulator-facing page. (a) needed: yes — silent fallback on a state machine page; (b) <5 callers: 1 page; (c) bundle: negligible (Promise.allSettled is built-in); (d) reuses existing patterns: yes — same getErrMessage helper already imported; (e) test fails without it: yes (Playwright stub of 500 currently shows "Job not found.").
- [ ] **G2 Reproduce-failure** — Playwright tests stub the failure modes RED before fix.
- [ ] **G3 Completion** — a 500 from `/api/documents/{id}` shows the actual error message; a 500 from `/api/documents/{id}/segments` shows a per-section error banner without losing the doc header.

---

## 1. Task

`fetchData` in `app/workspace/jobs/[id]/page.tsx:68-81` wraps each fetch in a per-promise `.catch(() => null/[])` that silently coerces failures into success-with-empty-data. The page then renders "Job not found." for any failure mode — 404, 500, network timeout, abort, AuthN — without distinguishing them. This is exactly the A3 anti-pattern: a regulated-path surface is substituting a default value where it should fail loud.

This loop changes the fetchData function to use `Promise.allSettled`, distinguishes "couldn't load the doc" (fatal, page is unrecoverable) from "couldn't load the segments" (degraded, page still useful), and surfaces the actual error message in both cases.

**Addenda**: A3 (no silent fallbacks in regulated paths — primary), A1 (audit-by-default — error states are part of the audit trail), A7 (canonical IA — `/workspace/*` is the surface a regulator inspects).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.documents.get(jobId)` rejects with `"API Error: 500"`, the page renders the actual error message ("API Error: 500") in the error UI — NOT the static "Job not found." string.
- [ ] AC-2: When `api.documents.get(jobId)` rejects with a 404-flavored error (`"Document not found"` or `"API Error: 404"`), the page still renders the actual server message — preserving existing UX for the legitimate not-found case.
- [ ] AC-3: When `api.documents.get(jobId)` succeeds but `api.segments.list(jobId)` rejects, the page renders:
  - the doc header (name, status, glossary, language pair) — successfully fetched, no reason to hide
  - a clearly marked error banner where the segments section would otherwise render, with the actual segments-fetch error message
- [ ] AC-4: All existing e2e + vitest still pass.
- [ ] AC-5: 2 new e2e tests in `segments-revisions.spec.ts`:
  - "renders real backend error when document fetch fails" — stubs documents.get → 500, asserts visible error contains "500" or stub-defined message, asserts NOT containing "Job not found."
  - "renders doc header + segments-error banner when only segments fail" — stubs segments → 500, asserts doc name visible AND segments-error banner present.

**Out of scope**:
- Retry button (TMX-3603-jobs-id-retry — defer until reviewers ask for it).
- Optimistic refresh on connection-restore (TMX-3603-jobs-id-online).
- Toast notifications (no toast system in this codebase yet).

## 3. Design

```ts
async function fetchData() {
  setLoading(true)
  setError(null)
  setSegmentsError(null)
  try {
    const [docResult, segsResult] = await Promise.allSettled([
      api.documents.get(jobId),
      api.segments.list(jobId),
    ])
    if (docResult.status === "rejected") {
      setError(getErrMessage(docResult.reason, "Failed to load job"))
      setDoc(null)
      setSegments([])
      return
    }
    setDoc(docResult.value)
    if (segsResult.status === "fulfilled") {
      setSegments(segsResult.value)
    } else {
      setSegmentsError(getErrMessage(segsResult.reason, "Failed to load segments"))
      setSegments([])
    }
  } finally {
    setLoading(false)
  }
}
```

Render-side: where the segments section currently renders, add a conditional:

```tsx
{segmentsError ? (
  <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
    <strong>Couldn't load segments.</strong> {segmentsError}
  </div>
) : (
  /* existing segments render */
)}
```

**Why `role="alert"`**: WCAG 4.1.3 — status messages. Screen readers announce alerts when they appear, which is what we want for an in-page failure that didn't change the URL.

**Why amber not red**: red for fatal errors (full page); amber for degraded sections (doc still works). Status colour ladder.

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/jobs/[id]/page.tsx` | `fetchData` rewritten with Promise.allSettled; new `segmentsError` state; conditional banner where segments render. |
| `frontend/e2e/segments-revisions.spec.ts` | 2 new tests for the failure modes. |

## 5. Eval / Test

```
$ cd frontend && npm run e2e -- segments-revisions.spec.ts
$ npm run test -- RevisionIndicator
$ npm run lint && npm run typecheck && npm run build
```

Expected: e2e 4/4 (was 2/2); vitest unchanged; build green.

## 6. Red team

- **role='alert' collision with Next.js**: my first cut used `role="alert"` for the segments-error banner. Playwright `getByRole("alert")` matched 2 nodes — mine and `__next-route-announcer__` — and strict-mode failed. Fixed by switching to `role="status"` + an explicit `aria-label="Segments failed to load"`. Semantically more correct anyway: the banner is informational, not a critical interruption.
- **react-hooks/set-state-in-effect lint regression**: my Promise.allSettled + branching shape triggered a lint rule about cascading setState in effects, even though all setState happens after `await`. Re-shaped to nested try/catch matching the original code's structure (try outer for doc, try inner for segments). Lint clean. Sequential await costs negligible latency on small JSON payloads.
- **Refetch invariant**: `setError(null)` / `setSegmentsError(null)` resets at the top of fetchData are nice-to-have for a future retry button, but redundant on first mount and they tripped the lint rule. Removed for now; will return when a retry path lands.
- **Failure modes considered**: 401 (still redirected to /login by request()); 404 (server-supplied detail surfaces in error UI — same path as 500 with a more specific message); abort/timeout (caught in request(), error message includes "Request timed out" — surfaces the same way).
- **A11y**: role='status' is polite (announced after current SR utterance); aria-label gives it a distinct accessible name. Visible text is `<strong>` headline + colon + message — readable for both sighted and SR users.

CLEAN — no remaining findings.

## 7. Fix

Two iterations:
1. role='alert' → role='status' + explicit aria-label, after Playwright strict-mode caught the Next.js announcer collision.
2. Promise.allSettled with branching → nested try/catch (sequential await), after lint flagged the branching shape as cascading setState. Same external behaviour, lint clean.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — real A3 fix, surgical scope, no new abstractions.
- [x] G2 reproduce-failure: 2 tests RED with the static "Job not found." behaviour; GREEN after fix.
- [x] G3 completion: doc-fetch 500 surfaces actual server message; segments-fetch 500 renders doc header + alert banner with real message.
- [x] e2e: 4/4 (was 2, +2).
- [x] vitest: 89/89 unchanged.
- [x] Lint / typecheck / build all green.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T01:05Z | — | `[Spec]` | Loop opened — TMX-3603-jobs-id-err |
| 2026-05-10T01:25Z | `[Spec]` | `[Code]` | 2 e2e tests written; ran — confirmed RED |
| 2026-05-10T01:35Z | `[Code]` | `[Test]` | Promise.allSettled + segmentsError state landed; e2e GREEN |
| 2026-05-10T01:45Z | `[Test]` | `[Done]` | role='alert'→'status' fix + nested-try lint fix; 4/4 e2e, lint/typecheck/build clean |
