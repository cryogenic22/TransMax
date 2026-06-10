# TMX-FEEDBACK-2 — In-app feedback widget (frontend)

**State**: `[Done]` — `085aa94` on origin/main
**Owner**: Reviewer Frontend
**Sprint**: 2 (feedback-loop initiative)
**Started**: 2026-06-05
**Closed**: —
**Reversibility**: `two-way` — additive components + one client + 4 lines in root layout. Revert by deleting the two components + client and unmounting.
**Pre-mortem**: if this fails in production, the failure mode is a broken floating button or a widget that errors on submit — contained to the widget; no impact on translation, review, or audit surfaces. Submit failures surface a toast (A3), never a silent swallow.
**Blast radius**: `frontend/components/feedback/*` (new), `frontend/lib/feedbackApi.ts` (new), `frontend/app/layout.tsx` (+4 lines), `frontend/__tests__/FeedbackWidget.test.tsx` (new). Mounted globally; renders on every surface except `/` and `/login`.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — net-new because there is no in-app issue-intake UI; reuses sonner, the cookie-token idiom from `lib/api.ts`, design tokens, and the root `<Toaster>` mount point; ships with vitest coverage.
- [x] **G2 Reproduce-the-failure** — N/A (greenfield).
- [x] **G3 Completion** — clicking the floating button opens the widget; category→describe→priority→submit POSTs to `/api/feedback` and shows a success toast + feedback id; a backend failure surfaces an error toast + in-panel alert. **Backend path verified live 2026-06-10** (the widget's `feedbackApi.submit` target `POST /api/feedback` returns 200 and persists on Railway — see TMX-FEEDBACK-1 G3). Widget rides the same `NEXT_PUBLIC_API_URL` the working app uses.

---

## 1. Task

Port market_zero's `FeedbackButton` + `FeedbackWidget` to TransMax's Next.js App Router. Faithful chat-style flow (category → description (+screenshot paste) → priority → submit), restyled to TMX design tokens, using sonner for toasts and the TMX-FEEDBACK-1 backend.

Addenda: **A3** (submit failures surface a toast + alert, never mock/swallow); **A7** (mounted in the canonical app shell; hidden on landing/login; no new top-level route).

## 2. Spec — acceptance criteria

- [x] AC-1: floating "Feedback" pill renders on app surfaces, hidden on `/` and `/login`.
- [x] AC-2: clicking it dispatches `tmx:open-feedback`; the widget opens (decoupled via window event).
- [x] AC-3: state machine greeting→category_selected→description_provided→priority_selected→submitted|error; each step appends to an in-panel transcript.
- [x] AC-4: submit derives a title from the first sentence, attaches `page_url` + diagnostics, POSTs via `feedbackApi.submit`, shows success toast + feedback id.
- [x] AC-5: a failed submit shows an error toast AND an in-panel `role="alert"` (A3).
- [x] AC-6: screenshot paste (Ctrl+V) attaches up to 5 images ≤2MB each; draft persists to sessionStorage across accidental close.
- [x] AC-7: typecheck + lint clean; vitest coverage for the happy path, the failure path, and button visibility.

Out of scope: an admin "feedback inbox" view (future); attachment thumbnails beyond paste; auth wall (TMX-AUTH-WALL).

## 3. Design

Two client components decoupled by a `tmx:open-feedback` window event (so the trigger and dialog share no React state). Styling uses Tailwind utilities + TMX CSS tokens (`--brand-*`, `--neutral-*`, `--error-*`) so it tracks the design system (TMX-3601). `feedbackApi.ts` mirrors the cookie-bearer fetch idiom in `lib/api.ts` rather than coupling to the private `ApiClient.request`. Mounted in the root layout next to `<Toaster>`.

Rejected: a route/page for feedback (violates A7 + worse UX than a global widget); a heavyweight modal lib (sonner + a plain fixed div suffice).

## 4. Code

| File | Change |
|---|---|
| `frontend/lib/feedbackApi.ts` | new — types + `feedbackApi.submit()` (cookie bearer) |
| `frontend/components/feedback/FeedbackButton.tsx` | new — floating trigger, hidden on `/` + `/login` |
| `frontend/components/feedback/FeedbackWidget.tsx` | new — chat-style dialog, attachments, draft persistence, sonner |
| `frontend/app/layout.tsx` | +4 — import + mount both inside `<AuthProvider>` |
| `frontend/__tests__/FeedbackWidget.test.tsx` | new — 5 vitest cases |

## 5. Eval / Test

```
npm run typecheck   # clean
npm run lint        # clean (--max-warnings 0)
npx vitest run      # 14 files, 111 passed (incl. 5 new)
npm run build       # see status log
```

## 6. Red team

- A3: both failure paths (network + non-2xx) throw and surface a toast + `role="alert"`; no fallback content. Covered by the failure test.
- Accidental-close: draft persists to sessionStorage; cleared on success.
- a11y: dialog has `role="dialog"`/`aria-modal`/labelled title; Esc closes; Tab is trapped; focus restores on close.
- Auth: client sends the `transmax_token` cookie bearer when present; works in `none` mode (no token) and will carry the token once TMX-AUTH-WALL lands.
- Not covered (acceptable): attachment count/size enforced client-side only (backend stores the JSON as-is); a malicious client could POST a large `attachments` blob — bounded later by API-side validation/rate-limit when the wall lands.

## 7. Fix

Removed a `@ts-expect-error` (custom ring-color prop) in favour of a Tailwind ring class — respects the no-TS-suppression convention. Otherwise clean.

## 8. Deploy

- [x] Commit: `085aa94` (bundled with TMX-FEEDBACK-1)
- [x] `next build` green (13 routes generated)
- [x] Pushed to origin/main → Railway frontend auto-deploys
- [x] `.context/active_tasks.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-05 | — | `[Spec]` | Created |
| 2026-06-05 | `[Spec]` | `[WIP — pending push]` | Built; typecheck/lint/vitest green; running `next build` before push |
| 2026-06-10 | `[Done]` | `[Done]` | Backend submit path verified live on Railway (POST 200 + persist + soft-delete round-trip). Frontend redeployed from `085aa94`; widget hits the live backend via `NEXT_PUBLIC_API_URL`. G3 checked. |
