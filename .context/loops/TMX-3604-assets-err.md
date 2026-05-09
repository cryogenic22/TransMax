# TMX-3604-assets-err — surface real fetch errors in Trust Center Assets view

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-10
**Closed**: —
**Reversibility**: `two-way` — pure presentation refinement.
**Pre-mortem**: If this fails in production, the failure mode is — a regulator/auditor opens the Trust Center > Assets tab during a backend hiccup, sees "Translation Rules: 0 / Pending Review: 0 / Glossaries: 0", concludes the company has no rule coverage, raises that as a finding. The system actually has rules; the API was just down. Same A3 class as TMX-3603-jobs-id-err — silent fallback substituting an indistinguishable default for real failures.
**Blast radius**: `frontend/components/control_views/AssetsView.tsx` (one fetchCounts function reshaped, new error state, conditional banner). New `frontend/e2e/control-assets.spec.ts` (2 tests). No backend or wire change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — extending the same A3 fix pattern to a sibling surface. (a) needed: yes — same class as TMX-3603 on a regulator-facing page; (b) <5 callers: 1 file; (c) bundle: negligible (Promise.allSettled built-in); (d) reuses existing patterns: yes — exact same role='status' banner + getErrMessage helper + per-section state pattern; (e) test fails without it: yes — Playwright stub of 500 currently shows misleading 0/0/0.
- [ ] **G2 Reproduce-failure** — Playwright tests stub the failure mode RED before fix.
- [ ] **G3 Completion** — when the rules / glossaries fetches return 500, the view shows a banner with the actual error message AND the failed cards display "—" (not "0"), so the empty-state is visually distinct from a failure-state.

---

## 1. Task

`AssetsView.tsx:18-20` wraps each `api.knowledge.*` call in `.catch(() => [])`. When the API is down, the page renders three cards saying "0 / 0 / 0". The legitimate empty state (no rules yet) and the failure state (API down) are visually identical — a reviewer looking at the Black Book to verify rule coverage cannot tell which they're seeing.

**Addenda**: A3 (no silent fallbacks in regulated paths — primary), A1 (audit-by-default — the asset summary is part of the regulatory surface), A7 (canonical IA — `/workspace/control` is the unified command center).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `api.knowledge.listRules()` rejects, the "Translation Rules" card shows "—" instead of "0".
- [ ] AC-2: Symmetric for `listRules("PENDING_APPROVAL")` ("Pending Review" → "—") and `listGlossaries()` ("Glossaries" → "—").
- [ ] AC-3: When ANY fetch fails, a `role="status"` banner renders above the cards with text containing the actual server error message (not a generic "Couldn't load assets" string with no information).
- [ ] AC-4: When all three fetches succeed but return empty arrays, the cards show "0" (legitimate empty state, no banner). This is the cell that matters — empty must remain distinguishable from failure.
- [ ] AC-5: All existing tests still pass.
- [ ] AC-6: 2 new e2e tests in `frontend/e2e/control-assets.spec.ts`:
  - "renders error banner + '—' cards when listRules fails" — stubs only the listRules endpoint to 500, asserts banner visible with stub-supplied detail, asserts the "Translation Rules" card shows "—".
  - "renders 0/0/0 with no banner on legitimate empty state" — stubs all three to return `[]`, asserts cards show "0" and there's no error banner.

**Out of scope**:
- Retry button (defer until reviewers ask for it).
- Per-card error icons (a single banner is enough; per-card icons would clutter).
- The other control_views (DashboardView already has a graceful "Backend unreachable" warning; ComplianceView/JobsView are separate tickets if/when audit-flagged).

## 3. Design

```ts
const [ruleCount, setRuleCount] = useState<number | null>(null)
const [pendingCount, setPendingCount] = useState<number | null>(null)
const [glossaryCount, setGlossaryCount] = useState<number | null>(null)
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)  // NEW

useEffect(() => {
  (async () => {
    const [r, p, g] = await Promise.allSettled([
      api.knowledge.listRules(),
      api.knowledge.listRules("PENDING_APPROVAL"),
      api.knowledge.listGlossaries(),
    ])
    if (r.status === "fulfilled") setRuleCount(r.value.length)
    if (p.status === "fulfilled") setPendingCount(p.value.length)
    if (g.status === "fulfilled") setGlossaryCount(g.value.length)
    const firstErr = [r, p, g].find(x => x.status === "rejected") as PromiseRejectedResult | undefined
    if (firstErr) setError(getErrMessage(firstErr.reason, "Failed to load assets"))
    setLoading(false)
  })()
}, [])
```

The `useState<number | null>` already encodes the "didn't load" state — initial `null`, only set on success. So a failed fetch leaves the count at `null`. The display pivots:

```tsx
value={loading ? "..." : (ruleCount == null ? "—" : String(ruleCount))}
```

This naturally distinguishes:
- Loading: "..."
- Success-with-zero: "0"
- Failed: "—"

Banner uses the same `role="status"` + `aria-label` shape as TMX-3603-jobs-id-err.

**Why first-error wins for the banner**: 3 fetches on the same server, almost always fail in concert (the API is down or it isn't). Surfacing one real message is better than concatenating three identical ones. If they DO fail differently (one 500, one 404), the banner shows whichever came first; the per-card "—" still shows which sections are degraded.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/control_views/AssetsView.tsx` | Promise.allSettled + per-source-of-truth state shape; pivot card display on null; conditional error banner. |
| `frontend/e2e/control-assets.spec.ts` | NEW — 2 tests for the failure modes. |

## 5. Eval / Test

```
$ cd frontend && npm run e2e -- control-assets.spec.ts --workers=1
$ npm run lint && npm run typecheck && npm run build
```

Expected: 2/2 e2e GREEN, lint/typecheck/build clean.

## 6. Red team

- **First-error wins for the banner**: when 2 of 3 endpoints fail, the banner surfaces only one message. Acceptable: failures are typically correlated (the API is down or it isn't); the per-card "—" pattern shows which sections are affected. If the failures genuinely diverge in production we can revisit.
- **Pending Review = 0 vs no rules at all**: the legitimate empty state distinguishes "no pending rules but plenty active" (Pending=0, Rules=N) from "no rules in system" (Pending=0, Rules=0) via the Translation Rules count, not via this view. Banner-or-no-banner correctly separates failure from empty.
- **Lint rule didn't trigger here**: AssetsView uses a local async function inside useEffect rather than a useCallback'd handler — different shape than TMX-3603-jobs-id-err's, so the `react-hooks/set-state-in-effect` rule didn't fire. No re-shaping needed.
- **role='status' avoids Next.js announcer collision**: same fix as TMX-3603-jobs-id-err. Banner identified by aria-label="Assets failed to load".
- **A11y**: `loading ? "..." : n == null ? "—" : String(n)` — the "—" character is announced by SR as "em dash" in most engines. The banner's aria-label gives the SR user the necessary context that this is a failure state, not a pause.

CLEAN — no remaining findings.

## 7. Fix

No iterations needed. RED on first run (banner missing), GREEN after the single edit. The empty-state test already passed pre-fix because the fallback to "0" coincidentally matched the assertion, but the failed-test now also passes — both states are correctly distinguishable.

## 8. Deploy

- [x] G1 anti-bloat: PASSED — same A3 fix pattern as TMX-3603-jobs-id-err, applied to a sibling regulator-facing surface.
- [x] G2 reproduce-failure: 1 RED test before fix; both GREEN after.
- [x] G3 completion: failed listRules → "—" cards + real-error banner; all-empty → "0" cards + no banner. End-to-end distinguishable.
- [x] e2e: 2/2 in new file.
- [x] Lint / typecheck / build all green.
- [ ] Commit + push (next).

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-10T01:55Z | — | `[Spec]` | Loop opened — TMX-3604-assets-err |
| 2026-05-10T02:05Z | `[Spec]` | `[Code]` | New e2e file with 2 tests; ran — 1 RED, 1 GREEN as expected |
| 2026-05-10T02:10Z | `[Code]` | `[Test]` | Promise.allSettled + display helper + banner; 2/2 e2e GREEN |
| 2026-05-10T02:15Z | `[Test]` | `[Done]` | Lint / typecheck / build clean; ready to commit |
