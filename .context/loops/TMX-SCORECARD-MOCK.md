# TMX-SCORECARD-MOCK — remove the first-paint mock quality scorecard (A3, frontend)

**State**: `[Verify]` — on branch `loop/scorecard-mock`; merge pending
**Owner**: Reviewer Frontend (loop agent, batch A3)
**Sprint**: engine-pack convergence batch
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way`
**Pre-mortem**: if this fails in production, the failure mode is a reviewer seeing an invented quality score (94 / "Negation Safety 88") — or a fabricated perfect 100 / "All Checks Passed" for a document the quality engine never scored — and signing off on it.
**Blast radius**: one page — `frontend/app/workspace/documents/[id]/page.tsx` (Quality Scorecard tab of the document review surface) + one new test file. No API, no backend, no shared components.

**Loop-driven-dev gates** (per `~/.claude/skills/loop-driven-dev`):
- [x] **G1 Anti-bloat (between stage 2 and 3)** — net-new code path passes the 5-test rubric:
  (a) needed at all? yes — removing a fabricated trust signal is the ticket; the empty state extends the existing page, no new module;
  (b) <5 callers? yes — page-local JSX only;
  (c) bundle impact ~0 (a few JSX lines, no new deps);
  (d) reuses the QualityDashboard TMX-UX-QDASH-REAL amber "scoring unavailable — manual review required" pattern and the page's existing loading gate;
  (e) ships with tests that fail without the change (see stage 5 red run).
- [x] **G2 Reproduce-the-failure (before stage 4)** — red tests written and run BEFORE the fix; verbatim red output in stage 5. See the G2 nuance in stage 1.
- [x] **G3 Completion (between stage 7 and 8)** — the user-visible fabrication (mock literals + vacuous perfect score) is gone from the shipped source and the repro tests pass. Source changed (not tests-only); ACs 1-5 all verified green.

---

## 1. Task

`frontend/app/workspace/documents/[id]/page.tsx` seeds its scorecard `useState` with a hardcoded mock (`overall_score: 94`, categories including `"Negation Safety", score: 88, issues: 2`). A real computation overwrites it in a `useEffect`, but the mock is a fabricated trust signal sitting in a regulated reviewer surface — A3 (no silent fallbacks / no unearned claims). Fix: initial state `null`; keep the page's existing honest loading gate until real data lands; when scoring is unavailable, render the honest "scoring unavailable" empty state per QualityDashboard's TMX-UX-QDASH-REAL pattern. No mock numbers anywhere in the file.

**G2 nuance (found while reproducing):** during a pending fetch the current page renders a full-screen "Loading document..." gate, so the mock state never actually paints in that path — the ticket's literal repro passes pre-fix. The mock IS one refactor away from painting, so that test ships as a regression guard. The genuinely red, user-visible A3 failure in the same state: when the fetch succeeds but NO segment carries `gate_results` (quality engine never scored), the current code computes and paints a fabricated **100 / "All Checks Passed" / all categories 100%** — a vacuous-green verdict for an unscored document. That path plus a source-literal scan are the red tests.

## 2. Spec — acceptance criteria

- [ ] AC-1: The page source contains no mock scorecard literals — no `overall_score: 94`, no `score: 88`, no hardcoded category scores/issue counts anywhere in the file (source-scan test).
- [ ] AC-2: With the data fetch pending (api mocked, unresolved), the rendered DOM shows the honest loading state ("Loading document...") and does NOT contain "94" or "Negation Safety".
- [ ] AC-3: When the fetch resolves but no segment has `gate_results` (scoring never ran), the Quality Scorecard tab renders the honest amber "Quality scoring unavailable — manual review required" empty state — no score dial, no "All Checks Passed", no category percentages.
- [ ] AC-4: When segments DO carry real `gate_results`, the scorecard renders the real computed values exactly as before (regression: computation path unchanged).
- [ ] AC-5: `npx vitest run` (new file + nearest suite), `npm run typecheck`, `npm run lint` all pass.

Out of scope for this ticket: the scorecard scoring formula itself (per-category `100 - n*penalty` heuristic), the Issues panel, backend scoring availability signals, wiring `<QualityDashboard>` into this page, the other view modes.

## 3. Design

Three surgical edits, no new module. (1) `useState<QualityScorecard | null>(null)` — the surface starts with no claim. (2) In the fetch effect, gate the existing computation on scoring availability: `segs.some(s => s.gate_results != null)`; when no segment was ever scored, `setScorecard(null)` instead of letting empty-violation arrays produce a vacuous 100/PASSED. (3) In the scorecard view, branch on `scorecard === null` to an amber empty-state panel mirroring QualityDashboard's TMX-UX-QDASH-REAL wording ("Quality scoring unavailable — manual review required" + unverified-output explanation); the real grid renders only when `scorecard` is non-null.

Alternatives rejected: (a) keep a zeroed-out initial scorecard object — still an invented claim (0% reads as "measured terrible"), same A3 defect with a different sign; (b) reuse `<QualityDashboard>` component here — it is a per-segment confidence panel with expand/breakdown props that don't map to the document-level scorecard; importing it would need prop shims (bloat) for a visual pattern that is 15 lines of JSX; (c) treat `segments.length === 0` separately from "no gate_results" — both mean "nothing scored", one honest state covers both.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `frontend/app/workspace/documents/[id]/page.tsx` | 55-58 | mock initial state → `useState<QualityScorecard \| null>(null)` with A3 comment |
| `frontend/app/workspace/documents/[id]/page.tsx` | 70-76 | `scoringRan = segs.some(s => s.gate_results != null)` availability signal |
| `frontend/app/workspace/documents/[id]/page.tsx` | 110, 124 | `setScorecard(scoringRan ? {…real computation…} : null)` — unscored docs no longer default to 100/PASSED |
| `frontend/app/workspace/documents/[id]/page.tsx` | 407-436 | amber "Quality scoring unavailable — manual review required" empty state (mirrors QualityDashboard TMX-UX-QDASH-REAL wording); real grid gated behind `scorecard &&` |
| `frontend/__tests__/DocumentReviewPage.test.tsx` | new | 4 tests per AC-1..AC-4 (api/next-navigation/sonner mocked; source-literal scan) |

## 5. Eval / Test

**RED run (pre-fix), verbatim:**

```
npx vitest run __tests__/DocumentReviewPage.test.tsx
```

```
 ❯ __tests__/DocumentReviewPage.test.tsx (4 tests | 2 failed) 1112ms
   × DocumentReviewPage — no fabricated quality scorecard (A3) > contains no mock scorecard literals in the page source 8ms
     → expected '"use client"\r\n\r\nimport { useState…' not to match /overall_score:\s*94/
   × DocumentReviewPage — no fabricated quality scorecard (A3) > renders the honest 'scoring unavailable' state — not a fabricated perfect score — when no segment has gate results 1016ms
AssertionError: expected '"use client"\r\n\r\nimport { useState…' not to match /overall_score:\s*94/
TestingLibraryElementError: Unable to find an element with the text: /quality scoring unavailable/i.
 Test Files  1 failed (1)
      Tests  2 failed | 2 passed (4)
```

(The 2 pre-fix passes are the predicted ones — the pending-fetch guard, hidden by the full-page loading gate, and the real-data regression path. Documented in stage 1's G2 nuance.)

**GREEN run (post-fix):**

```
npx vitest run __tests__/DocumentReviewPage.test.tsx
 ✓ __tests__/DocumentReviewPage.test.tsx (4 tests) 230ms
 Test Files  1 passed (1)
      Tests  4 passed (4)

npx vitest run          (full unit suite)
 Test Files  17 passed (17)
      Tests  127 passed (127)

npm run typecheck   → tsc --noEmit: clean
npm run lint        → eslint --max-warnings 0: clean
```

## 6. Red team

1. **Partial scoring** — some segments scored, some not → `scoringRan` true and unscored segments count as issue-free. Pre-existing formula semantics (explicitly out of scope in stage 2); this change strictly improves on the old behaviour (fully-unscored docs showed 100/PASSED). Follow-up candidate: surface "N of M segments scored" on the scorecard.
2. **Stale scorecard after HITL edit** — `handleSaveEdit` refreshes segments but never recomputed the scorecard, before and after this change. Pre-existing, out of scope.
3. **`gate_results: {}`** — empty object counts as "engine ran, scored clean". Object presence is the availability signal; matches the backend shape (`units_ok`/`negation_ok`/`violations`).
4. **"Approve All" is a no-op button** — adjacent trust-signal debt observed, not touched (scope discipline).
5. **Test robustness** — source-scan is CRLF-safe (regex, not line-based) and the literal `[id]` path segment is safe on Windows and Linux (fs does not glob).

## 7. Fix

No blocking findings — clean. Items 1 and 4 recorded as follow-up candidates for the orchestrator, not in-scope changes.

## 8. Deploy

- [x] Commit: (SHA recorded in structured output) — on branch `loop/scorecard-mock`; merge pending
- [ ] Push / `.context/active_tasks.md`: orchestrator-owned; NOT done here by design

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created from _template; G2 nuance documented (loading gate hides mock; vacuous-green is the live failure) |
| 2026-07-22T01:30Z | `[Spec]` | `[Verify]` | Red 2/4 → fix → green 4/4; full suite 127/127; typecheck+lint clean. On branch `loop/scorecard-mock`; merge pending. |
