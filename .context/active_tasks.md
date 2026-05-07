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
| TMX-3011 | Add `organization_id` to all domain tables | Auth | M | 1 — **[WIP]** |
| TMX-3012 | Tenant-scoped session factory | Auth | M | 1 |
| TMX-3013 | Auth0 / Keycloak integration; OIDC + SAML; MFA enforced | Auth | L | 1-2 |
| TMX-3015 | Soft-delete columns + filter logic | Auth | M | 1 |
| TMX-3100 | `audit_events_v2` schema + migration | Audit | M | 1 |
| TMX-3700 | DOCX ingestion v2 with tracked-changes preservation | Pipeline | L | 1-2 |
| TMX-3705 | File-type sniffing + size cap + AV scan trigger | Pipeline | M | 1 |
| TMX-3800 | Sentence segmenter service skeleton + interface | Pipeline | M | 1 |
| TMX-3200 | Prompt registry directory layout + loader | Agent | M | 1 |
| TMX-3201 | Migrate `prompts.py` constants to v1.0.0 YAML files | Agent | M | 1 |
| TMX-3212 | Audit timestamp bug fix (datetime UTC ISO) | Agent | XS | 1 — **[Done, pending commit]** — see `.context/loops/TMX-3212.md` |
| TMX-3600 | Pick canonical IA = `/workspace/*`; redirect map | Frontend | S | 0-1 |
| TMX-3601 | Theme unification — light default, dark via prefers-color-scheme | Frontend + Design | M | 1 |
| TMX-3614 | Vitest unit + Playwright e2e suites; CI gate | Frontend + Platform | M | 1-2 |
| TMX-3615 | CSP / HSTS / X-Frame-Options / Permissions-Policy via next.config.ts | Frontend | S | 1 |
| TMX-3616 | Cookie hardening — httpOnly Secure SameSite=Strict + CSRF tokens | Frontend + Auth | M | 1 |
| TMX-3618 | File upload validation + size cap + AV trigger | Frontend + Pipeline | M | 1 |
| TMX-3900 | OpenTelemetry SDK wired across LangGraph nodes | Platform | M | 1 |

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
