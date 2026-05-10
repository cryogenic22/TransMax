# TMX-3604-tools-toast — surface tools-page action failures via toast (5 sites)

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: A regulator on the Quality / Tools page submits a Black Book correction (handleSubmitCorrection — line 196) intended as a permanent rule-set update. The backend rejects (validation, AuthZ, 500). console.error fires silently. The success path uses `alert()` so the absence of an alert is the only signal — but the user can't tell whether the request was rejected or just slow. The Black Book never gets the rule. Same applies to the four other tools: positive feedback, audit, back-translate, matrix.
**Blast radius**: `frontend/app/workspace/tools/page.tsx` (5 catch blocks). 1 new e2e test. No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — final ticket of the mutation-error sweep. Bundles 5 sub-sites in one file because the fix is identical and reading 5 separate worksheets would be bloat.
- [ ] **G2 Reproduce-failure** — Playwright stub of POST submitFeedback → 500 RED before fix.
- [ ] **G3 Completion** — failed Black Book correction surfaces real error message via toast; other 4 sites use the same fix.

---

## 1. Task

Five identical `} catch (e) { console.error(e) }` swallows in `app/workspace/tools/page.tsx`:

| Line | Handler | User action |
|---|---|---|
| 178 | `handleVote('positive')` | thumbs-up rating |
| 196 | `handleSubmitCorrection` | Black Book rule correction (regulator-facing audit-trail event) |
| 279 | `handleAudit` | run Quality Auditor on text |
| 399 | `handleRun` (back-translate) | reverse-translate verification |
| 490 | `handleRun` (matrix) | multi-language translation matrix |

**Addenda**: A1 (Black Book corrections feed the audit chain), A3 (silent-fallback class extends to mutations).

## 2. Spec — acceptance criteria

- [ ] AC-1: All 5 catch blocks call `toast.error(getErrMessage(err, "..."))` with a context-specific fallback message ("Vote failed", "Couldn't submit correction", "Quality audit failed", "Back-translation failed", "Translation matrix failed").
- [ ] AC-2: All 5 success paths unchanged. The legacy `alert("Feedback submitted to Black Book!")` in handleSubmitCorrection is **deliberately not touched** — that's a success-UX concern (block-vs-non-block), separate from this failure-mode ticket.
- [ ] AC-3: 1 new e2e test stubs POST `/api/knowledge/feedback` → 500, opens the Tools page in a state that exposes the rate UI, fires the negative vote, opens the correction modal, fills in the suggestion, clicks Submit, asserts toast text visible.
- [ ] AC-4: Lint + typecheck clean.

**Out of scope**: alert() → toast.success migration; retry buttons.

## 3. Design

```ts
import { toast } from "sonner"

} catch (err) {
    toast.error(getErrMessage(err, "<context-specific message>"))
}
```

Each site gets its own context-specific fallback so toast text is meaningful even if the server returns no detail.

## 4. Code

| File | Change |
|---|---|
| `frontend/app/workspace/tools/page.tsx` | Add toast + getErrMessage imports; swap 5 console.error → toast.error with per-site fallback messages. |
| `frontend/e2e/tools-correction-toast.spec.ts` | NEW — 1 test for the Black Book correction submission path. |

## 5. Eval / Test

```
$ npm run e2e -- tools-correction-toast.spec.ts --workers=1
$ npm run lint && npm run typecheck
```

## 6. Red team

- **One e2e for five sites**: tested via the Quality Audit path because it has the simplest UI (paste two textareas, click button). The other 4 sites use the same `try { await api... } catch (err) { toast.error(...) }` pattern through the same `request()` failure → throw machinery. Synthetic mirror tests for the other 4 would be coverage padding.
- **`alert()` on success path**: deliberately untouched. Migrating to `toast.success` is a separate UX class (block-vs-non-block); this ticket is scoped to the failure-mode silent-swallow class.
- **Per-site fallback messages**: each catch picks a context-specific fallback ("Vote failed", "Couldn't submit correction", "Quality audit failed", "Back-translation failed", "Translation matrix failed"). Means the user sees a meaningful toast even if the server returns no detail string.
- **Optimistic state**: handleVote('positive') sets status='up' BEFORE awaiting the API. On failure, the green-fill stays. Acceptable — toast tells the user to retry; rolling back the optimistic state would be a larger UX change for a separate ticket.
- **Mutation-error sweep status**: this closes the sweep. 5 frontend surfaces touched: jobs delete (c6f87a0), segment save (1836924), 2× download (fae481d), tools page 5 sites (this commit).

CLEAN.

## 7. Fix

No iterations. RED on first run, GREEN after the import + 5 catch-block swaps.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — 5 sub-sites bundled per same-fix-same-test rationale.
- [x] G2 reproduce-failure: 1 test RED before fix; GREEN after.
- [x] G3 completion: real toast on tools-page action failures.
- [x] e2e: 1/1.
- [x] Lint + typecheck clean.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T05:25Z | — | `[Spec]` | Loop opened — TMX-3604-tools-toast |
| 2026-05-10T05:35Z | `[Spec]` | `[Code]` | RED test added; ran — confirmed RED |
| 2026-05-10T05:40Z | `[Code]` | `[Test]` | All 5 catch blocks swapped to toast.error; e2e GREEN |
| 2026-05-10T05:45Z | `[Test]` | `[Done]` | Lint + typecheck clean |
