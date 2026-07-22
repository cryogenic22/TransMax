# TMX-POSTURE-FAB — delete the fabricated compliance posture panel (A3, frontend)

**State**: `[Verify]` <!-- on branch loop/posture-fab; merge pending -->
**Owner**: Reviewer Frontend
**Sprint**: engine-pack convergence batch (A3 theme)
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` <!-- pure frontend render change; no schema, no API shape change -->
**Pre-mortem**: if this fails in production, the failure mode is a pharma reviewer reading a live-looking compliance panel ("Zero Retention", "NER_V2_EN", "AES-256") that describes controls the product does not have — an unearned compliance claim that fails a CSV review and destroys trust in every OTHER signal we render.
**Blast radius**: `frontend/components/control_views/ComplianceView.tsx` (Privacy Monitor column of the Control page compliance tab, `frontend/app/workspace/control/page.tsx` renders it unchanged); one new test file. No backend, no API, no other pods.

**Loop-driven-dev gates** (per `~/.claude/skills/loop-driven-dev`):
- [x] **G1 Anti-bloat (between stage 2 and 3)** — net-new code path passes the 5-test rubric:
  (a) needed at all? Yes — the fabricated panel must be REPLACED by something honest, and the honest data source (`api.trust.getPosture()`) already exists; this is deletion + rewire, not net-new capability.
  (b) <5 callers? Yes — one caller (ComplianceView itself; component stays file-private).
  (c) bundle impact <5%? Yes — net LOC roughly flat (static JSX out, fetch + render in).
  (d) reuses existing patterns? Yes — same fetch/loading/error/retry pattern as `frontend/app/workspace/trust/page.tsx:PrivacyMonitor` and the same `api.trust.getPosture()` client already in `frontend/lib/api.ts`. Decision: do NOT extract a shared component — the Trust Center renders in GlassCard visual language, ComplianceView in slate-card language; a shared component would need a style-variant prop (fails "stays simple") and a new module (fails G1). Duplicating the ~30-line honest render locally is the smaller diff.
  (e) ships with a test that fails without the change? Yes — red test below.
- [x] **G2 Reproduce-the-failure (bug tickets only, before stage 4)** — red test renders ComplianceView with a mocked api and asserts the fabricated strings are absent + the real posture endpoint is exercised. Fails against current code because `PrivacyCards()` hardcodes the strings and never calls the API.
- [x] **G3 Completion (between stage 7 and 8)** — the compliance tab must render only backend-derived posture; zero hardcoded compliance-claim strings remain in the component. VERIFIED: source changed (not tests-only); fabricated-string grep returns nothing; a UI repro of the original failure (open Control → Compliance) now renders live posture or an honest error — never the fabricated cards.

---

## 1. Task

`frontend/components/control_views/ComplianceView.tsx` contains `PrivacyCards()`, a static JSX block that renders fabricated compliance posture: "Zero Retention (Azure OpenAI)" / "Policy Active: NO_STORE" (the product does not use Azure OpenAI), "Scrubber Active: NER_V2_EN" (the PII service is regex-only — known issue C-12; NER_V2_EN does not exist), and a "Privacy Impact Assessment" card claiming US-EAST-2 residency, AES-256 encryption, and SHA-256 immutability — all with animated pulse dots that read as live status. This is the canonical A3 violation (an unearned claim in a regulated path) and is literally the first known instance listed in AGENTS.md Reviewer mode ("a compliance panel rendering fabricated posture"). The honest implementation already exists: `frontend/app/workspace/trust/page.tsx:PrivacyMonitor` fetches `api.trust.getPosture()` under the comment "A3: real posture only". Fix: delete the fabricated cards and render REAL posture from `api.trust.getPosture()` with honest loading / error / empty states, plus a link-through to `/workspace/trust`. Addenda at play: **A3** (no silent fallbacks / no unearned claims), A7 (link target stays under `/workspace/*`).

## 2. Spec — acceptance criteria

- [x] AC-1: Rendering `<ComplianceView />` (mocked api) produces a document in which none of the strings "Zero Retention", "NER_V2", "AES-256", "NO_STORE", "US-EAST-2", or "Azure OpenAI" appear.
- [x] AC-2: `api.trust.getPosture()` is called when ComplianceView mounts, and each control returned (label, value, verified badge) is rendered — real posture, not a static list.
- [x] AC-3: While the posture request is in flight, an honest loading state renders; if the request rejects, an honest error state renders (with retry, no substituted values — A3); if the backend returns zero controls, an honest empty state renders.
- [x] AC-4: A link to `/workspace/trust` renders so the reviewer can reach the full Trust Center.
- [x] AC-5: `grep -iE "zero retention|NER_V2|AES-256|NO_STORE|US-EAST|azure" ComplianceView.tsx` returns nothing; `npx vitest run` on the new test + existing suite passes; `npm run typecheck` and `npm run lint` clean.

Out of scope for this ticket: the AuditLogList half of ComplianceView (already real via `api.audit.list`); the Trust Center page itself; backend posture content; extracting a shared posture component (rejected at G1).

## 3. Design

Replace `PrivacyCards()` (static fabricated JSX) with a file-private `PrivacyPosture()` that mirrors the proven Trust Center pattern: `useState` posture/loading/error, fetch `api.trust.getPosture()` on mount, explicit retry on error. Render each `TrustControl` in ComplianceView's existing slate-card visual language with the same verified/not-verified semantics the Trust Center uses (`Verified` green vs `Not verified in-app` amber — the honesty distinction is load-bearing), the same "self-reported controls" disclaimer, and a `next/link` to `/workspace/trust`. Alternatives considered: (1) extract a shared `<PostureCards>` component used by both surfaces — rejected at G1: the two surfaces use different card systems (GlassCard vs slate), so sharing needs a variant prop and a new module for ~30 lines of JSX; (2) drop the panel entirely and render only a link to `/workspace/trust` — rejected: the Control page compliance tab is a reviewer surface and showing the real posture summary in place is strictly more useful at near-zero extra cost since the API client already exists. No ADR needed — this implements the already-decided A3 posture (see the trust page's "A3: real posture only" comment).

## 4. Code

| File | Lines | Change |
|---|---|---|
| `frontend/components/control_views/ComplianceView.tsx` | 1-5 | imports: + `Link`, `XCircle`, `ExternalLink`, `TrustPosture`; render `<PrivacyPosture />` in place of `<PrivacyCards />` |
| `frontend/components/control_views/ComplianceView.tsx` | 31-117 | DELETE fabricated `PrivacyCards()` (Zero Retention / NO_STORE / NER_V2_EN / US-EAST-2 / AES-256 static cards with pulse dots); ADD `PrivacyPosture()` fetching `api.trust.getPosture()` with loading / error+retry / empty states, per-control verified vs not-verified-in-app badges, self-reported disclaimer, and link to `/workspace/trust` |
| `frontend/__tests__/ComplianceView.test.tsx` | 1-108 | NEW red test: fabricated strings absent, real endpoint called + controls rendered, link present, honest error state (no substituted values), honest empty state |

No parent wiring change: `PrivacyCards` was file-private; `frontend/app/workspace/control/page.tsx` imports only `ComplianceView`, unchanged.

## 5. Eval / Test

**RED (pre-fix), verbatim:**
```
npx vitest run __tests__/ComplianceView.test.tsx
```
```
❯ __tests__/ComplianceView.test.tsx (5 tests | 5 failed) 4104ms
   × <ComplianceView> privacy posture (A3: real posture only) > never renders the fabricated compliance-claim strings 44ms
expected document not to contain element, found <h3
   × ... > fetches and renders the REAL posture from api.trust.getPosture() 1020ms
     → Unable to find an element with the text: PII scrubbing.
   × ... > links through to the full Trust Center at /workspace/trust 1009ms
   × ... > renders an honest error state (no substituted values) when the posture fetch fails 1017ms
     → Unable to find an element with the text: /couldn't load trust posture/i.
   × ... > renders an honest empty state when the backend reports zero controls 1013ms
 Test Files  1 failed (1)
      Tests  5 failed (5)
```
(The `<h3` found by the not-to-contain assertion was the fabricated "Zero Retention (Azure OpenAI)" heading; `getPosture` was never called.)

**GREEN (post-fix), verbatim:**
```
npx vitest run __tests__/ComplianceView.test.tsx   →  Test Files  1 passed (1) / Tests  5 passed (5)
npx vitest run                                     →  Test Files  17 passed (17) / Tests  128 passed (128)
npm run typecheck                                  →  tsc --noEmit  (clean, exit 0)
npm run lint                                       →  eslint --max-warnings 0  (clean, exit 0)
grep -inE "zero retention|NER_V2|AES-256|NO_STORE|US-EAST|azure" components/control_views/ComplianceView.tsx  →  no matches (exit 1)
```

## 6. Red team

- **Backend without the endpoint / endpoint down:** panel renders the explicit error card with the real message + Retry; nothing substituted. Fail-loud is the A3-correct production behaviour, verified by the rejected-fetch test.
- **Zero controls returned:** honest "No posture controls reported" empty state — verified by test. No fabricated defaults fill the gap.
- **Found while here (deferred, out of scope):** the sibling `AuditLogList` in the same file swallows fetch errors into `setLogs([])`, so a failed audit fetch renders as "No activity recorded" — an A3-adjacent silent fallback. NOT fixed here (distinct failure mode, would need its own red test; ticket scope is the fabricated posture panel). Flagged for a follow-up ticket in the return notes.
- **First green run found a test bug, not a code bug:** `getByText("Not verified in-app")` matched both the disclaimer copy and the badge (same wording the Trust Center uses). Fixed the assertion to target the badge (`bg-amber-100`) — behaviour was correct.
- **Comment sweep:** my first explanatory comment repeated the fabricated strings verbatim, so the repo-wide fabricated-claim grep would still hit this file. Reworded; AC-5 grep now returns nothing.
- **setState-after-unmount on slow fetch:** same pattern as the shipped Trust Center `PrivacyMonitor`; React 18 no longer warns and no leak beyond the resolved promise. Accepted for parity; not worth an abort-controller divergence here (G1).
- `posture.app_env` fetched but not displayed in this compact column — full detail is one click away via the `/workspace/trust` link (AC-4).

## 7. Fix

Both red-team findings actioned pre-commit: badge-targeted assertion (test), reworded comment (component). Re-run after both: target test 5/5 green, full suite 128/128 green, grep clean. AuditLogList silent-catch deferred with explicit note — no other findings.

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] CI green: n/a (loop branch; merge pending)
- [ ] `.context/active_tasks.md` updated: NOT by this agent (orchestrator owns it)
- [ ] Ratchet baseline updated: n/a

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created from _template.md on branch loop/posture-fab |
| 2026-07-22T01:30Z | `[Spec]` | `[Verify]` | Stages 1-7 complete; red 5/5-fail evidence + green 128/128 captured; on branch loop/posture-fab; merge pending — commit SHA recorded at stage 8 |
