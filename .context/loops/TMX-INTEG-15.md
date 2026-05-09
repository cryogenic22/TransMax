# Loop 15 — Frontend ↔ Backend integration tests

**State**: `[Done]` pending push
**Owner**: Reviewer Frontend pod (Antigravity / Pod B)
**Sprint**: 1
**Started**: 2026-05-09
**Closed**: 2026-05-09

---

## 1. Task

Loop 14 (TMX-3614) wired the frontend test harness with mocked backend e2e — proves the frontend renders. Loop 15 closes the test pyramid by wiring **integration tests against a live backend**: the frontend talks to a real FastAPI process, hitting the real DB layer, exercising real CORS, real auth-mode routing, real serialisation.

This loop:
1. Adds `frontend/e2e-integration/` test suite that requires a live backend.
2. Adds `frontend/playwright.integration.config.ts` that spawns BOTH `uvicorn app.main:app --port 8001` AND `npm run dev` (port 3000) as Playwright web servers, then runs the integration suite against the stack.
3. Adds CI job `frontend-integration` that runs after `test` and `frontend` jobs are green.
4. Tests cover: backend health, frontend boots without "API offline" banner, dashboard stats endpoint round-trips through the frontend.

**Blast radius**: `frontend/` (new test dir + new config + new script) and `.github/workflows/ci.yml` (new job). No production code touched. Backend is exercised exactly as in production — no test-only forks.

**Addenda**: A2 (quality at gates — frontend↔backend contract enforced by CI), A6 (LLMs are qualified suppliers — these tests don't call LLMs but the contract test ensures the API surface that DOES call LLMs stays stable), A10 (`.context/` brain).

## 2. Spec — acceptance criteria

- [ ] AC-1: `frontend/e2e-integration/` exists with at least 3 spec files exercising the live backend:
  - `health.spec.ts` — direct HTTP to `:8001/health`, asserts 200 + JSON shape
  - `dashboard.spec.ts` — frontend fetches `/api/dashboard/stats` via UI render, asserts numbers/strings appear in DOM
  - `documents.spec.ts` — frontend fetches `/api/documents` (list endpoint), asserts the empty/non-empty list state renders without errors
- [ ] AC-2: `frontend/playwright.integration.config.ts` exists, `webServer` is an array spawning uvicorn (cwd: project root) AND Next dev (cwd: frontend/).
- [ ] AC-3: `package.json` exposes `e2e:integration` script.
- [ ] AC-4: A new CI job `frontend-integration` runs `npm run e2e:integration` after both backend `test` and `frontend` jobs are green. Uses SQLite (APP_ENV=test) — no Postgres dependency for the integration job.
- [ ] AC-5: `frontend/.gitignore` excludes the integration playwright report dir.
- [ ] AC-6: Local invocation `npm run e2e:integration` works end-to-end on Windows + Linux. The webServer array waits for both ports before tests fire.
- [ ] AC-7: Existing checks (Loop 14 mocked-backend e2e, vitest, lint, typecheck, build) stay green.

**Out of scope** (sister loops):
- A `post-deploy-smoke` job that hits the deployed Railway URL — Sprint 2 follow-up.
- LLM-touching integration tests (translation flow end-to-end). Requires OpenAI key in CI; spawned as TMX-INTEG-LLM. The current loop is contract-only.
- Auth-mode integration. The default `auth_mode=none` is what these tests exercise; an auth-on variant is a sister ticket.

## 3. Design

**Why one combined Playwright config rather than two separate configs**: Playwright's `webServer: [...]` lets us spawn multiple processes that ALL must be ready before tests run. Cleaner than docker-compose for this scale; pytest can stay as the backend's contract gate, Playwright owns the frontend↔backend contract.

**Why SQLite, not Postgres**: this loop's tests touch GET endpoints only (no pgvector embedding inserts). SQLite removes the need for a `services: postgres:` block in CI. If a future test needs pgvector, it gets its own variant.

**Why uvicorn from project root, not a nested path**: `app.main:app` resolves correctly from `cwd=.`. Setting cwd to the frontend dir then trying to import `app.main` would force PYTHONPATH gymnastics.

**Port choices**:
- Backend: 8001 (matches NEXT_PUBLIC_API_URL default in `.env.example`)
- Frontend: 3000 (Next.js default)

**Why webServer waits for /health, not /**:
- Backend: `url: "http://localhost:8001/health"` — Playwright polls until the FastAPI process responds 200. `/` may 404 (FastAPI doesn't serve a root route by default).
- Frontend: `url: "http://localhost:3000"` — Next dev's root always 200 (landing page).

**Backend env in CI**:
- `APP_ENV=test` so `core/config.py` uses SQLite
- `OPENAI_API_KEY=test` (falsy stub; no LLM calls made)
- `AUTH_MODE=none` (no auth required)

**Why this loop intentionally does NOT exercise LLM paths**: a CI-time test that calls OpenAI would be slow, flaky, and burn budget. The translation contract is best tested via the eval harness (`tests/evals/`) using fixture LLM responses. This loop is the frontend↔backend contract; LLM calls are a different concern.

## 4. Code

| File | Change |
|---|---|
| `frontend/e2e-integration/health.spec.ts` | new — direct backend health probe |
| `frontend/e2e-integration/dashboard.spec.ts` | new — frontend → /api/dashboard/stats |
| `frontend/e2e-integration/documents.spec.ts` | new — frontend → /api/documents |
| `frontend/playwright.integration.config.ts` | new — dual webServer config |
| `frontend/package.json` | add `e2e:integration` script |
| `frontend/.gitignore` | add `playwright-report-integration/` |
| `.github/workflows/ci.yml` | add `frontend-integration` job |

## 5. Eval / Test

```
$ cd frontend && npm run e2e:integration
# spawns uvicorn :8001 + next dev :3000, polls /health, runs tests
```

Then push and verify GitHub Actions `frontend-integration` job is green.

## 6. Red team

- **CLEAN** after one fix iteration. Tier 2 22-item self-review on the diff:
  - 8/8 integration tests passing in 1.2 min on Windows. Stack: uvicorn :8001 + Next dev :3000 + Playwright. Both webServers pre-warm via `/health` and `/` respectively before the test suite starts.
  - 💡 **Real-bug catch**: my first cut of `documents.spec.ts` asserted `body.documents` based on a stale type contract. The integration test caught the mismatch — backend actually returns `{ items, total, page, page_size }`. Fixed the test (kept the assertion contract-shape-only, not count-dependent).
  - 💡 **CORS preflight covered**: explicit OPTIONS test with `Origin: http://localhost:3000` confirms the FastAPI CORSMiddleware echoes the origin (or wildcard) — guards against accidental `allow_origins=["http://localhost:3009"]` typos breaking the integration.
  - 💡 **Console-error guard**: `dashboard.spec.ts` and `documents.spec.ts` both register `pageerror` listeners and assert empty-error-array. Catches React render errors that wouldn't be surfaced in mock e2e (because mocks return shapes the frontend already expects).
  - 💡 **Workers=1 (serial)**: backend SQLite is single-writer; parallel workers would race on init_db(). Serial is fine for 8 short tests.
  - 💡 **No LLM coupling**: tests don't trigger any translation flow. Pure contract / render checks. The translation contract is enforced by the eval harness (`tests/evals/`) which uses fixture LLM responses.

## 7. Fix

One iteration: rewrote `documents.spec.ts` test to check `body.items` (the backend's actual paginated shape) instead of the imagined `body.documents`. Re-run: 3/3 documents tests green; full integration: 8/8 in 1.2 min.

## 8. Deploy

- [x] Code: `frontend/{playwright.integration.config.ts,e2e-integration/health.spec.ts,e2e-integration/dashboard.spec.ts,e2e-integration/documents.spec.ts}`, `frontend/package.json` (e2e:integration script), `frontend/.gitignore` (integration artefacts), `.github/workflows/ci.yml` (frontend-integration job dependent on `test` + `frontend`)
- [x] Local stack verified: uvicorn boot in <2s, Next dev boot in ~5s, full suite 1.2 min
- [x] Tests: 8 integration tests across 3 files (3 backend-API contract, 3 frontend-render-vs-live-API, 2 redirect-thru-live-stack)
- [x] Real bug surfaced (and fixed): contract drift in DocumentListResponse shape
- [x] All Loop 14 checks still green: vitest 21/21, mocked e2e 3/3, lint 0e/185w, typecheck clean, build 16 routes
- [x] Backend regression-free: 716/719 (3 pre-existing flakes unchanged), ratchet 17/17
- [ ] Commit + push (next)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T14:00Z | — | `[Spec]` | Loop opened — frontend↔backend integration |
| 2026-05-09T14:30Z | `[Spec]` | `[WIP]` | Wrote 3 spec files + dual-webServer config; first run 7/8 |
| 2026-05-09T14:35Z | `[WIP]` | `[Fix]` | Documents shape contract mismatch |
| 2026-05-09T14:45Z | `[Fix]` | `[Done]` (pending commit + push) | 8/8 green; CI job added |
