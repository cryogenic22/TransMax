# TransMax v3.0 "Pilot Ready" — Active Backlog

**Status**: v3.0 release plan signed off 2026-05-01. Sprint 0 in progress.
**Plan**: `research/v3_pilot_ready_release_plan.md` (Parts I + II + III)
**Parking lot**: `parking_lot/deferred_features.md`
**Backlog protocol**: `[READY]` claimable → `[WIP]` in progress → `[Done]` completed → `[Blocked]` waiting on input

This file replaces the legacy ticket list (Tickets 10-23) which were Phase 1-3 historical work, now superseded by the v3.0 epic structure.

---

## Sprint 0 — "Stop the Bleeding" (week 0; in progress)

The non-negotiable list. Day-1 work; no sprint-planning needed.

| Ticket | Title | Owner | Status | Notes |
|---|---|---|---|---|
| TMX-3000 | Rotate exposed OpenAI API key + history-purge `.env` via `git filter-repo` | Programme Lead (Kapil) + Auth | **[Blocked — needs Kapil]** | Kapil must rotate in OpenAI dashboard first; then Antigravity executes the filter-repo. Destructive op gated on explicit confirmation. |
| TMX-3001 | Move secrets to vault (1Password Secrets Automation or AWS Secrets Manager); GHA env injection only | Auth + Platform | **[Blocked — needs vault decision]** | Choice of vault is a Programme Lead call; see §9 D-3 |
| TMX-3002 | `.gitignore` *.db, *.log, .env, debug_*, *.txt artefacts; `git rm --cached` historical artefacts | Platform | **[WIP]** — `.gitignore` updated; `git rm --cached` deferred to Kapil confirmation | New .gitignore covers all classes; ratchet metric `hygiene.committed_db_files` etc. unchanged until rm is run |
| TMX-3003 | Force `AUTH_MODE != none` in production (refuse to start); break build on default `SECRET_KEY` | Auth | **[Done]** 2026-05-10 | `app/core/config.py:Settings.assert_production_safe()` raises `InsecureProductionConfigError` when `app_env != "dev"` and (`secret_key` is in `_INSECURE_SECRET_KEYS` OR `auth_mode == "none"`). Called from `get_settings()` so misconfigured non-dev deployments crash at first import. Default `secret_key` dropped from `"change-me-in-production"` to `""` (still caught by guard). 14 regression tests in `tests/test_config_production_safety.py`; foundation 43/43 + ratchet 17/17 green. See `.context/loops/TMX-3003.md`. Closes the 2026-05-09 audit lying-backlog finding. |
| TMX-3004 | Strip mock-data fallback from `app/review/[jobId]/page.tsx`; replace with explicit error UX | Frontend | **[Done]** | `MOCK_TRANSLATIONS`, `SOURCE_SENTENCES`, `getMockSegments` removed. Both fallback paths replaced with explicit error state. Console.log noise stripped. |
| TMX-3005 | Strip admin-fallback in `lib/auth.tsx`; replace with retry / re-auth UX | Frontend | **[Done]** | Both dev-admin fallback paths removed (`fetch.catch` + `autoLoginNoAuth.catch`). Backend unreachability now surfaces as null user. |
| TMX-3006 | Fix `tailwindcss-animate` import in `tailwind.config.ts`; get the frontend build green | Frontend | **[Done]** | `require('@tailwindcss/typography')` replaced with ESM `import typography from "@tailwindcss/typography"`. Verify with `cd frontend && npm run build`. |
| TMX-3007 | Add `SECURITY.md`, incident-response runbook stub, privacy notice | Pilot/GTM | **[Done]** | `SECURITY.md`, `docs/incident_response.md`, `docs/privacy_notice.md` all written. Counsel review pending before pilot signing (TMX-4001). |
| TMX-3008 | Stand up Dependabot + gitleaks pre-commit + secret scanning in GHA | Platform | **[Done]** | `.github/dependabot.yml`, `.github/workflows/secret-scan.yml` (PR + push + nightly), gitleaks already in `.pre-commit-config.yaml`. |
| TMX-3009 | CI gates: backend pytest + frontend build + ESLint + secret scan; PRs blocked on failure | Platform | **[Done]** | `.github/CODEOWNERS` + `docs/branch_protection.md` document the required-status-checks. Kapil applies in GitHub UI. |

**Sprint 0 exit gate**: TMX-3000, TMX-3001, TMX-3002 all complete. Then Sprint 1 starts.

---

## Sprint 1 — "Foundations everyone else needs" (weeks 1-2)

**Status**: Not started. Depends on Sprint 0 completion + steering decisions.

| Ticket | Title | Owner | Size | Sprint |
|---|---|---|---|---|
| TMX-3010 | Add `organizations` table + tenant model | Auth | M | 1 — **[Done]** c0ac3a3 — see `.context/loops/TMX-3010.md` |
| TMX-3011 | Add `organization_id` to all domain tables | Auth | M | 1 — **[Done]** bf58ae4 — see `.context/loops/TMX-3011.md` |
| TMX-3012 | Tenant-scoped session factory | Auth | M | 1 — **[Done]** c68a1b4 — see `.context/loops/TMX-3012.md`. AC-6/8 split to TMX-3012b. SHA backfilled by TMX-3060. |
| TMX-3013 | Auth0 / Keycloak integration; OIDC + SAML; MFA enforced | Auth | L | 1-2 |
| TMX-3015 | Soft-delete columns + filter logic | Auth | M | 1 — **[Done]** 349838a — see `.context/loops/TMX-3015.md`. SHA verified on origin/main by TMX-3060. |
| TMX-3100 | `audit_events_v2` schema + migration | Audit | M | 1 — **[Done]** 7022f49 — see `.context/loops/TMX-3100.md`. SHA backfilled by TMX-3060. |
| TMX-3700 | DOCX ingestion v2 with tracked-changes preservation | Pipeline | L | 1 — **[Done]** b043075 — see `.context/loops/TMX-3700.md`. SHA backfilled by TMX-3060. |
| TMX-3701 | Round-trip DOCX export with revision-mark preservation (export side) | Pipeline | M | 2 — **[Spawned by TMX-3700]** |
| TMX-3702 | Reviewer-frontend UX for accept/reject revisions | Frontend | M | 2 — **[Spawned by TMX-3700]** (TMX-3606 unblocked) |
| TMX-3703 | Differential rendering (current vs. proposed) | Frontend | M | 2 — **[Spawned by TMX-3700]** (TMX-3606 unblocked) |
| TMX-3603-* | /workspace/jobs/[id] page chain | Frontend | M | 1 — **[Done]** in Loop 27 chain (7ed25d3, ea6c7d9, cfb0032, 729a66b, c93c6a6). `/workspace/jobs/[id]` page with overview/translate/review modes; agent-activity-by-job endpoint; live AgentLanes; ActivityFeed = dashboard hero. |
| TMX-3604 | Migrate `/design-system` under `/workspace/*` | Frontend | XS | 1 — **[Done]** (c7c4e6c + 252a4ad). Legacy page deleted; 308 redirect; e2e test. |
| TMX-3617 | Rename `middleware.ts` → `proxy.ts` (Next.js 16 deprecation) | Frontend | XS | 1 — **[Done]** (0f21dc3). |
| TMX-3616-auth0 | Server-issue cookies via Auth0 with httpOnly + add CSRF tokens | Frontend + Auth | M | 2 — **[Spawned by TMX-3616 partial close; blocked on TMX-3013 Auth0 wiring]** |
| TMX-3704 | `<w:moveFrom>` / `<w:moveTo>` semantic handling | Pipeline | S | 2 — **[Spawned by TMX-3700]** |
| TMX-3704-pairing | Capture `w:id` on move marks for cross-block correlation | Pipeline | XS | 2 — **[Done]** 9e53928 — see `.context/loops/TMX-3704-pairing.md`. SHA backfilled by TMX-3060. |
| TMX-3702-a11y | Dynamic aria-label on RevisionIndicator (direction + magnitude) | Frontend | XS | 2 — **[Done]** 7ee4441 — see `.context/loops/TMX-3702-a11y.md`. SHA backfilled by TMX-3060. |
| TMX-3603-jobs-id-err | Surface real fetch errors on workspace jobs page (A3 fix) | Frontend | XS | 2 — **[Done]** c7d7473 — see `.context/loops/TMX-3603-jobs-id-err.md`. SHA backfilled by TMX-3060. |
| TMX-3604-assets-err | Surface real fetch errors in Trust Center Assets view (A3 fix) | Frontend | XS | 2 — **[Done]** 517a547 — see `.context/loops/TMX-3604-assets-err.md`. SHA backfilled by TMX-3060. |
| TMX-3705-glossary-err | Surface glossary fetch failures in upload form (A3 fix) — NB: prefix collides with parent TMX-3705 (Pipeline / file-type sniffing); this is a Frontend upload-UX sub-ticket, NOT a child of file-type sniffing | Frontend | XS | 2 — **[Done]** e2ac305 — see `.context/loops/TMX-3705-glossary-err.md`. SHA backfilled by TMX-3060. |
| TMX-3603-agents-err | Surface agent-activity poll errors on workspace jobs page (A3 fix; completes the page's error triad alongside doc + segments) | Frontend | XS | 2 — **[Done]** 418cbc5 (+ active_tasks-backfill `c0d886d`) — see `.context/loops/TMX-3603-agents-err.md`. Pushed to origin/main by TMX-3060 reconciliation. |
| TMX-3604-doc-review-err | Surface fetch errors on document review page (A3 fix; final ticket of the silent-fallback sweep) — NB: prefix collides with parent TMX-3604 (design-system migration) | Frontend | XS | 2 — **[Done]** 9c3adca — see `.context/loops/TMX-3604-doc-review-err.md` |
| TMX-3604-delete-toast | Surface delete-job failures via toast (A3 mutation-error class; first ticket pivoting from fetch-sweep) | Frontend | XS | 2 — **[Done]** c6f87a0 — see `.context/loops/TMX-3604-delete-toast.md` |
| TMX-3604-save-toast | Surface segment-save failures via toast (A3 mutation-error class; HITL-correction audit-event path) | Frontend | XS | 2 — **[Done]** 1836924 — see `.context/loops/TMX-3604-save-toast.md` |
| TMX-3604-download-toast | Surface download failures via toast (A3 mutation-error class; covers JobsView + documents/[id] download buttons in one commit) | Frontend | XS | 2 — **[Done]** fae481d — see `.context/loops/TMX-3604-download-toast.md` |
| TMX-3604-tools-toast | Surface tools-page action failures via toast (5 sites; closes the mutation-error sweep) | Frontend | XS | 2 — **[Done, pending commit + push]** — see `.context/loops/TMX-3604-tools-toast.md` |
| TMX-3705 | File-type sniffing + size cap + AV scan trigger | Pipeline | M | 1 — **[Done]** dc4795c — see `.context/loops/TMX-3705.md`. SHA backfilled by TMX-3060. |
| TMX-3706 | Deeper DOCX vs XLSX vs PPTX disambiguation (peek inside ZIP for `[Content_Types].xml`) | Pipeline | S | 2 — **[Spawned by TMX-3705]** |
| TMX-3707 | AV scanner integration (clamd / Cloud DLP) — wire `emit_av_scan_request` to actual scanner | Pipeline + Platform | M | 2 — **[Spawned by TMX-3705]** |
| TMX-3708 | Wire `validate_and_save_upload` into endpoints.py + knowledge.py upload routes | Pipeline | XS | 2 — **[Spawned by TMX-3705]** |
| TMX-3800 | Sentence segmenter service skeleton + interface | Pipeline | M | 1 — **[Done]** a67ad04 — see `.context/loops/TMX-3800.md`. SHA backfilled by TMX-3060. |
| TMX-3801 | NLTK / spaCy / pragmatic-segmenter backend integration | Pipeline | M | 2 — **[Spawned by TMX-3800]** |
| TMX-3802 | Language-specific segmenters for ZH/JA/KO (CJK boundary rules differ) | Pipeline | M | 2 — **[Spawned by TMX-3800]** |
| TMX-3803 | Stable segment IDs (storage-layer; A5 follow-up) | Pipeline + Auth | L | 2 — **[Spawned by TMX-3800]** |
| TMX-3200 | Prompt registry directory layout + loader | Agent | M | 1 — **[Done]** fdeb256 — see `.context/loops/TMX-3200-3201.md`. SHA backfilled by TMX-3060. |
| TMX-3201 | Migrate `prompts.py` constants to v1.0.0 YAML files | Agent | M | 1 — **[Done]** fdeb256 — bundled with TMX-3200 in same loop. SHA backfilled by TMX-3060. |
| TMX-3204 | Wire `lang_instruction` into graph.py + batch_translator.py | Agent | XS | 1 — **[Done]** 3575845 — see `.context/loops/TMX-3204.md`. SHA backfilled by TMX-3060. |
| TMX-3212 | Audit timestamp bug fix (datetime UTC ISO) | Agent | XS | 1 — **[Done]** 5bfafd3 — see `.context/loops/TMX-3212.md`. SHA backfilled by TMX-3060. |
| TMX-3600 | Pick canonical IA = `/workspace/*`; redirect map | Frontend | S | 1 — **[Done]** — shipped via TMX-3606 de-tangle (cbef01f). 308 redirects for `/document`, `/new`, `/dashboard`, `/design-system`; 308 for `/translate/:jobId`, `/review/:jobId` (TMX-3603-jobs-id tightened from 307); 307 for `/knowledge`. Legacy page files deleted in cleanup commit 252a4ad. |
| TMX-3606 | De-tangle frontend nested-git-repo | Frontend + Platform | S | 1 — **[Done]** (cbef01f) — option (b) merge into parent. History preserved at `parking_lot/frontend-pre-detangle-history.bundle`. |
| TMX-3601 | Theme unification + design tokens + brand mark | Frontend + Design | M | 1 — **[Done]** (cdef0e2) — TMX tokens in `:root` + `.dark` (AI gradient, Provenance chip, Status Lifecycle, Agent identity); brand mark at `frontend/public/transmax-mark.svg`. |
| TMX-3614 | Vitest unit + Playwright e2e suites; CI gate | Frontend + Platform | M | 1-2 — **[Done]** (1b0a2fe + Loop 27 chain). 71/71 vitest · 6/6 mocked Playwright · 14/14 live-stack integration. Lint 0/0, all rules at error. CI workflow `frontend` + `frontend-integration` jobs. |
| TMX-3615 | CSP / HSTS / X-Frame-Options / Permissions-Policy via next.config.ts | Frontend | S | 1 — **[Done]** (f46dae8) — 6 headers via `headers()`; 2 integration tests verify they ship + ride redirect destinations. |
| TMX-3616 | Cookie hardening — httpOnly Secure SameSite=Strict + CSRF tokens | Frontend + Auth | M | 1 — **[Done partial]** (48427d9) — Secure flag on https; SameSite=Lax kept (Strict breaks OAuth callbacks); removeCookie matches flag set. `httpOnly` blocked on Auth0 wiring (ADR-0003) and tracked as **TMX-3616-auth0**. CSRF tokens deferred until Auth0 lands a real session. |
| TMX-3618 | File upload validation + size cap + magic-byte sniff | Frontend + Pipeline | M | 1 — **[Done]** (570c8b4) — `frontend/lib/fileValidation.ts` mirrors backend `app/services/file_validation.py`; 50 MB cap, .pdf/.docx/.txt whitelist, magic-byte sniff. Wired into DocumentUpload with inline error UX. 10 vitest cases. |
| TMX-3900 | OpenTelemetry SDK wired across LangGraph nodes | Platform | M | 1 — **[Done]** 3dd5623 — see `.context/loops/TMX-3900.md`. SHA backfilled by TMX-3060. |
| TMX-3901 | LLM-call child spans with prompt_version/content_hash/token_usage attributes | Agent + Platform | S | 2 — **[Spawned by TMX-3900]** |
| TMX-3902 | OTLP exporter config (Honeycomb/Jaeger/Tempo) in deployment manifests | Platform | S | 2 — **[Spawned by TMX-3900]** |

---

## Sprints 2-6 — see plan

Tickets for sprints 2-6 are in `research/v3_pilot_ready_release_plan.md` §16 and §C.3. The full backlog with ACs and dependencies is in §17. Once Sprint 0 closes and the steering decisions land, this file gets the per-sprint expansion.

---

## Open decisions blocking sprint planning

Per plan §9 + §III.D — the Programme Lead (Kapil) owes:

1. **D-1 Pilot customer profile** — recommendation: 2 mid-market pharma €500M-€2B
2. **D-2 Audit anchor** — S3 Object Lock (QLDB rejected; deprecated by AWS)
3. **D-3 IdP** — Auth0 recommended; vault decision in TMX-3001
4. **D-4 LLM strategy** — hosted-only for v3.0 pilot
5. **D-5 Region** — single EU-Central
6. **D-6 Pricing** — closed by headless spec adoption: Pilot + Enterprise + Regulatory Pack
7. **D-7 Positioning** — defer to Sprint 2
8. **D-8 Open-source kit** — keep proprietary v3.0
9. **D-9 CLI lang (v3.1)** — Rust recommended
10. **D-10 Hosted review domain (v3.1)** — separated `review.transmax.io`
11. **D-11 CMK breadth** — AWS KMS only v3.1
12. **D-12 Air-gapped deployments** — not until €20M ARR
13. **D-13 Bug bounty** — Phase 2 REST + MCP via HackerOne

---

## Real eval-harness findings (Sprint 1 / loop-driven)

Two cases in `tests/evals/data/en_es/critical_safety.jsonl` failed at the start of Sprint 1, surfacing real bugs in the deterministic gates:

- **`number_001`** (TMX-3408) — `NUMERIC_MISMATCH` did NOT fire on a 10mg→100mg tamper because `SpanishPack.check_numbers` used Python `in` (substring containment), so "10" was "found" inside "100". **[Done]** 181ff7c — see `.context/loops/TMX-3408.md`. Eval moved 8/10 → 9/10. SHA backfilled by TMX-3060.
- **`good_001`** (TMX-3409) — false-positive `FREQUENCY_MISMATCH` on canonical EN→ES because `check_frequency` lacked Spanish patterns. **[Done]** fc091dc — see `.context/loops/TMX-3409.md`. Eval moved 9/10 → 10/10. All EN→ES critical-safety cases now pass. Spawned TMX-3411 (Sprint 2) for the cross-language frequency-pattern sweep covering DE/IT/PT/KO/ZH/JA/AR. SHA backfilled by TMX-3060.

### TMX-3410 — Cross-pack `check_numbers` sweep — **[Done]** 7a5ade0 (+ TMX-3410-fix d478641); SHA backfilled by TMX-3060

Closed 2026-05-07. Word-bounded `_find_missing_numbers` helper added to `BaseLanguagePack`; all 8 packs (Spanish, German, French, Portuguese, Korean, Chinese, Japanese, GenericLanguagePack) now delegate. Japanese preserves full-width digit handling via `digit_translate` arg. 13 parametrised tests in `tests/test_lang_packs_numeric_word_boundary.py`; combined 50/50 unit tests across all 4 loops. Eval 10/10. See `.context/loops/TMX-3410.md`.

---

## Verification audit follow-ups (filed 2026-05-09 from 4-agent verify-audit)

The 4-agent loop verification ran on 2026-05-09 over `HEAD~30..HEAD`. Reports archived under `docs/audit-extracts/loop-{quality-review,pytest-report,vitest-report,spec-compliance}-2026-05-09.md`. Summary: **3 GREEN + 1 YELLOW (test-runner)**. Loop discipline holding; no PAUSE warranted. Eight follow-ups filed:

| Ticket | Title | Source | Owner | Sprint |
|---|---|---|---|---|
| TMX-3012c | Complete service-layer DEFAULT_ORG_ID sweep (44 literals across 13 files) — finish what TMX-3012b (partial) started | Quality-audit Concern #1 | Auth | 2 — **[Done]** a804b09 — see `.context/loops/TMX-3012c.md`. All `organization_id=DEFAULT_ORG_ID` literals removed from `app/api/`, `app/auth/`, `app/services/`; runner now requires `org_id` kwarg and wraps the pipeline in `org_context(org_id)` so background DB writes inherit tenancy. 5 new tests (3 runner + 2 e2e). Foundation 43/43, ratchet 17/17. **Cosmetic close completed by TMX-3012d** (`d1b8ae3`) — three residual stale narrative comments removed; new regression test `tests/test_no_default_org_id_in_services.py` enforces the four-canonical-files invariant in CI. |
| TMX-3012d | Cosmetic close on the multi-tenancy sweep — remove residual `DEFAULT_ORG_ID` references outside the four canonical files (`app/models/database.py`, `app/main.py`, `app/core/database.py`, `app/models/tenant_scoped.py`) and add a regression test that walks `app/` and asserts the invariant | 2026-05-09 audit §4.1 / §6 | Auth & Tenancy | 2 — **[Done]** `d1b8ae3` — see `.context/loops/TMX-3012d.md`. Inventory: 3 REMOVE / 4 KEEP-EXPLICIT (8 lines across the 4 canonical files). REMOVEs: stale narrative comments in `app/auth/factory.py:121`, `app/api/auth.py:160`, `app/agents/runner.py:70` (no functional code touched — TMX-3012c already removed all literal arguments). New `tests/test_no_default_org_id_in_services.py` is RED on pre-fix `main`, GREEN post-fix; pattern lifts to a quality-gate rule if a 3rd such loop emerges (see spawned **TMX-3012e**). Foundation 31/31 green (audit + RBAC + blackbook 39/39 green; rule_promotion + resilience + quality_gate_thread_safety 27/27 green). Ratchet pre-existing TODO 17 vs 16 unchanged. Drift exits 0 once committed. |
| TMX-3412 | Split `quality_gate.py` (717L) into per-defect-class modules (numeric, frequency, unit, negation) — TMX-3411 already extracted frequency data; this completes the per-class split | Quality-audit Concern #2 | Quality | 2 |
| TMX-3017a | Complete C-06 unwind for the 7 init_db-only tables (`audit_records`, `chunk_translations`, `quality_reports`, `translation_glossaries`, `translation_jobs`, `translation_memory`, `users`) before TMX-3017 rationalisation — defensive FK skip in `audit_events_v2` migration is the visible symptom | Quality-audit Concern #3 | Auth + Platform | 2 |
| TMX-3618 | Add Playwright visual-snapshot test for `/workspace/design-system` page — covers TMX-3601 design-token regressions | Quality-audit Concern #4 | Frontend | 2 |
| TMX-LOOP-HYGIENE | Backfill worksheets for `9d3c4e7` (CI init_db) and `97b2935` (FK test fix) — sub-ticket fixes spawned by TMX-3011's blast; one-line worksheets with `Stage 5: N/A` per loop README | Quality-audit Concern #5 | pod-A | 2 |
| TMX-AUDIT-CLEANUP-DASH | Dashboard activity feed empty (4 tests) | Pytest-audit | Platform | 2 — **[Done]** closed by TMX-AUDIT-CLEANUP-ROUTES (same `importlib.reload` test pollution; fixing one fixed both) |
| TMX-AUDIT-CLEANUP-DOCX | DOCX round-trip: ingestion not prefixing translatable text with `TR:` — 4 tests fail in `test_docx_roundtrip.py` (paragraph-table order, header, footer, ingestion-export order). In-flight from TMX-3700 | Pytest-audit | Pipeline | 2 — **[Pod B's lane]** — flagged, not for pod-A to touch |
| TMX-AUDIT-CLEANUP-ROUTES | Test pollution: 5 `fresh_db` fixtures used `importlib.reload(core_db)` which created NEW `get_db` function objects — broke FastAPI dependency overrides in unrelated tests, manifesting as 404s on routes that ARE correctly registered. Audit diagnosis was wrong (route registration); real cause was test infra | Pytest-audit | pod-A | 2 — **[Done]** 16d4667 — see `.context/loops/TMX-AUDIT-CLEANUP-ROUTES.md`. Full suite went 11 → 4 failures. SHA backfilled by TMX-3060. |
| TMX-VERIFY-AUDIT-PROMPT-V2 | Spawned by red team of TMX-AUDIT-CLEANUP-ROUTES: extend the verify-audit Agent 2 prompt to run failing tests in ISOLATION as a pollution-screening step before bucketing root cause. Saves a future loop the diagnosis-rework | Loop hygiene | pod-A | 2 |
| TMX-3050 | Sanitise Tiptap RichTextEditor egress via DOMPurify (audit F-H03 — stored XSS) | F-H03 (2026-05-09 audit) | Reviewer Frontend | 2 — **[Done]** `05abca8` — see `.context/loops/TMX-3050.md`. New `frontend/lib/sanitizeHtml.ts` with explicit allowlist + URI-scheme guard + two-pass sanitisation; `RichTextEditor` `onUpdate` now wraps `editor.getHTML()` in `sanitizeRichTextHtml()`. 15 new vitest cases (10 negative XSS-vector + 5 positive legitimate-markup). Frontend 104/104 (was 89/89), typecheck 0, lint 0, build green, ratchet 16/17 (one pre-existing TODO regression unrelated). Spawned TMX-3050a (audit-event hook), TMX-3050b (backend HTML sanitisation), TMX-3050c (initial-load sanitisation). SHA verified on origin/main by TMX-3060. |
| TMX-3060 | Worksheet/commit drift audit + push-hygiene codification | 2026-05-09 audit §6 / Risk D | Platform & Observability | 2 — **[Done]** `6dc7081` — see `.context/loops/TMX-3060.md`. New `scripts/audit_worksheet_drift.py` (read-only CLI + advisory pre-commit hook); reconciled 7 STALE-STATE worksheets, 1 LOCAL-ONLY (TMX-3603-agents-err pushed via 418cbc5 + c0d886d), 1 MISSING-COMMIT (TMX-INTEG-15 SHA `724b276` declared); CLAUDE.md gains "End-of-loop and end-of-sprint push hygiene" section under Loop discipline. Drift script exits 0 on origin/main. |
| TMX-3045 | Remove auto-promote of high-confidence learning rules; require signed approval (C-13 / Pillar 1) | 2026-05-09 audit §5 / Risk E | Quality & Regulatory + Auth | 2 — **[Done]** `7231c7d` — see `.context/loops/TMX-3045.md`. **Reversibility: `one-way`** — Programme Lead awareness: future learning events behave differently. Auto-promote branch removed from `app/services/learning_service.py`; new `app/services/rule_promotion.py::promote_rule()` is the only path PROPOSED→ACTIVE, requiring `RULE_APPROVE` permission + non-empty reason + audit-event-before-mutation (A1). New `Permission.RULE_APPROVE` granted to ADMIN, PROJECT_MANAGER, CURATOR. Three nullable approval columns added to `translation_rules` via defensively-idempotent migration `20260510_tmx_3045_rule_approval_fields.py`. Manual curator-create paths (`POST /api/knowledge/rules`, `/rules/import`) now stamp `approved_by` from the authenticated user. Spawned **TMX-3045a** (backfill historical signatures — A1 audit gap, Programme-Lead governance call), **TMX-3045b** (capture LLM provenance per A6), **TMX-3045c** (curator promote UI), **TMX-3045d** (pin learning prompt per A8). 21 new tests in `tests/test_rule_promotion.py` (canonical C-13 regression: confidence∈{0.9, 0.901, 0.95, 1.0} all land PROPOSED, not ACTIVE). Foundation 43/43, blackbook+audit+RBAC 64/64. Ratchet 17/17 (pre-existing TODO regression unchanged). |
| TMX-3053 | QualityGateService singleton thread-safety (audit C-08 — race-prone `_initialized` flag) | 2026-05-09 audit §5 / C-08 (High) | Quality & Regulatory | 2 — **[Done]** `3ee727e` — see `.context/loops/TMX-3053.md`. Option (A) `threading.Lock` chosen over (B) `lru_cache` factory (18 callsites use the bare `QualityGateService()` constructor; (B) would have escalated reversibility to `one-way` and broken every callsite). Double-checked locking added in `__new__`, `__init__`, `_load_lang_pack` cache, and module-level `get_quality_gate_service()` accessor. Init body extracted to `_populate_initial_state()` for hookable testability without destroying the lock under test. 3 new regression tests in `tests/test_quality_gate_thread_safety.py` reproduce the race deterministically (Barrier(N) + injected sleep): 5/5 reds against unfixed code, 50/50 greens post-fix. Foundation 43/43 green; adjacent quality-gate suites 24/24 green; ratchet pre-existing TODO 17 vs 16 unchanged. Spawned **TMX-3053a** (apply same lock pattern to module-level service accessors in `app/agents/graph.py` for `_quality_gate_service` / `_db_service` / `_audit_service` — 1-line race on each cache write). C-07 (resilience.py same-shape race) explicitly out of scope per ticket spec; remains owned by TMX-3052. |
| TMX-3052 | ResilienceService circuit breaker thread-safety + Redis-ready state-store interface (audit C-07) | 2026-05-09 audit §5 / C-07 (High) | Platform & Observability | 2 — **[Done]** `fb3c8ee` — see `.context/loops/TMX-3052.md`. **Reversibility: `one-way`** — class-level `ResilienceService.resilient_llm_call` / `move_to_dlq` API replaced with instance methods accessed via `get_resilience_service()` factory; old class-level `_state` / `_failure_count` / `_last_failure_time` fields DELETED. Option (C) chosen — pluggable `CircuitBreakerStateStore` Protocol with `InMemoryStateStore` (default, `threading.Lock`-protected) and stub `RedisStateStore` (raises `NotImplementedError`, TMX-3052b will wire). Rejected (A) plain-locks (doesn't fix multi-worker drift; descope §5.3 commits to Redis) and (B) full-Redis-now (loop spec says no new dep). 3 thread-safety regression tests in `tests/test_circuit_breaker_thread_safety.py` reproduce the race deterministically (32-thread `Barrier` + injected sleep): pre-fix simulation loses 31 of 32 increments (96.9% loss); post-fix 50/50 stress green. Existing `tests/test_resilience*.py` migrated to instance API + `state_store=` injection. All callers updated: `app/agents/graph.py:336,550`, `app/services/learning_service.py:85`. 6 patches in dependent test files updated. Foundation 43/43 green; ratchet 17/17 green. Pre-existing pollution-driven failures in `test_rule_promotion` when run after `test_sprint6_safety`/`test_tm_bypass` (TMX-AUDIT-CLEANUP-ROUTES theme) are unchanged on baseline. Spawned **TMX-3052b** (wire RedisStateStore — connection pool, env-flag read, fail-loud-on-Redis-down per A3, descope §5.3), **TMX-3052c** (emit `CIRCUIT_BREAKER_TRIPPED` audit-event on CLOSED→OPEN transition — A1 audit-chain gap), **TMX-LAZY-SINGLETON-HELPER** (extract `app.core.singletons.lazy_singleton(factory)` if a 3rd copy of TMX-3053/TMX-3052 pattern lands). |

**Foundation suites stayed green** — every new TMX-3010 / 3011 / 3012 / 3015 / 3100 regression test passed (43/43); ratchet 17/17. The yellow is well-known pre-existing technical debt and in-flight work, not loop-introduced regressions.

---

## Recently completed

- Phase 0 / pre-v3 work (the legacy backlog: Tickets 10-23) — all done before 2026-05-01; superseded by the v3.0 epic structure.
- **2026-05-01**: v3.0 release plan written (`research/v3_pilot_ready_release_plan.md` Parts I + II + III). Signed off by Kapil. Parking lot at `parking_lot/deferred_features.md` registers all deferred features.
- **2026-05-01**: KP_SDLC harness bootstrapped — `CLAUDE.md`, `AGENTS.md`, skills, slash commands, hooks, ADR templates, pre-commit, `scripts/{check,setup}.sh`.
- **2026-05-01**: Ratchet system implemented — `scripts/ratchet.py`, `ratchet/baseline.json`, `.github/workflows/ratchet.yml`, README.
- **2026-05-01**: AI eval harness implemented — `tests/evals/`, golden corpus, runner, README, `.github/workflows/eval.yml`.
- **2026-05-01**: Sprint 0 safe portion executed — TMX-3002 through TMX-3009 complete; TMX-3000 and TMX-3001 blocked on Kapil.
- **2026-05-05**: Loop board stood up at `.context/loops/` with multi-agent coordination protocol. Parallel team (Pod A: Auth & Tenancy) handed off the multi-tenant DB rewrite chain (TMX-3010 → 3011 → 3015 → 3012 → 3100); see `.context/loops/HANDOFF_TO_PARALLEL_TEAM.md`. Antigravity (Pod B: Agent & AI) running TMX-3212 → eval fixes → TMX-3600 → TMX-3200/3201.
- **2026-05-05**: Loop 1 — TMX-3212 closed (committed `5bfafd3`). `app/agents/graph.py` lines 150 + 439 audit timestamps replaced with `datetime.now(timezone.utc).isoformat()`. 4 regression tests added in `tests/test_graph_audit_timestamps.py`, all passing. Ratchet 17/17 green.
- **2026-05-05**: Loop 2 — TMX-3408 closed (committed `181ff7c`). `SpanishPack.check_numbers` now word-bounded; 10mg→100mg tamper fires NUMERIC_MISMATCH. 7 new unit tests in `tests/test_spanish_pack_numbers.py`. Eval 8/10 → 9/10. Red-team surfaced TMX-3410 (cross-pack sweep, 7 other packs affected) — added to Sprint 1 backlog.
- **2026-05-05**: Loop 3 — TMX-3409 closed (pending commit). `QualityGateService.check_frequency` extended with Spanish patterns + NFKD accent-fold. 7 new unit tests in `tests/test_quality_gate_frequency.py`. Eval 9/10 → 10/10 — both real findings resolved. Spawned TMX-3411 (cross-language frequency sweep) for Sprint 2.
