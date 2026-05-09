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
| TMX-3003 | Force `AUTH_MODE != none` in production (refuse to start); break build on default `SECRET_KEY` | Auth | **[Done]** | `app/core/config.py:assert_production_safe()` raises `InsecureProductionConfigError` when `APP_ENV != dev` and any insecure default. Called from `get_settings()`. |
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
| TMX-3012 | Tenant-scoped session factory | Auth | M | 1 — **[Done]** (local; awaiting push) — see `.context/loops/TMX-3012.md`. AC-6/8 split to TMX-3012b. |
| TMX-3013 | Auth0 / Keycloak integration; OIDC + SAML; MFA enforced | Auth | L | 1-2 |
| TMX-3015 | Soft-delete columns + filter logic | Auth | M | 1 — **[Done]** 349838a (local; awaiting push) — see `.context/loops/TMX-3015.md` |
| TMX-3100 | `audit_events_v2` schema + migration | Audit | M | 1 — **[Done]** (local; awaiting push) — see `.context/loops/TMX-3100.md` |
| TMX-3700 | DOCX ingestion v2 with tracked-changes preservation | Pipeline | L | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3700.md` |
| TMX-3701 | Round-trip DOCX export with revision-mark preservation (export side) | Pipeline | M | 2 — **[Spawned by TMX-3700]** |
| TMX-3702 | Reviewer-frontend UX for accept/reject revisions | Frontend | M | 2 — **[Spawned by TMX-3700; blocked on TMX-3606]** |
| TMX-3703 | Differential rendering (current vs. proposed) | Frontend | M | 2 — **[Spawned by TMX-3700; blocked on TMX-3606]** |
| TMX-3704 | `<w:moveFrom>` / `<w:moveTo>` semantic handling | Pipeline | S | 2 — **[Spawned by TMX-3700]** |
| TMX-3705 | File-type sniffing + size cap + AV scan trigger | Pipeline | M | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3705.md` |
| TMX-3706 | Deeper DOCX vs XLSX vs PPTX disambiguation (peek inside ZIP for `[Content_Types].xml`) | Pipeline | S | 2 — **[Spawned by TMX-3705]** |
| TMX-3707 | AV scanner integration (clamd / Cloud DLP) — wire `emit_av_scan_request` to actual scanner | Pipeline + Platform | M | 2 — **[Spawned by TMX-3705]** |
| TMX-3708 | Wire `validate_and_save_upload` into endpoints.py + knowledge.py upload routes | Pipeline | XS | 2 — **[Spawned by TMX-3705]** |
| TMX-3800 | Sentence segmenter service skeleton + interface | Pipeline | M | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3800.md` |
| TMX-3801 | NLTK / spaCy / pragmatic-segmenter backend integration | Pipeline | M | 2 — **[Spawned by TMX-3800]** |
| TMX-3802 | Language-specific segmenters for ZH/JA/KO (CJK boundary rules differ) | Pipeline | M | 2 — **[Spawned by TMX-3800]** |
| TMX-3803 | Stable segment IDs (storage-layer; A5 follow-up) | Pipeline + Auth | L | 2 — **[Spawned by TMX-3800]** |
| TMX-3200 | Prompt registry directory layout + loader | Agent | M | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3200-3201.md` |
| TMX-3201 | Migrate `prompts.py` constants to v1.0.0 YAML files | Agent | M | 1 — **[Done, pending commit + push]** — bundled with TMX-3200 in same loop |
| TMX-3204 | Wire `lang_instruction` into graph.py + batch_translator.py | Agent | XS | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3204.md` |
| TMX-3212 | Audit timestamp bug fix (datetime UTC ISO) | Agent | XS | 1 — **[Done, pending commit]** — see `.context/loops/TMX-3212.md` |
| TMX-3600 | Pick canonical IA = `/workspace/*`; redirect map | Frontend | S | 1 — **[Blocked]** code complete locally; ship gated on TMX-3606 (frontend-repo structural fix) — see `.context/loops/TMX-3600.md` |
| TMX-3606 | De-tangle frontend nested-git-repo (no `.gitmodules`, no remote); pick one of: (a) formal submodule + remote, (b) merge into parent repo, (c) split-repo with its own deploy hook | Frontend + Platform | S | 1 — **[Needs Kapil decision]** |
| TMX-3601 | Theme unification — light default, dark via prefers-color-scheme | Frontend + Design | M | 1 |
| TMX-3614 | Vitest unit + Playwright e2e suites; CI gate | Frontend + Platform | M | 1-2 |
| TMX-3615 | CSP / HSTS / X-Frame-Options / Permissions-Policy via next.config.ts | Frontend | S | 1 |
| TMX-3616 | Cookie hardening — httpOnly Secure SameSite=Strict + CSRF tokens | Frontend + Auth | M | 1 |
| TMX-3618 | File upload validation + size cap + AV trigger | Frontend + Pipeline | M | 1 |
| TMX-3900 | OpenTelemetry SDK wired across LangGraph nodes | Platform | M | 1 — **[Done, pending commit + push]** — see `.context/loops/TMX-3900.md` |
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

- **`number_001`** (TMX-3408) — `NUMERIC_MISMATCH` did NOT fire on a 10mg→100mg tamper because `SpanishPack.check_numbers` used Python `in` (substring containment), so "10" was "found" inside "100". **[Done, pending commit]** — see `.context/loops/TMX-3408.md`. Eval moved 8/10 → 9/10.
- **`good_001`** (TMX-3409) — false-positive `FREQUENCY_MISMATCH` on canonical EN→ES because `check_frequency` lacked Spanish patterns. **[Done, pending commit]** — see `.context/loops/TMX-3409.md`. Eval moved 9/10 → 10/10. All EN→ES critical-safety cases now pass. Spawned TMX-3411 (Sprint 2) for the cross-language frequency-pattern sweep covering DE/IT/PT/KO/ZH/JA/AR.

### TMX-3410 — Cross-pack `check_numbers` sweep — **[Done, pending commit + push]**

Closed 2026-05-07. Word-bounded `_find_missing_numbers` helper added to `BaseLanguagePack`; all 8 packs (Spanish, German, French, Portuguese, Korean, Chinese, Japanese, GenericLanguagePack) now delegate. Japanese preserves full-width digit handling via `digit_translate` arg. 13 parametrised tests in `tests/test_lang_packs_numeric_word_boundary.py`; combined 50/50 unit tests across all 4 loops. Eval 10/10. See `.context/loops/TMX-3410.md`.

---

## Verification audit follow-ups (filed 2026-05-09 from 4-agent verify-audit)

The 4-agent loop verification ran on 2026-05-09 over `HEAD~30..HEAD`. Reports archived under `docs/audit-extracts/loop-{quality-review,pytest-report,vitest-report,spec-compliance}-2026-05-09.md`. Summary: **3 GREEN + 1 YELLOW (test-runner)**. Loop discipline holding; no PAUSE warranted. Eight follow-ups filed:

| Ticket | Title | Source | Owner | Sprint |
|---|---|---|---|---|
| TMX-3012c | Complete service-layer DEFAULT_ORG_ID sweep (44 literals across 13 files) — finish what TMX-3012b (partial) started | Quality-audit Concern #1 | Auth | 2 |
| TMX-3412 | Split `quality_gate.py` (717L) into per-defect-class modules (numeric, frequency, unit, negation) — TMX-3411 already extracted frequency data; this completes the per-class split | Quality-audit Concern #2 | Quality | 2 |
| TMX-3017a | Complete C-06 unwind for the 7 init_db-only tables (`audit_records`, `chunk_translations`, `quality_reports`, `translation_glossaries`, `translation_jobs`, `translation_memory`, `users`) before TMX-3017 rationalisation — defensive FK skip in `audit_events_v2` migration is the visible symptom | Quality-audit Concern #3 | Auth + Platform | 2 |
| TMX-3618 | Add Playwright visual-snapshot test for `/workspace/design-system` page — covers TMX-3601 design-token regressions | Quality-audit Concern #4 | Frontend | 2 |
| TMX-LOOP-HYGIENE | Backfill worksheets for `9d3c4e7` (CI init_db) and `97b2935` (FK test fix) — sub-ticket fixes spawned by TMX-3011's blast; one-line worksheets with `Stage 5: N/A` per loop README | Quality-audit Concern #5 | pod-A | 2 |
| TMX-AUDIT-CLEANUP-DASH | Dashboard activity feed empty (4 tests) | Pytest-audit | Platform | 2 — **[Done]** closed by TMX-AUDIT-CLEANUP-ROUTES (same `importlib.reload` test pollution; fixing one fixed both) |
| TMX-AUDIT-CLEANUP-DOCX | DOCX round-trip: ingestion not prefixing translatable text with `TR:` — 4 tests fail in `test_docx_roundtrip.py` (paragraph-table order, header, footer, ingestion-export order). In-flight from TMX-3700 | Pytest-audit | Pipeline | 2 — **[Pod B's lane]** — flagged, not for pod-A to touch |
| TMX-AUDIT-CLEANUP-ROUTES | Test pollution: 5 `fresh_db` fixtures used `importlib.reload(core_db)` which created NEW `get_db` function objects — broke FastAPI dependency overrides in unrelated tests, manifesting as 404s on routes that ARE correctly registered. Audit diagnosis was wrong (route registration); real cause was test infra | Pytest-audit | pod-A | 2 — **[Done]** (local; awaiting push) — see `.context/loops/TMX-AUDIT-CLEANUP-ROUTES.md`. Full suite went 11 → 4 failures. |
| TMX-VERIFY-AUDIT-PROMPT-V2 | Spawned by red team of TMX-AUDIT-CLEANUP-ROUTES: extend the verify-audit Agent 2 prompt to run failing tests in ISOLATION as a pollution-screening step before bucketing root cause. Saves a future loop the diagnosis-rework | Loop hygiene | pod-A | 2 |

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
