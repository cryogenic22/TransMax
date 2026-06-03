# Transmax — Code and System Audit

**Status:** Audit at end of Sprint 1 (T+9 days from v3.0 plan sign-off)
**Audit date:** 2026-05-09
**Audited HEAD:** `7ee4441` *TMX-3702-a11y: dynamic aria-label surfaces direction + magnitude*
**Owner:** Product Management — Pharma Translation Agent
**Audience:** Programme Lead, Engineering Lead, Regulatory Affairs Lead, Steering
**Companion documents:** *Transmax — Code Review and Enterprise Upgrade Path* (Word, May 2026); *Headless Agent Spec*; *Platform Capabilities Spec*; *Descope Note*; *v3.0 Pilot Ready Release Plan* (research/)

---

## 1. Headline

In nine days the team has shipped 68 commits, four ADRs, four Alembic migrations (where there was one), a multi-tenancy primitive, a soft-delete primitive, an audit-events-v2 schema, a versioned prompt registry, a real sentence segmenter, file-upload validation, OpenTelemetry tracing scaffolding, a unified `/workspace/*` IA, a six-component design system with full Vitest coverage, security headers, file-upload validation on the frontend, a DOCX tracked-change ingestion pipeline, and a reviewer surface that surfaces revision metadata with full accessibility. They have also instituted a credible loop-driven discipline: per-ticket worksheets in `.context/loops/` (37 of them), Architecture Decision Records (`docs/decisions/0001–0004`), a four-agent verification audit run on 2026-05-09 (archived in `docs/audit-extracts/`), a ratchet that gates regressions, and an evaluation harness that has already caught and fixed real safety bugs (TMX-3408, 3409, 3410). This is exemplary execution against the v3.0 plan.

It is not, however, complete — and, more importantly, the active backlog board contains at least one self-report that the code does not support. Sprint 0 is *not* closed in code, even though `.context/active_tasks.md` marks it so. Six critical May findings remain genuinely open. The audit-events-v2 *schema* has shipped but the *writer* that uses domain-separated chained hashing has not, so the production audit trail is still v1 string-concatenation. The learning service still auto-promotes rules at 0.90 confidence (C-13). The circuit breaker is still class-level mutable global state (C-07). The quality-gate singleton is still race-prone (C-08). And approximately 100 files of work are sitting in the local working tree without having been pushed to `main`, which means CI has not validated them and the canonical baseline is stale.

The verdict is: **disciplined and substantive progress, but with two corrections owed and two real risk areas.** The corrections — closing Sprint 0 honestly and pushing the local commits — are a one-day exercise. The risk areas — getting the audit ledger writer (TMX-3101) and the four open critical findings into Sprint 2 — are the most important programme decisions for the next 14 days.

---

## 2. Programme Discipline — What Is Working

The shape of the engineering organisation has changed in nine days, and that is the most under-appreciated achievement.

**Loop-driven development is real.** Every substantive commit has a `.context/loops/TMX-NNNN.md` worksheet. The worksheets follow eight stages (Task / Spec / Design / Code / Eval / Red-team / Fix / Deploy). I spot-checked TMX-3012, TMX-3700, TMX-3410, TMX-3614, TMX-3601: each had stages 1–7 filled with care, including a stage-6 red-team that explicitly spawned follow-up tickets when gaps emerged. The pattern of disciplined-explicit-partial (TMX-3012 → TMX-3012b → TMX-3012c) is exactly what the loop discipline asks for. Stage 8 (Deploy) is where the slack is — see Section 5 below.

**Architecture Decision Records are real decisions.** ADR-0002 (secrets management) commits to a phase-tiered vault strategy with explicit Phase 2 / Phase 3 triggers. ADR-0003 (auth provider) settles on Auth0 for Phase 1 with explicit lock-in mitigation and a fallback path. ADR-0004 (revision-decision persistence) walks through three options and chooses the smallest reversible change. None of these is boilerplate; each has clear consequences and named alternatives.

**The team audited itself.** The four-agent verification audit on 2026-05-09 produced four reports (`docs/audit-extracts/loop-{quality,pytest,vitest,spec-compliance}-2026-05-09.md`). Every audit verdict is honest: GREEN on quality, GREEN on frontend, YELLOW on backend tests (11 failures triaged), GREEN on spec-vs-delivery (18 Match, 1 Partial-explicit, 0 Drift). The reports name follow-up tickets and acknowledge concerns. This is the kind of programme self-policing that turns a project from a sprint board into a system.

**Eval harness is producing real defects.** TMX-3408 and TMX-3409 found genuine bugs in `spanish.py` and `quality_gate.py` — a substring-containment numeric check that missed a `10mg → 100mg` tamper and a missing Spanish frequency-pattern set that produced false positives. Both fixes shipped production code plus regression tests; the eval suite moved 8/10 → 10/10 on EN→ES safety. The follow-up TMX-3410 cross-pack sweep replaced eight near-duplicate `check_numbers` implementations with a single `_find_missing_numbers` helper using a `(?<!\d)X(?!\d)` digit-only-boundary regex — the single best refactor in the window.

**Ratchet is gating regressions.** `scripts/ratchet.py` blocks any commit that regresses any of seventeen metrics. When `quality_gate.py` crossed an 800-line ceiling under TMX-3411, the ratchet forced an extraction of `quality_gate_frequencies.py`. That is exactly how anti-bloat is meant to work.

**Migrations are now versioned.** The May review flagged the single mega-migration `430291da76c3` as a GAMP 5 traceability violation. Today there are four further versioned migrations (`20260505_tmx_3010_add_organizations.py`, `20260507_tmx_3011_add_org_id_fk.py`, `20260507_tmx_3015_add_soft_delete.py`, `20260509_tmx_3100_audit_events_v2.py`). Each is idempotent and downgradable. The mega-migration itself is not yet split, but the discipline for new schema is in place.

**Frontend test harness is real.** Eleven Vitest files covering `RevisionIndicator`, `AIMoment`, `ProvenanceChip`, `StatusLifecycle`, `AgentLanes`, `ActivityFeed`, `DefectTrace`, `StatusBadge`, `permissions`, `utils`, and `fileValidation`. Two Playwright e2e specs (`landing.spec.ts`, `segments-revisions.spec.ts`). The `RevisionIndicator` test alone has 56 test cases covering accessibility direction-and-magnitude labels, count thresholds, and back-compatibility with old payloads. This is not boilerplate.

**IA is now canonical.** `next.config.ts` defines 308 redirects from every legacy route (`/document/:docId`, `/translate/:jobId`, `/review/:jobId`, `/new`, `/knowledge`, `/design-system`) to `/workspace/*` equivalents. The legacy page files have been deleted. The May review's biggest frontend complaint — two parallel IAs — is closed.

That is a substantial body of work in nine days, and it is being carried out under genuine engineering discipline, not by adding code thoughtlessly.

---

## 3. Sprint 0 — Self-Reported "Done", Verified "Open"

Sprint 0 is the "stop the bleeding" list — non-negotiable safety and hygiene fixes that gate Sprint 1. The active backlog reports nine of ten Sprint 0 tickets as **[Done]** or **[WIP]**, with only TMX-3000 (key rotation) and TMX-3001 (vault decision) blocked on Programme Lead. **Code-level verification disagrees with that self-report on at least one item.**

**TMX-3003 — Force AUTH_MODE != none in production; break build on default SECRET_KEY.** Reported `[Done]` with the note that *"`app/core/config.py:assert_production_safe()` raises `InsecureProductionConfigError` when `APP_ENV != dev` and any insecure default. Called from `get_settings()`."* I read `app/core/config.py` directly. The function does not exist. `grep -rn "assert_production_safe\|InsecureProductionConfig" app/ tests/` returns nothing. There is no `.context/loops/TMX-3003.md` worksheet. `git log` against `app/core/config.py` shows the last touching commit is `0143017` from 2026-01-25 (Railway-friendly config), well before the v3.0 plan. The defaults at lines 51 and 55 are still:

```python
secret_key: str = "change-me-in-production"
auth_mode: str = "none"  # "none" | "jwt" | "oidc"
```

This is a Critical-severity gap masquerading as Done. The fix is straightforward (add a startup check that raises if `APP_ENV != dev` and either default is unchanged), but it must actually ship and be tested. **Recommendation: re-open TMX-3003 today; ship within 24 hours; correct the active_tasks.md row.**

**TMX-3000 — Rotate exposed OpenAI API key.** Confirmed Blocked on Programme Lead, as reported. ADR-0002 records that the key was rotated on 2026-05-09. The history-purge step is still pending Kapil's go-ahead (it is destructive). `SECURITY.md` still has a `<TODO: date Kapil completes TMX-3000>` placeholder. **Recommendation: schedule the filter-repo this week; until then, the repository remains a leak for the old key even though it is invalid.**

**TMX-3002 — `.gitignore` and `git rm --cached` historical artefacts.** Reported `[WIP]`. The `.gitignore` covers `.env`, `*.db`, `*.log`, `debug_*`, `*.txt`, but the `git rm --cached` step has not run. The historical .env, debug logs, and committed `transmax.db` (5.6 MB) are still in `git ls-files`. **Recommendation: run the rm-cached pass; couple with the filter-repo of TMX-3000.**

**TMX-3004 / TMX-3005 / TMX-3006 / TMX-3007 / TMX-3008 / TMX-3009.** All correctly closed. Verified:
* Mock-data fallback in `app/review/[jobId]/page.tsx` is gone (route now 308-redirects to `/workspace/jobs/[id]`; the new page renders an explicit empty/error state, no hardcoded mock translations).
* Admin fallback in `lib/auth.tsx` is gone (`autoLoginNoAuth` no longer injects a dev-admin on backend failure; null user surfaces).
* `tailwind.config.ts` uses ESM import for `tailwindcss-animate`; build is green; lint is at zero warnings against a tightening cap.
* `SECURITY.md`, `docs/incident_response.md`, `docs/privacy_notice.md` exist with real content.
* `.pre-commit-config.yaml` runs `gitleaks`, `ruff`, the quality gate, the ratchet, and red-flag attestation.
* Dependabot and a secret-scan workflow are present in `.github/workflows/`; CI gates lint plus pytest plus frontend build plus secret scan.

So the ledger reads **8 / 10 Sprint 0 truly Done; 1 / 10 Done-as-reported-not-in-code (TMX-3003); 1 / 10 Blocked-on-Kapil (TMX-3000) plus a partial (TMX-3002)**. Sprint 0 is not closed. The exit gate criterion ("TMX-3000, TMX-3001, TMX-3002 all complete") is technically blocked on the Programme Lead, but TMX-3003 needs to be reopened and shipped before Sprint 1 can honestly call itself complete.

---

## 4. Sprint 1 — Verified Delivery by Epic

Sprint 1 has shipped substantial real work across every epic. The verification below is grounded in code reads, not commit messages.

### 4.1 Auth and Tenancy (E1)

| Ticket | Verdict | Notes |
| --- | --- | --- |
| TMX-3010 organizations table | **Shipped** | Migration `20260505_tmx_3010_add_organizations.py` idempotent, seeds DEFAULT_ORG_ID, constrains `org_kind`. Model in `app/models/database.py` mixes in SoftDeleteMixin. |
| TMX-3011 organization_id FKs across domain tables | **Shipped** | Migration adds nullable column, backfills DEFAULT_ORG_ID, flips to NOT NULL plus FK across 23 tables; system tables (e.g. `language_packs`) intentionally excluded. Indexes added. |
| TMX-3012 tenant-scoped session factory | **Shipped (clean)** | `app/core/tenant_context.py` uses `ContextVar` for async-task scoping; `app/models/tenant_scoped.py` implements `_inject_org_id` (raises `TenantContextMissing` rather than defaulting — A3 compliant) and `_filter_by_tenant` (auto-injects `WHERE organization_id = current_org` via `with_loader_criteria`). 11 unit tests. |
| TMX-3012b / 3012c middleware + service-layer sweep | **Shipped (mostly)** | `TenantContextMiddleware` in `app/main.py:52–76` sets context per request. The service-layer DEFAULT_ORG_ID sweep (3012c, commit `a804b09`) removed roughly 27 of 44 transitional markers in services and the runner; some markers remain in `db_service`, `audit_service`, `learning_service`, `resilience` and a couple of routes. Functionally fine because the listener raises if no context is set; cosmetically still untidy. |
| TMX-3013 Auth0 / OIDC / SAML / MFA | **Blocked on Programme Lead D-3** | ADR-0003 settled on Auth0 for Phase 1; the team is waiting for sign-off. Until D-3 lands, no auth wiring can begin and TMX-3616-auth0 (httpOnly cookies and CSRF tokens) cannot start. |
| TMX-3015 soft-delete | **Shipped** | `app/models/soft_delete.py` ships SoftDeleteMixin (is_deleted / deleted_at / deleted_by), a `_refuse_hard_delete` listener that raises `HardDeleteRefused`, and a `_filter_soft_deleted` listener that auto-injects `WHERE is_deleted = false` unless `execution_options(include_deleted=True)`. Migration touches 24 tables. 7 tests; conversion of seven `db.delete` call-sites to `soft_delete()` confirmed. |

### 4.2 Audit Ledger (E2 / E3)

| Ticket | Verdict | Notes |
| --- | --- | --- |
| TMX-3100 audit_events_v2 schema | **Schema shipped; writer NOT shipped** | `app/models/audit_v2.py` defines `AuditEventV2` with `domain_tag`, `event_type`, `actor_kind`, `payload`, three 32-byte hash columns (`event_hash`, `payload_hash`, `previous_hash`), `event_ts_utc DateTime(timezone=True)`, optional `tsa_token`. CHECK constraints on hash lengths; UNIQUE on `(job_id, sequence_index)`. `AuditAnchor` model defined for daily Merkle anchors with S3 object reference. 10 schema tests, including an explicit regression that audit events do NOT inherit SoftDeleteMixin (correct — audit must be append-only, not soft-deletable). |
| TMX-3101 chained-hash writer | **Not started** | The migration file's docstring explicitly defers the writer ("the writer (TMX-3101), timestamps integration (TMX-3102), FreeTSA (TMX-3103), verification API (TMX-3104), daily Merkle anchor (TMX-3107) and v1→v2 migration (TMX-3109) are separate Sprint 2 tickets"). |
| TMX-3212 audit timestamps | **Partial** | The v2 schema uses per-event timezone-aware UTC columns. The v1 writer in `app/services/audit_service.py` still uses `datetime.now(timezone.utc)` per call (which is correct), but the v1 chain itself is the concerning surface — see below. |

The audit ledger is the single most important regulatory primitive in transmax. The schema is in place. **The writer is not.** `app/services/audit_service.py:60–110` still implements the v1 chain:

```python
previous_hash = "GENESIS_HASH"  # Seed for the first entry
…
payload_json = json.dumps(payload, sort_keys=True)
hash_input = f"{previous_hash}{payload_json}"
entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()
```

This is exactly the C-04 weakness from the May review: hardcoded genesis seed, string concatenation with no domain separator, no anchoring. Until TMX-3101 ships and the writer is swapped, **no audit claim survives a 30-minute expert review**. This is the most important Sprint 2 deliverable and must be sequenced first.

### 4.3 Document Pipeline and Segmentation (E4 / E5)

| Ticket | Verdict | Notes |
| --- | --- | --- |
| TMX-3700 DOCX ingestion v2 (tracked changes) | **Shipped** | `app/services/docx_ingestion.py:_collect_revisions` parses `<w:ins>`, `<w:del>`, `<w:moveFrom>`, `<w:moveTo>` from OOXML, returns counts plus author and date plus `w:id` for cross-block move correlation. Six integration sites. 9 tests. The block text uses the v2 contract (final-text mode: insertions included, deletions excluded). |
| TMX-3701 DOCX export with revisions | **Spawned, not started** | Depends on 3700. Sprint 2 work. |
| TMX-3705 file-type sniff plus size cap plus AV trigger | **Shipped** | `app/services/file_validation.py` reads the first bytes of an upload, matches against a magic-byte table (`b"%PDF-"`, `b"PK\x03\x04"`, etc.), enforces `MAX_UPLOAD_BYTES` (default 50 MB), and emits a structured AV-scan request via `emit_av_scan_request()` (clamd wiring deferred to TMX-3707). |
| TMX-3800 sentence segmenter | **Shipped** | `app/services/segmenter.py` replaces `text.split('.')` with an abbreviation-aware regex segmenter; handles `Dr.`, `e.g.`, `i.v.`, decimals (`5.5 mg` stays one segment), `?` and `!` correctly. 18 tests. NLTK / spaCy backends deferred to TMX-3801. |

The four `test_docx_roundtrip.py` failures reported by the team's pytest audit are a real concern. They cluster in header / footer / table / order extraction tests that expect a `TR:` translatable-text marker prefix that the ingestion service is not yet producing. This is the export side of the round-trip, not the ingestion side; TMX-3701 is the right vehicle. **Recommendation: ensure TMX-3701 is the first Sprint-2 Document-Pipeline ticket, behind TMX-3101.**

### 4.4 Prompts, Quality Gates, Eval (E6, E7)

| Ticket | Verdict | Notes |
| --- | --- | --- |
| TMX-3200 / 3201 / 3204 versioned prompt registry | **Shipped** | `app/agents/prompts/registry.py` loads versioned YAMLs from `app/agents/prompts/{translator,fixer,reviewer}/v*.yaml`. `PromptVersion` is a frozen dataclass carrying agent, version, system, user and content_hash. Cache plus Lock; semver `latest` resolution; SHA-256 canonical hash domain-separated by `\n---\n`. M-03 closed for prompts. |
| TMX-3408 / 3409 / 3410 / 3411 eval-driven defect fixes | **Shipped** | Two real safety defects fixed (Spanish numeric substring containment; missing Spanish frequency patterns). Cross-pack sweep collapsed eight near-duplicate `check_numbers` into a single `_find_missing_numbers` helper using a digit-only boundary regex. Cross-language frequency sweep added DE / IT / PT / KO / ZH / JA / AR. Eval moved to 10/10 on critical-safety EN→ES. |
| TMX-3412 split quality_gate.py | **Spawned, not started** | Frequency data extracted to `quality_gate_frequencies.py`; gate logic itself still in a 717-line module. Sprint 2 candidate. |

### 4.5 Frontend Surface (E8)

| Ticket | Verdict | Notes |
| --- | --- | --- |
| TMX-3600 IA consolidation | **Shipped** | 308 redirects in `next.config.ts` from every legacy route to `/workspace/*`. Legacy page files deleted. |
| TMX-3601 design tokens plus brand mark | **Shipped** | Tokens in `globals.css` (`--ai-gradient-from/to`, `--audit-chip-*`, `--status-*`, `--agent-*`); Tailwind theme extended; brand mark SVG in `public/`. |
| TMX-3602 AIMoment / ProvenanceChip / StatusLifecycle | **Shipped** | Three components, semantic HTML, accessible, themable, fully tested with `@testing-library/react`. |
| TMX-3603 jobs page chain (AgentLanes / ActivityFeed / DefectTrace) | **Shipped** | `/workspace/jobs/[id]` page with overview / translate / review tabs; backend `agent-activity-by-job/{job_id}` endpoint and hook; live polling. |
| TMX-3604 design system migrated under `/workspace/*` | **Shipped** | 308 redirect; design system page demos all components. |
| TMX-3614 Vitest plus Playwright plus CI gate | **Shipped** | 11 unit test files, 2 e2e specs, dual-webServer Playwright config (mocked plus real-backend), CI jobs gating. ESLint at 0 errors, 33 warnings (cap 65); TypeScript strict, 0 errors. |
| TMX-3615 security headers | **Shipped** | CSP, HSTS (`max-age=31536000; includeSubDomains; preload`), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy disabling camera / microphone / geolocation / payment / etc. |
| TMX-3616 cookie hardening | **Partial-explicit** | Secure flag added when on HTTPS. SameSite=Lax retained (Strict breaks OAuth callback). httpOnly and CSRF blocked on Auth0 wiring (TMX-3013 → TMX-3616-auth0). |
| TMX-3617 middleware → proxy | **Shipped** | Renamed for Next.js 16 deprecation. |
| TMX-3618 file upload validation | **Shipped** | Client-side `lib/fileValidation.ts` mirrors backend; magic-byte sniff, size cap, extension allow-list, 10 Vitest cases. |
| TMX-3700 / 3702 / 3704 reviewer surface for revisions | **Shipped** | `RevisionIndicator` component with dynamic accessible aria-labels carrying direction (moved-out / moved-in) and magnitude (count); back-compat for old payloads; 56 Vitest cases plus a Playwright e2e. ADR-0004 proposes the v2 segment-level accept/reject persistence schema. |
| TMX-3900 OpenTelemetry across LangGraph | **Shipped** | `app/services/tracing.py` provides `init_tracing()` plus `@traced(name)` decorator; six graph nodes wrapped; idempotent init; no-op when env disabled. Child spans for LLM calls and OTLP exporter wiring deferred to TMX-3901 / 3902 (Sprint 2). |

The frontend is in a healthier state than at any point I have seen since the May review. The build is green, the test harness is real, the design system is functional, the IA is canonical. The single critical gap is documented below.

---

## 5. Critical Findings Still Open

The May review identified thirteen Critical-severity backend findings (`C-01..C-13`) and seven frontend Critical findings (`F-C01..F-C05`, `F-H01..F-H07`). The team has closed approximately two-thirds of them. The remainder, as verified against the code:

| ID | Finding | Verified state today | Severity | Recommended next step |
| --- | --- | --- | --- | --- |
| C-01 | Real OpenAI key in `.env`; not purged from git history | Key rotated 2026-05-09 (per ADR-0002); history purge pending Kapil | Critical | Schedule filter-repo this week; until then the repo still leaks the dead key |
| C-02 | `secret_key` defaults to `"change-me-in-production"`; no production guard | Default unchanged; no `assert_production_safe()` exists | Critical | Re-open TMX-3003; ship within 24 hours |
| C-03 | `auth_mode` defaults to `"none"`; no production guard | Default unchanged; no production guard | Critical | Same ticket as C-02 |
| C-04 | Audit chain is hardcoded `GENESIS_HASH` plus string concatenation, no domain separator, no anchor | v2 *schema* shipped; v1 *writer* still active; chain not anchored | Critical | TMX-3101 must be the first Sprint 2 ticket |
| C-07 | Circuit breaker is class-level mutable state, not thread-safe | Confirmed at `app/services/resilience.py:52–56`, with comment "Assuming single-threaded check logic or accepting race conditions for simplicity check" | High | Refactor to `threading.Lock` or back with Redis (descope plan §5.3 calls for Redis) |
| C-08 | QualityGateService singleton has race-prone `_initialized` flag | Confirmed at `app/services/quality_gate.py:7–24`; no Lock in `__new__` or `__init__` | High | Add `threading.Lock` or refactor to instance-based |
| C-12 | PII service is regex-only with sequential-pass interference | `app/services/pii_service.py` unchanged | High | Replace with Microsoft Presidio or AWS Comprehend Medical; Phase 2 work but flag in backlog |
| C-13 | Learning service auto-promotes rules at confidence ≥ 0.90 | Confirmed at `app/services/learning_service.py:85–86`: `if confidence >= 0.90: status = "ACTIVE"` | High | Remove auto-promotion; require signed human approval (per Capabilities Spec Pillar 1) |
| F-H03 | Tiptap RichTextEditor `getHTML()` output not sanitised | Confirmed at `frontend/components/ui/RichTextEditor.tsx:83`; no DOMPurify | High | Add DOMPurify; immediate one-day patch |
| F-H06 | Long segment lists not virtualised | `app/workspace/jobs/[id]/page.tsx` renders `segments.map()` without virtualisation | Medium | TanStack Virtual once a 500+ segment document is in test corpus |
| F-M03 | Reviewer save-and-sign UX | Edits POST cleanly, but no signature / reason capture, no signed audit event | Medium | Pair with TMX-3101 audit writer so the signed event lands on the v2 chain |

Six of these are Critical or High and unaddressed in the current Sprint 1 plan. **Three of them (C-02, C-03, F-H03) are one-day patches.** The other three (C-04 → TMX-3101 writer; C-07 → Redis-backed circuit breaker; C-13 → remove auto-promotion) need Sprint 2 tickets.

---

## 6. New Issues Surfaced By Sprint 1

Most of these are positive — surfaces that were dim in May are now lit, and small problems are visible.

**Pytest 11 failures.** The team's own audit triaged these into three clusters: dashboard activity feed (4), DOCX round-trip (4), unmounted endpoints (3 — `reverse_translate`, `verify`). All three clusters are within in-flight scope, not regressions. The DOCX ones will be closed by TMX-3701 (export); the unmounted endpoints look like router-registration drift and should be a 30-minute fix. The dashboard-feed ones need investigation — could be route registration or empty-state semantics. **Recommendation: a single half-day "test-cleanup" loop in Sprint 2 closes all eleven.**

**100+ files unstaged in working tree.** Git index reports unable to read (extension corruption — see below), but `git log --oneline -10` against `origin/main` versus HEAD shows that only `7ee4441` is ahead of where the upstream was at the start of the audit window. Worksheets are marked `[Done, pending commit + push]` — meaning the team is staging work in worksheets but not pushing the commits. This is operationally fine for a single-IC environment, but it means CI has not validated the latest work and a fresh clone cannot reproduce the current state. **Recommendation: mass-push at end of every sprint; codify in CLAUDE.md.**

**Git index corruption.** `git status` and `git diff` against the local index returned `error: index uses ټ͓ extension, which we do not understand; fatal: index file corrupt` during the audit. This is a tooling issue (likely a stale or partially-written index from an interrupted command), not a data loss event. `git read-tree HEAD` will rebuild it. **Recommendation: rebuild the index before any further commits.**

**Service-layer DEFAULT_ORG_ID transitional markers.** TMX-3012c removed roughly 27; about 17 remain in `app/services/db_service.py`, `audit_service.py`, `learning_service.py`, `resilience.py`, and a few routes. Functionally harmless because the listener raises rather than defaults silently, but a hygiene loose end that should close cleanly. **Recommendation: TMX-3012d (cosmetic close) in Sprint 2.**

**`quality_gate.py` at 717 lines.** The data extraction (TMX-3411) deferred the structural split. Per the team's own quality review, this should be split per-defect-class (numeric / frequency / unit / negation / glossary / safety). Spawned as TMX-3412 but not yet sized. **Recommendation: include in Sprint 2.**

**Mega-migration `430291da76c3` not yet split.** Four further versioned migrations live alongside, but the original creates approximately 80 tables in one revision and is referenced by every Sprint 1 migration as the down-revision. GAMP 5 traceability of schema evolution is genuinely better than it was, but the original sin remains. **Recommendation: TMX-3017 unwind; Sprint 3 candidate (not blocking pilot).**

**Auto-`include_deleted=True` is the documented escape hatch for soft-delete.** This is correct. But there is no audit logging of when a query opts out of the soft-delete filter. **Recommendation: log every `include_deleted=True` execution to the audit chain (low-frequency, high-value); spawn from TMX-3015.**

---

## 7. Programme Risks

**Risk A — Steering decisions blocking critical-path work.** Three decisions (D-1 pilot customer profile, D-3 IdP provider, D-5 region) remain owed to the Programme Lead. ADR-0003 has settled D-3 on Auth0; ADR-0002 has settled secrets handling; the descope note has settled D-1 (managed-service-first, two mid-market pharma) and D-5 (single EU region, Frankfurt). The decisions are written; only the signature is missing. Until D-3 is signed, TMX-3013 cannot start, and TMX-3616-auth0 (httpOnly cookies plus CSRF) cannot ship. *Severity: Medium. Likelihood: Low (signature is hours of work). Action: sign D-1, D-3, D-5 this week.*

**Risk B — Sprint 0 not honestly closed.** TMX-3003 is reported `[Done]` but the code does not contain the claimed enforcement function. This is a discipline-level risk: if the active backlog drifts from the code, the loop discipline collapses. *Severity: High. Likelihood: ongoing if not corrected. Action: re-open TMX-3003 today; fix; correct the active_tasks.md row.*

**Risk C — Audit ledger writer is not yet shipped.** The schema is in place; the production audit calls are still using v1 string-concat hashing with hardcoded genesis. Until TMX-3101 ships, the "tamper-evident" claim is theatre at the writer level. *Severity: Critical for any pilot conversation. Likelihood: certainty until Sprint 2 lands. Action: TMX-3101 must be the first Sprint 2 ticket; allocate two engineers; no other audit-related work starts before this.*

**Risk D — Local commit backlog.** Approximately 100 files of work in the local working tree, not pushed. Worksheets across `.context/loops/` say `[Done, pending commit + push]`. CI cannot validate; baseline is stale. *Severity: Medium. Likelihood: ongoing. Action: end-of-sprint mass push; codify the practice in CLAUDE.md.*

**Risk E — Critical findings unflagged in backlog.** C-02, C-03, C-07, C-08, C-13, F-H03 are all Critical or High and not on the current Sprint 2 plan. The team appears to assume they are resolved (or their loop discipline missed them when verifying TMX-3003). *Severity: High. Likelihood: ongoing until corrected. Action: file Sprint-2 tickets for each; treat as gate items rather than nice-to-haves.*

**Risk F — Sprint scope creep.** Sprint 1 has spawned at least eight follow-up tickets from red-teams (TMX-3012b, 3012c, 3012d, 3017a, 3412, 3618 visual-snapshot, plus DOCX cleanups). This is healthy when controlled. The ratchet plus the active_tasks board are managing it well so far, but it is worth watching: by mid-Sprint 2 the spawned-ticket count could outpace the closure rate. *Severity: Low at present. Action: explicit "spawn budget" per loop (e.g. max two follow-ups; anything beyond is parked).*

---

## 8. Sprint 2 — Recommended Priorities

In strict order of importance:

1. **Re-open TMX-3003 and ship the production guard for `secret_key` and `auth_mode`.** One-day patch. Until done, Sprint 0 is not honestly closed.

2. **TMX-3101 — Audit ledger v2 writer with domain-separated chained hashing.** This is the single most important Sprint 2 deliverable. Concretely: replace the v1 writer in `audit_service.py` with one that computes `event_hash = sha256(domain_tag || sequence_index_le8 || previous_hash || payload_hash)`, where `||` is byte concatenation and `domain_tag = b"transmax.audit.v1\0"`. Add the `tsa_token` capture using a trusted timestamp authority (FreeTSA initially per ADR work; DigiCert later). Migrate v1 entries to v2 in a one-time chain (TMX-3109).

3. **TMX-3107 — Daily Merkle anchor to S3 Object Lock.** ADR-0002 plus the descope note both call for S3 Object Lock as the immutability anchor (QLDB is deprecated by AWS). Daily root, signed manifest, public verification page (`verify.transmax.io` is in the headless spec but Sprint 3 can wait).

4. **F-H03 — DOMPurify on RichTextEditor.** Add DOMPurify to sanitise `editor.getHTML()` before POST. One-day patch. Add a Vitest test that injects `<img src=x onerror=...>` and asserts it is stripped.

5. **TMX-3013 — Auth0 wiring.** Once D-3 is signed, this is a 1–2 week effort. Unblocks TMX-3616-auth0 (httpOnly cookies + CSRF). Critical-path for any pilot customer demo.

6. **TMX-3052 / TMX-3053 — Resilience and quality-gate thread-safety.** Refactor circuit breaker to instance-based with a Redis-backed shared store (descope §5.3 already commits to Redis); add `threading.Lock` to the QualityGateService singleton init or refactor it to a module-level cached factory. Both are half-day fixes.

7. **TMX-3045 — Remove learning-service auto-promotion.** Replace `if confidence >= 0.90: status = "ACTIVE"` with `status = "PROPOSED"` and require an explicit human-signed promotion via a `promote_rule(rule_id, approver_id, signature)` API. Adds a new RBAC role `RuleApprover` per the Capabilities Spec.

8. **DOCX round-trip closure (TMX-3701).** Resolve the four `test_docx_roundtrip.py` failures; ship the export side of the v2 ingestion. Without this, the DOCX flow is half-built.

9. **`quality_gate.py` split (TMX-3412).** Split the 717-line module into `quality_gate/{numeric,frequency,unit,negation,glossary,safety}.py`. Improves testability and prepares for adding EMA QRD validators in Sprint 3.

10. **Validation-pack scaffold (URS / FS / IQ / OQ / PQ).** The plan calls for these to be CI artefacts. Begin with templates and a generator that pulls test results plus AC traceability into a signed PDF per release. Required before any pilot SOW is signed.

11. **Pytest 11-failure half-day cleanup loop.** Triage the dashboard-feed failures, register the missing `reverse_translate` and `verify` routes, decide whether the DOCX round-trip failures are TMX-3701 work or test-fixture issues. Bring the suite to 100% green so future regressions are visible.

12. **End-of-sprint mass push and CI baseline anchor.** Codify in CLAUDE.md that every sprint ends with a push, a green CI run on `main`, and a `parking_lot/` archive of any unsigned worksheets.

Items 1, 4 are 24-hour tasks. Item 2 is the most significant engineering effort in Sprint 2. Items 5–12 fit in a two-week sprint with the existing team.

---

## 9. Strategic Alignment Check

The descope note recommended *managed-service-first for 12 months* and *embedded-first surface design*. The work shipped is consistent with both:

* The team has not built a self-service signup, billing, marketing site, or seat licensing — correct.
* The frontend is being built as a credible reviewer surface, not a beautiful one — correct (consistent design tokens, accessible, tested, but functional rather than novel).
* The headless surfaces (REST API v2, Python SDK, MCP server) are correctly Sprint 2+ work — TypeScript SDK and CLI are correctly deferred per the descope.
* The Regulatory Pack (URS / FS / IQ / OQ / PQ, Part 11 attestation, EU AI Act conformity) is on the plan but has not started — correct timing per the descope (Phase 2).

The Capabilities Spec four pillars are progressing in the expected order:

* **Pillar 1 (Knowledge / Rules / Black Books):** TMX-3010 / 3011 / 3012 give us tenant scope; the rule-layering work (regulator / tenant / project) and signed promotion are Sprint 3 candidates.
* **Pillar 2 (Memory / Determinism / Token Cost):** TM exact-match exists; Determinism Library is not yet started but EDQM Standard Terms ingestion is a Sprint 3 ticket; segment-result cache is Sprint 3.
* **Pillar 3 (Confidence / Check-and-Recheck / Escalation):** Three signals exist (`confidence_service.py`, `language_calibration.py`, `quality_gate.py` defects). Calibration model and back-translation and check-and-recheck loop are Sprint 3+.
* **Pillar 4 (Format Fidelity):** DOCX ingestion v2 with tracked changes is a major step. XLIFF 2.1 canonical, RTF / TLF / OOML / MathML support, OCR fallback, IDML are all Sprint 3+.

Pillars 1 and 4 are appropriately in motion; Pillars 2 and 3 are correctly deferred to Sprint 3 once the regulatory primitives (audit v2, validation pack, EMA QRD validators) are stable.

---

## 10. Top 12 Actions for the Programme Lead

In priority order:

1. **Sign D-1, D-3, D-5 today.** Pilot customer profile (two mid-market pharma); IdP provider (Auth0 per ADR-0003); region (EU-Central / Frankfurt per descope). Three signatures, one hour, unblocks TMX-3013 and the deployment specification.

2. **Re-open TMX-3003.** Ship the production guard for `secret_key` and `auth_mode` within 24 hours. Correct the active_tasks.md row.

3. **Mass-push the local commits to `main` before Sprint 2 starts.** Run `git read-tree HEAD` first to fix the index corruption, then commit and push. CI will validate; baseline anchored.

4. **Schedule the OpenAI-key history purge (TMX-3000).** Either today or alongside the mass push. Until done, the dead key is in git history.

5. **Make TMX-3101 (audit ledger v2 writer) the first ticket of Sprint 2.** Two engineers; allocate ten days; no other audit-related work in parallel until this lands.

6. **File six new Sprint 2 tickets for the verified-open Critical and High findings:** TMX-3052 (circuit breaker thread-safety), TMX-3053 (quality-gate thread-safety), TMX-3045 (remove learning-service auto-promotion), TMX-3107 (daily Merkle anchor), TMX-3045-frontend (DOMPurify on Tiptap), TMX-3071-pii (Presidio replacement, may slip to Phase 2).

7. **Cross-pod risk retro on Friday 2026-05-17.** Twenty-five minutes; review yellow audit findings, confirm spawned-ticket trail, validate spawn budget per loop.

8. **Codify the end-of-sprint push hygiene in CLAUDE.md.** Stage all work, run CI, push `main`, archive worksheets to `parking_lot/`.

9. **Begin the Regulatory Pack scaffold.** URS, FS, IQ, OQ, PQ templates plus a generator that pulls release artefacts. No ticket exists; create TMX-3500 family.

10. **Pick the OTLP exporter for OpenTelemetry.** ADR needed (Honeycomb recommended for time-to-value; Tempo if self-hosted preference). Five-minute decision; unblocks TMX-3902.

11. **Decide the validation-pack signer.** Programme Lead plus Regulatory Affairs Lead plus Quality Lead per release. Assign roles in `.context/lead_decisions.md`.

12. **Close the pytest suite to green.** Half-day loop in Sprint 2; assign to Pod B. Treat any "test failing because feature is WIP" as a hint that the test should be `@pytest.mark.skip(reason=...)` until the feature lands rather than failing the suite.

---

## 11. Closing

The team has done in nine days what most teams do in twelve weeks. The loop discipline is real, the ADRs are decisions not boilerplate, the eval harness is producing genuine defect findings, the ratchet is enforcing anti-bloat, the verification audit is honest about its YELLOW conclusions, and the frontend is in better shape than it has been at any point I have reviewed.

The two corrections owed are small. Sprint 0 has one open item that must close (TMX-3003); the local commits must be pushed; six critical findings need to land on the Sprint 2 board. None of this changes the trajectory: with a one-day correction and a focused Sprint 2, transmax can hit the v3.0 "pilot ready" target by 24 July 2026 as planned. The audit-ledger v2 writer (TMX-3101) is the single most consequential piece of remaining engineering work; everything else flows from there.

The team should know this: from the May review to today, the gap to a pharma-pilot-credible platform has narrowed by something like two-thirds. The remaining third is harder than what they have already done, but the discipline that got them this far is the right discipline to finish the job.

---

*End of audit.*
