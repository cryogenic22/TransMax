# TMX-3705-glossary-err — surface glossary fetch failures in upload form

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: If this fails in production, the failure mode is — a translator uploads a regulated document, intending to apply the validated glossary v3.2 (mandatory for compliance). The glossary selector doesn't render because `listGlossaries()` failed silently; they can't tell whether (a) no glossaries exist, (b) target-language filter ruled them all out, or (c) the API is just down. They proceed without the glossary. The reviewer downstream has no way to detect the mistake until QA catches it.
**Blast radius**: `frontend/app/workspace/upload/page.tsx` (one effect changed, one new state field, one inline notice). New `frontend/e2e/upload-glossary.spec.ts` (1 test). No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — third application of the same A3 fix pattern (TMX-3603-jobs-id-err, TMX-3604-assets-err, this). (a) needed: yes — translator-blocking workflow gap on a regulated path; (b) <5 callers: 1 file; (c) bundle: negligible; (d) reuses pattern: yes — same role='status' + getErrMessage; (e) test fails without it: yes (Playwright stub of 500 currently hides selector silently).
- [ ] **G2 Reproduce-failure** — Playwright test stubs the failure mode RED before fix.
- [ ] **G3 Completion** — when listGlossaries fails, an inline notice with the real error message renders where the selector would be; when it succeeds (empty array OR with data), no notice renders.

---

## 1. Task

`upload/page.tsx:67-70`:

```ts
api.knowledge.listGlossaries().then(data => {
    setGlossaries(...)
}).catch(() => {})
```

The selector at line 578 only mounts when `glossaries.length > 0`. So a fetch failure leaves the selector hidden — indistinguishable from a server with zero glossaries. A translator who must apply a specific glossary for compliance reasons has no signal that they should retry or contact ops.

**Addenda**: A3 (no silent fallbacks in regulated paths — primary), A1 (audit-by-default — glossary application is part of the audit chain).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.knowledge.listGlossaries()` rejects, the upload form renders an inline notice (not a full-page banner) where the selector would otherwise mount, with text containing the actual server error message.
- [ ] AC-2: The notice uses `role="status"` + `aria-label="Glossary list failed to load"` (matching the pattern from TMX-3603-jobs-id-err and TMX-3604-assets-err).
- [ ] AC-3: When `listGlossaries()` succeeds with an empty array, no notice renders (legitimate empty state — preserves existing behaviour).
- [ ] AC-4: When `listGlossaries()` succeeds with one or more active glossaries, the selector renders as today (no behaviour change to the happy path).
- [ ] AC-5: All existing tests still pass.
- [ ] AC-6: 1 new e2e test in `frontend/e2e/upload-glossary.spec.ts`:
  - "renders glossary-error notice when listGlossaries fails" — stubs the endpoint to 500, navigates to /workspace/upload, asserts notice visible with the stub-supplied detail message.

**Out of scope**:
- "No active glossaries — upload one in Trust Center" empty-state hint (separate UX concern; deserves its own ticket).
- Retry button (defer until translators ask).
- The other `.catch(() => {})` in `WorkspaceShell.tsx` — that's a focus-refresh of the recent-docs sidebar, an ergonomic nicety; degraded = stale list, not blocking.

## 3. Design

```ts
const [glossaryError, setGlossaryError] = useState<string | null>(null)

useEffect(() => {
    api.knowledge.listGlossaries()
        .then(data => {
            setGlossaries((data as ...).filter(g => g.is_active))
        })
        .catch(err => {
            setGlossaryError(getErrMessage(err, "Failed to load glossaries"))
        })
}, [])
```

Render-side, near where the selector currently lives (post-form, pre-translate-button):

```tsx
{glossaryError ? (
    <div role="status" aria-label="Glossary list failed to load" className="...amber...">
        <strong>Couldn't load glossaries.</strong> {glossaryError}
    </div>
) : glossaries.length > 0 ? (
    /* existing selector */
) : null}
```

Inline notice (small, in-form), not a full banner — the upload form already has lots of chrome and a top-of-form error state for upload failures.

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/upload/page.tsx` | `.catch()` captures the error; inline notice rendered conditionally where the selector would mount. |
| `frontend/e2e/upload-glossary.spec.ts` | NEW — 1 test for the failure mode. |

## 5. Eval / Test

```
$ cd frontend && npm run e2e -- upload-glossary.spec.ts --workers=1
$ npm run lint && npm run typecheck && npm run build
```

Expected: 1/1 e2e GREEN, lint/typecheck/build clean.

## 6. Red team

- **Naming collision**: ticket name conflicts with parent TMX-3705 (Pipeline / file-type sniffing). Sub-ticket is structurally distinct (`TMX-3705-glossary-err`) but the prefix is misleading — this is NOT a child of file-type sniffing, it's an upload-form UX ticket. Convention-bug not blocking; documented in worksheet so future readers don't think this is Pipeline work.
- **Notice placement first attempt was wrong**: I put the notice inside the post-upload conditional block. Test failed because translator hits the page in idle state. Hoisted to a state-agnostic position (above the IDLE-state JSX) so it renders from landing — which is the right UX anyway: translator should know the catalog is broken BEFORE wasting time uploading.
- **role='status' polite, not assertive**: glossary fetch failure is informational on a workflow page, not a hard error preventing the user from continuing (they CAN still upload without a glossary). Polite notice matches the severity. Aria-label distinguishes from any other status messages on the page.
- **Empty success vs. failure**: still not handling "successful fetch but zero glossaries" with a positive empty-state message. That's a separate UX gap (out of scope per spec).
- **Stub-test fragility**: the test asserts on the stub-supplied detail text. If the upload page later displays glossaryError differently (e.g. via toast), the test would break. Acceptable — that's exactly what we want a regression test to catch.

CLEAN.

## 7. Fix

One iteration: notice was placed in the post-upload conditional block, invisible on initial page load. Hoisted out to a state-agnostic position before the IDLE-state JSX. Test went RED → GREEN.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — third application of the same pattern, surgical scope.
- [x] G2 reproduce-failure: RED before fix; GREEN after.
- [x] G3 completion: idle-state translator now sees the failure on landing, with the actual server message.
- [x] e2e: 1/1 in new file.
- [x] Lint / typecheck / build all green.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T02:25Z | — | `[Spec]` | Loop opened — TMX-3705-glossary-err |
| 2026-05-10T02:35Z | `[Spec]` | `[Code]` | Test written; ran — RED as expected |
| 2026-05-10T02:42Z | `[Code]` | `[Test]` | Notice landed in post-upload block; RED on idle-state navigation |
| 2026-05-10T02:48Z | `[Test]` | `[Done]` | Notice hoisted to state-agnostic position; 1/1 GREEN; gates clean |
