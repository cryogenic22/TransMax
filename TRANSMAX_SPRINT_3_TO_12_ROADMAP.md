# Transmax — Sprint 3 to Sprint 12 Roadmap

**Status:** Forward plan after Sprint 2 ten-loop chain (closed 2026-05-10)
**Audit basis:** Direct code-level verification of TMX-3003 / 3050 / 3045 / 3052 / 3053 / 3500 / 3101 / 3107
**Deadline anchor:** EU AI Act high-risk obligations apply 2 August 2026
**Owner:** Product Management — Pharma Translation Agent
**Audience:** Programme Lead, Engineering Lead, Regulatory Affairs Lead, Steering
**Principle:** Solid and functional. We build what a pharma pilot will actually use, not what is architecturally satisfying.

---

## 1. Code-Level Verification of Sprint 2

I read the actual files for the seven highest-impact loops. Verdict: the Sprint 2 chain is genuine, production-grade engineering. The team did not write feel-good code; they wrote regulator-defensible code. Specific verifications:

**TMX-3003 — production guard.** `app/core/config.py` now defines `InsecureProductionConfigError(RuntimeError)`, a frozen `_INSECURE_SECRET_KEYS` set including the empty string, and `Settings.assert_production_safe()` that raises on placeholder `secret_key` or `auth_mode == "none"` whenever `app_env != "dev"`. The guard runs once via the `@lru_cache`d `get_settings()` so any backend importer crashes at first import in a non-dev deployment. The default `secret_key` is now `""`, which is itself in the placeholder set — so omitting the env var is a fail-closed default. The "lying-backlog" gap from the 2026-05-09 audit is genuinely closed; the active_tasks row no longer outpaces the code.

**TMX-3101 — audit writer v2.** `app/services/audit_writer_v2.py` ships a canonical chained-hash writer with a 92-byte preimage: 20-byte domain tag + 8-byte little-endian sequence index + 32-byte previous hash + 32-byte payload hash. Canonical JSON with `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`, `allow_nan=False`. Genesis is the all-zero pattern, which is detectable and domain-separates from any real SHA-256. Concurrent writers handled via `(job_id, sequence_index)` UNIQUE plus retry-on-IntegrityError. The docstring explicitly cites C-04 closure and addenda A1, A3, A4, A6.

**TMX-3107 — daily Merkle anchor builder.** `app/services/audit_anchor.py` implements an RFC 6962-style tree with `0x01` leaf prefix and `0x02` internal-node prefix to defeat the CVE-2012-2459 second-preimage attack on duplicate-leaf trees. Pluggable `AnchorObjectStore` Protocol so the storage backend (S3 Object Lock at production, in-memory at test) is swappable without touching the algorithm. Algorithm ID is pinned (`transmax.merkle.v1`) and recorded in the manifest so verifiers know which spec they are verifying. Empty-day anchors emit `merkle_root = "00"*32` as a positive assertion of "no events" rather than silently skipping.

**TMX-3045 — signed promote_rule.** `app/services/rule_promotion.py` is the only sanctioned path from `PROPOSED` to `ACTIVE` for translation rules. New `Permission.RULE_APPROVE`. Audit event written before row mutation in the same transaction. Idempotent-or-raise on already-active rules ("a curator wouldn't click promote twice"). The auto-promote branch in `learning_service.py` is gone. C-13 closed.

**TMX-3050 — DOMPurify.** `frontend/lib/sanitizeHtml.ts` ships a strict allowlist (block + inline + tables only); strips every `on*` event handler, every `javascript:` / `data:` / `vbscript:` / `file:` / `blob:` URI, every `<script>` / `<iframe>` / `<object>` / `<embed>` / `<link>` / `<meta>` / `<style>`. SVG and MathML are stripped by `USE_PROFILES=html`-only. Wired into `RichTextEditor.tsx` `onChange` so segment edits are sanitised before they POST. F-H03 closed; the explicit "no silent fallback" comment matches addendum A3.

**TMX-3052 — circuit breaker.** Refactored from class-level globals to instance-based with a pluggable `StateStore` Protocol. Default in-memory store for tests; Redis-backed store deferred to TMX-3052b but the seam is in place. Pre-fix was lost 31/32 increments under contention; post-fix is 50/50 atomic. C-07 closed.

**TMX-3053 — quality gate singleton.** Double-checked locking with `threading.Lock` in `__new__` / `__init__`. Pre-fix was 16× duplicate language-pack loads under contention; post-fix is 50/50 atomic single-load. C-08 closed.

**TMX-3500 — regulatory pack scaffold.** `regulatory_pack/` directory with templates for URS, FS, IQ, OQ, PQ; `generators/traceability.py` walks `.context/loops/`, `tests/`, and `git log` to produce a typed `TraceabilityMatrix`; `generators/pack_builder.py` is the CLI entry. Signature blocks deliberately empty in templates — humans sign at release time, not the generator.

The discipline observation in the team's own summary is borne out: every loop wrote a failing test first (G2), every stage 6 ran the 22-item Tier 2 plus A1–A10 audit, every commit shipped a self-review block, every worksheet has all eight stages filled. The drift script (`scripts/audit_worksheet_drift.py`) is real and exits non-zero on `MISSING-COMMIT` / `LOCAL-ONLY` / `STALE-STATE`; the team's report of 55/55 worksheets resolving to commits on `origin/main` is verifiable.

**Three honest concessions on what the chain did *not* do.** First, the new audit writer (TMX-3101) ships, but no production code calls it yet. `app/services/rule_promotion.py:116–117` deliberately uses v1 `AuditService.log_event` with a docstring note that TMX-3110 (call-site swap) will rewrite it. The verify-chain endpoints in `app/api/v1/audit.py`, `app/api/endpoints.py`, and `app/api/v1/translations.py` all still call `AuditService().verify_chain_integrity` — the v1 verifier. So **C-04 is half-closed: the v2 cryptography is correct, but the production audit trail is still v1 string-concatenation until call-sites swap and v1 entries are migrated forward.** Second, the daily Merkle anchor builder is in place but no scheduler runs it yet (TMX-3107d) and no S3 Object Lock backend is wired (TMX-3107a) and no public verification page exists (TMX-3107c). Third, the regulatory pack scaffold builds markdown but does not yet render PDFs, capture signatures, emit a signed audit event for pack creation, or run as a CI artefact per release (TMX-3500a–e). These are the right next-sprint items; they are also why the audit ledger and validation pack are not yet pilot-credible despite the cryptography being right.

The ratchet drifted from 16 to 18 TODOs without an issue tag — the team flagged it as `TMX-AUDIT-RATCHET-TODO-SWEEP`. Honest, but worth catching before it becomes a habit.

---

## 2. Where the Platform Genuinely Stands

Sprint 2 closed seven of the ten Critical findings on the May audit list. The platform now has, verifiably:

* Multi-tenancy with row-level security enforcement, soft-deletes everywhere, signed rule promotion, a domain-separated chained-hash audit writer, an RFC 6962 Merkle anchor, production-mode safety guards, sanitised reviewer input, instance-based thread-safe circuit breaker and quality gate, a versioned prompt registry, an OpenTelemetry tracing scaffold, a sentence segmenter that closes the C-11 naive split, file-upload validation client and server, DOCX tracked-change ingestion, security headers, a unified `/workspace/*` IA, six accessible review-surface components with full Vitest coverage, a Playwright e2e harness, and a regulatory pack scaffold.

It does not yet have, in production-credible form:

* End-to-end audit trail (call-sites still v1; verifier still v1; TSA absent; daily anchor not scheduled; verification page absent).
* Auth at the edge (Auth0 blocked on D-3 sign-off).
* DOCX round-trip with revision preservation on the export side.
* PDF ingestion beyond pypdf (no OCR, no table extraction).
* Translation memory cascade (exact-match exists; fuzzy-RAG, Determinism Library, segment-result cache absent).
* Calibrated confidence model (signals captured; calibration model and check-and-recheck loop absent).
* EMA QRD validators (regulatory profiles list section names; no enforcement).
* EDQM Standard Terms (not ingested).
* Validation pack productionised (scaffold exists; PDF rendering, signature workflow, CI artefact, signed audit event absent).
* Per-tenant rate limit, per-job cost ceiling enforcement, per-tenant monthly budget.
* Multi-region deployment (single environment).
* SOC 2 Type II evidence collection started, ISO 27001 audit booked, HIPAA BAA template, GDPR DPA published.
* EU AI Act conformity package (technical documentation, model cards, post-market monitoring) — drop-dead 2 August 2026.

**That last item dictates the calendar.** The EU AI Act high-risk obligations apply on 2 August 2026, twelve weeks from now — six two-week sprints. Sprints 3 through 7 must produce a defensible conformity package alongside the rest of the work. Anything that does not contribute to either pilot signing or AI-Act conformity belongs in Sprint 8+.

---

## 3. The Discipline — What "Solid and Functional" Means

Five rules govern the next ten sprints. They are negotiable only if a customer or a regulator demands otherwise.

1. **Every sprint exits on a customer-visible capability or a regulator-visible artefact, not a feature.** The exit gate is "a pilot reviewer can do X" or "a regulator can verify Y", not "module Z exists".
2. **Spawned follow-ups have a budget.** A loop may spawn at most two follow-ups; the rest go to `parking_lot/deferred_features.md` and are revisited on schedule.
3. **No new architectural primitive without three concrete callers.** A protocol, a base class, a factory, a hook, a registry, a generic — none of them ship until at least three real call-sites need them. (Today's pluggable `AnchorObjectStore` and `StateStore` are correct because each has at least two callers in scope.)
4. **A "deferred" item is reviewed every sprint planning, not every loop.** The descope discipline avoids re-litigating the same battles.
5. **A test that is failing because the feature is WIP is `@pytest.mark.skip` until the feature lands**, not failing the suite. Eleven yellow tests in the May audit cluster were already triaged; close out before Sprint 3 starts.

Items already on the descope list — TypeScript SDK, CLI, full MCP hardening, knowledge graph, per-reviewer calibration, LaTeX, cross-tenant boilerplate, figures pipeline, multi-region beyond single EU, BYOK / on-prem, self-service onboarding, billing — stay descoped.

---

## 4. Sprint-by-Sprint Plan

Each sprint is two weeks. The team is 8–10 engineers plus QA, RA Lead, PM, Designer, half-time SecEng. Velocity assumed at 8–12 medium tickets per sprint.

### Sprint 3 — Close the Audit Ledger End-to-End

**Goal.** Every audit-emitting code path writes to v2; every verifier reads v2; the daily anchor runs on a schedule and lands on signed S3 Object Lock; a public verification endpoint exists. C-04 fully closed.

**Exit gate.** A regulator can hit `GET /api/v1/audit/v2/verify?org_id=X&job_id=Y` and receive `{verified: true, sequence_count: N, merkle_proof: ...}` for a real translation job, signed by a trusted timestamp authority.

**Deliverables.**
- TMX-3110 swap call-sites in `rule_promotion.py`, `app/api/endpoints.py`, `app/api/v1/audit.py`, `app/api/v1/translations.py`, and `app/agents/graph.py` from v1 `AuditService.log_event` to v2 `AuditWriterV2.write`. Add a regression test that asserts no production code path imports the v1 logger.
- TMX-3104 chain verifier (`verify_chain_v2(org_id, job_id) -> VerifyReport`) — recomputes the chain head, compares to stored, returns structured pass/fail.
- TMX-3105 verifier endpoint `GET /api/v1/audit/v2/verify`.
- TMX-3103 trusted-timestamp wrapper (FreeTSA per ADR-0002 phase 1; plug-in interface for DigiCert later).
- TMX-3107a S3 Object Lock backend wiring (governance mode, retention 7 years, MFA delete).
- TMX-3107c public verification page (`/verify` route or a separate `verify.transmax.io` per descope §8 D-10).
- TMX-3107d daily anchor scheduler (APScheduler or similar; Sprint 4 candidate to harden).
- TMX-3109 v1→v2 historical migration (one-time pipeline that recomputes v2 hashes over v1 entries; documented as a single-run ops artefact).
- TMX-3050a sanitiser audit event (every sanitisation event lands on the audit chain so anomalous reviewer input is forensically visible).
- TMX-3052c circuit-breaker tripped audit event.

**Not in scope.** Tamper-detection alarming, third-party periodic chain attestation (Sprint 12), Postgres advisory-lock optimisation (TMX-3101a — defer until 100+ events/sec is observed).

**Risks.** v1→v2 migration is the riskiest single piece. Prefer to keep v1 entries readable forever rather than rewrite them — the migration produces a v2 chain seeded from a v1 boundary marker, not a destructive overwrite.

### Sprint 4 — Authentication and the Reviewer End-to-End

**Goal.** A real user signs in via their corporate IdP, uploads a DOCX, edits a segment, signs off, and the sign-off lands on the v2 audit chain bound to their identity.

**Exit gate.** A scripted pilot run takes a 10-segment SmPC excerpt from upload to signed-off in under five minutes with full audit verification.

**Deliverables.**
- TMX-3013 Auth0 wiring — OIDC plus SAML; session timeout 12 hours; MFA enforced. Unblocked by D-3 sign-off (recommended Auth0 per ADR-0003).
- TMX-3616-auth0 — backend issues `Set-Cookie: transmax_token=...; HttpOnly; Secure; SameSite=Strict`; CSRF tokens for all mutating endpoints.
- TMX-3620 reviewer save-and-sign UX — modal capturing reviewer attestation, reason, and timestamp; POST to `/api/v1/segments/{id}/sign-off`; signed audit event on the v2 chain.
- TMX-3702v2 segment-level revision accept-or-reject persistence per ADR-0004 (the column add).
- TMX-3045a curator UI for rule promotion (replaces the manual API call; lists `PROPOSED` rules, captures reason, calls `promote_rule()`).

**Not in scope.** SCIM v2 user provisioning (Phase 1.5), federated logout (defer), step-up MFA on critical actions (Sprint 8 candidate).

**Risks.** Auth0 tenant migration if region picks change; minimised by exposing only OIDC-standard interfaces in our code.

### Sprint 5 — DOCX Round-Trip and Format-Fidelity QA Gate

**Goal.** A reviewer can export the translated DOCX, open it in Word, and the formatting (bold, italic, lists, tables, footnote markers, sub/superscripts) is preserved. Format-fidelity defects are visible in the quality gate.

**Exit gate.** Round-trip a real SmPC: pre-translation DOCX byte-checksum the format-only XML elements, post-translation DOCX format-XML preserved, no orphan ins/del/move tags, table-cell count match, list-item count match, no symbol drift.

**Deliverables.**
- TMX-3701 DOCX export with revision preservation. Round-trip test against a corpus of ten real anonymised SmPCs (sourced from EMA's public SmPC repository).
- TMX-3702-counts-export — extend per-type revision-mark counts to the export side (consistency with ingestion).
- TMX-3704-export — `<w:moveFrom>` / `<w:moveTo>` round-trip on export with `w:id` correlation.
- Format-fidelity QA gate — `app/services/quality_gate/format.py` checks placeholder count match, table cell count match, list item count match, figure anchor preservation, symbol presence (Unicode allow-list).
- PDF/A-1b export — embedded fonts; archival format for regulators.
- Eleven-test cleanup loop — close the four DOCX round-trip failures, the four dashboard-feed failures, and the three unmounted-endpoint failures from the May audit.

**Not in scope.** RTF (TLF format), XLSX, PPTX, IDML, MathML / OOML formula handling. All Sprint 9 candidates.

**Risks.** Reviewer-edited segments must round-trip without losing the format applied by Tiptap; the sanitisation allowlist must be a strict superset of what python-docx round-trip can re-emit.

### Sprint 6 — Translation Memory Cascade and Determinism Library

**Goal.** A pre-approved EDQM Standard Term in source produces a byte-identical translation in target without a single LLM call. Determinism KPI starts at zero and rises week-on-week.

**Exit gate.** Demo a SmPC excerpt translated end-to-end; report Determinism KPI (segments resolved without LLM); show byte-stable identical output across two runs of the same input plus glossary plus profile.

**Deliverables.**
- TMX-32xx Determinism Library schema (`determinism_library_entry`) + signing workflow + lookup index.
- TMX-32xx EDQM Standard Terms ingestion as an L0 layer entry pack (subscribe to the EDQM database; bulk-import dosage forms, routes of administration, units of presentation, container types).
- TMX-32xx EMA QRD section-title canonical phrases as an L0 entry pack (six top language pairs).
- TMX-32xx Tier 1 / Tier 2 cascade in the `compile_constraints` LangGraph node — Determinism Library probe first, exact-match TM second, LLM only as fallback.
- TMX-32xx Segment-result cache (`(tenant_id, language_pair, source_segment_hash, glossary_hash, rule_set_hash, profile_hash, prompt_version, model)` → translation).
- TMX-32xx Pre-translation deduplication (identical segments translated once per job, propagated).
- TMX-32xx Determinism KPI report on the `/workspace/audit` page.

**Not in scope.** Fuzzy-RAG TM context (Sprint 8), constraint-pack cache, reasoning cache, model routing rules, cross-tenant boilerplate library.

**Risks.** Determinism Library curation overhead; mitigated by importing EDQM bulk and signing in batches under the existing rule-approver workflow.

### Sprint 7 — EMA QRD Validators, EDQM Lock, OTLP Exporter

**Goal.** A translated SmPC that omits a mandatory QRD section is rejected at the quality gate. EDQM standard terms are hard-locked. Production telemetry lands in a real backend.

**Exit gate.** Demo a "broken" SmPC missing section 4.3 ("Contraindications"); the quality gate emits a Critical defect and blocks sign-off. Show OTLP traces in Honeycomb (or chosen exporter) for a complete translation job.

**Deliverables.**
- TMX-32xx EMA QRD section-presence validator — for each supported language pair, asserts every translated SmPC contains every mandatory QRD section in canonical order.
- TMX-32xx EDQM standard-terms hard-lock — segment-level enforcement; failure is a Critical defect.
- TMX-32xx EDQM drift report — a customer-facing artefact showing terminology adherence percentage per release.
- TMX-3902 OTLP exporter wired (Honeycomb recommended for time-to-value; ADR needed).
- TMX-3901 LLM-call child spans with `prompt_version`, `content_hash`, `token_usage` attributes.
- TMX-3500a regulatory pack PDF rendering (URS / FS / IQ / OQ / PQ → PDF/A-1b).
- TMX-3500b signature workflow (Programme Lead, RA Lead, Quality Lead — 3-of-3 signed).
- TMX-3500c regulatory pack audit event on the v2 chain.

**Not in scope.** IDMP product-identifier validation (defer to Sprint 11+), MDR/IVDR labelling rules, ICH harmonised wordings library expansion beyond what Sprint 6 imports.

**Risks.** QRD spec complexity per language; mitigated by treating Sprint 7 as English-source first, EU language pair second, others as Sprint 8+.

### Sprint 8 — Confidence Calibration, Check-and-Recheck, EU AI Act Conformity v1

**Goal.** Reviewer escalation tier follows a calibrated probability. Critical-defect overrides bypass confidence. EU AI Act conformity package v1 is published in the trust centre.

**Exit gate.** Two AI Act artefacts: (a) the model card per LLM × language pair is auto-generated from JobConfigSnapshot metadata; (b) the post-market monitoring dashboard shows defect rate, drift rate, and reviewer-edit rate for the trailing 30 days. The conformity package PDF is signed and downloadable.

**Deliverables.**
- TMX-32xx three-signal confidence model — TM match score, glossary adherence, severity-weighted defect rate.
- TMX-32xx single global isotonic-regression calibration — trained on reviewer-accept-without-edit ground truth captured since Sprint 4.
- TMX-32xx tiered review thresholds — `>=0.95` auto-approve, `0.85–0.95` light review, `0.70–0.85` full review, `<0.70` dual review.
- TMX-32xx critical-defect override — negation, number, unit, drug-name, dose-frequency, polarity defects bypass confidence and route to mandatory dual review.
- TMX-32xx check-and-recheck loop — when signal disagreement exceeds threshold, regenerate with an alternate model; compare; escalate if delta is material.
- TMX-32xx EU AI Act conformity package v1 — technical documentation, model cards, risk-management system, post-market monitoring metrics, instructions for use. Auto-rendered per release.
- TMX-32xx FDA AI/ML credibility framework artefact pack — context of use, model risk, credibility plan, executed evidence, controls, post-market monitoring (companion to AI Act package).

**Not in scope.** Per-slice calibration models (Sprint 11+), per-reviewer calibration (dropped per descope), back-translation as a confidence signal (defer; expensive).

**Risks.** Calibration ground truth thin for the first month; mitigated by starting Sprint 4 with reviewer-action capture so by Sprint 8 there are 4–8 weeks of evidence.

### Sprint 9 — Format Fidelity Breadth: PDF, RTF/TLF, MathML

**Goal.** Three more formats round-trip with format fidelity. A real CSR with TLFs translates without numeric-cell drift.

**Exit gate.** A regulator-realistic CSR (text + appendix tables) is ingested, translated, exported. Numeric cells are byte-identical between source and target. Footnote anchors preserved. Statistical-notation phrases ("mean (SD)", "n (%)", "95% CI") hit the Determinism Library.

**Deliverables.**
- PDF (digital) ingestion with `pdfplumber` + `pypdfium2`; table extraction via Camelot; reading-order recovery.
- PDF (scanned) OCR fallback via AWS Textract or Azure Document Intelligence (per platform pick); confidence-gated escalation.
- RTF ingestion and export — primary TLF source format.
- TLF cell-level segmentation with five cell types (header, label, numeric, statistical-notation, footnote).
- Decimal precision preservation per column in numeric cells.
- Footnote-anchor preservation across translation.
- Statistical-notation Determinism entries seeded for top six language pairs.
- OOML / MathML formula handling — detect at ingestion, decompose, lock operators / numerals / units / variable symbols, re-emit on export.
- Locale-aware handling — decimal separator, date format, quotation marks, list punctuation.

**Not in scope.** XLSX, PPTX, IDML, LaTeX, figures/SVG re-rendering. All deferred per descope.

**Risks.** OCR cost on scanned PDFs; mitigated by OCR-only-on-demand and confidence threshold.

### Sprint 10 — Cost Governance, Per-Tenant Rate Limits, Production Ops

**Goal.** A pilot customer cannot accidentally burn €10,000 of LLM budget overnight. Production SLOs are measurable. Releases ship a signed validation bundle.

**Exit gate.** Show the per-tenant cost dashboard. Trigger a runaway by force-feeding 100k segments; the per-job cost ceiling pauses the job at €250 and emits `tenant.budget.threshold_reached`. Show the signed validation bundle for the latest release tag.

**Deliverables.**
- Per-tenant rate limiting (leaky-bucket, per scope).
- Per-job cost ceiling enforcement (already in submit; harden at every LLM call site).
- Per-tenant monthly cost budget; webhook events at 80% and 100%.
- Model routing rules engine — cheap model for high-confidence pre-cached content, frontier model for novel content.
- Token telemetry per segment per node per model in JobConfigSnapshot.
- TMX-3500d CI-bundled validation pack (auto-built per release tag).
- TMX-3500e OQ pytest-json + PQ eval-json auto-attached to validation pack.
- Sentry (or equivalent) wired for production error tracking.
- Daily Merkle anchor scheduler hardened with retry, monitoring, and dead-letter alerting.

**Not in scope.** BYOK / customer-managed keys (Phase 2 per descope), HSM integration, mTLS optional path.

**Risks.** Rate-limit interactions with batch translation; mitigated by per-scope buckets and explicit "burst plus sustained" thresholds.

### Sprint 11 — Pilot Onboarding and First Customer Sandbox

**Goal.** Two named pilot customers (D-1 sign-off) have working sandbox tenants loaded with anonymised pharma corpora; their QA teams can run the 25-scenario acceptance test pack independently.

**Exit gate.** Both customer QA leads run the acceptance test pack against their sandbox; both return signed acceptance certificates. SOC 2 Type II evidence collection starts.

**Deliverables.**
- Pilot customer onboarding playbook (consultant-facing under the managed-service-first descope).
- Sandbox tenant provisioning — region-pinned (EU-Central per D-5), CMK off (Phase 2), full feature set including Regulatory Pack add-on.
- Acceptance test pack — 25 scenarios covering upload, translate, review, sign-off, audit verify, evidence export, format-fidelity, terminology lock, EMA QRD validation.
- Vendor security questionnaire response (CAIQ-Lite).
- HIPAA BAA template, GDPR DPA template.
- Sub-processor list.
- Onboarding telemetry — time-to-first-signed-segment, time-to-first-validated-export.
- SOC 2 Type II evidence collection started (Drata or Vanta wired); evidence window opens.
- ISO 27001 audit booked with a recognised body (BSI / DNV / SGS).

**Not in scope.** ISO 13485 (only required if MDR/IVDR customers — defer until they appear), ISO 17100 / 18587 audit (Sprint 12+), public bug bounty (Phase 2).

**Risks.** Customer QA capacity; mitigated by the structured 25-scenario pack and a paired-running mode where ZS consultants execute alongside.

### Sprint 12 — Pilot Expansion, Validation Discipline, and Sprint Reset

**Goal.** Pilot customers in production. The next sprint planning takes the lessons learned from real customer use and re-baselines the backlog.

**Exit gate.** Both pilot customers using transmax in their regulatory operations for at least one real submission. SOC 2 Type II evidence window 60% complete. Three concrete improvements in the backlog from customer feedback.

**Deliverables.**
- Pilot customer #1 first signed translation pack.
- Pilot customer #2 first signed translation pack.
- Customer-validation council convened — quarterly cadence.
- Quarterly customer-facing changelog with breaking-change advisories and validation-impact statements.
- Sprint-13 onwards re-baselined from customer evidence.
- ISO 17100 process documentation drafted (translator and reviewer competence; revisions procedure; full-vs-light post-editing per ISO 18587).
- Public bug bounty scope drafted (HackerOne or Bugcrowd; REST + MCP only initially).

**Not in scope.** Productised SaaS conversion (managed-service-first holds for 12 months per descope), self-service onboarding, billing system, public marketing site.

**Risks.** Real customer usage will surface defects we haven't seen. Sprint 12 includes a 30% buffer for emergent fixes.

---

## 5. Cross-Sprint Themes

**EU AI Act conformity tracks Sprint 3 → Sprint 8.** Every sprint contributes one artefact to the conformity package (audit chain v2 → model cards → post-market monitoring → risk-management system → instructions for use). Sprint 8 publishes v1 of the package; Sprint 11 attaches it to the pilot acceptance materials. Sprint 12 reviews against any AI Act guidance updates issued since.

**Validation pack tracks Sprint 5 → Sprint 10.** Every sprint adds one component (URS template → FS template → IQ template → OQ template → PQ template → PDF rendering → signature workflow → CI artefact → audit event). Every release after Sprint 10 ships the bundle automatically.

**Determinism KPI tracks Sprint 6 → Sprint 12.** Customer-visible metric. Starts at 0% (every segment hits an LLM); rises to a target band of 50–70% by Sprint 12 as the Determinism Library expands and the segment-result cache fills. Reported on the audit page and on per-customer dashboards.

**Test suite to green tracks Sprint 5 → Sprint 7.** The 11 yellow tests from the May audit close out in Sprint 5 (DOCX export side fixes). Anything that becomes yellow because of a new feature is `@pytest.mark.skip` until the feature ships.

**Deferred items reviewed at Sprint 8 and Sprint 12 planning, not at every loop.** Saves the team from re-litigating the same descope decisions.

---

## 6. Pilot Readiness Criteria

A pilot customer signs when **all** of the following hold. Sprints 3–11 ship them in order.

1. SSO via the customer's IdP works end-to-end (Sprint 4).
2. A real DOCX (their content) ingests with format and tracked-changes preservation (Sprints 3 + 5).
3. A real DOCX exports with format and revision preservation (Sprint 5).
4. Quality gates fire on a curated set of safety defects in their language pair (Sprints 3 + 7).
5. EMA QRD section-presence validators pass on a real SmPC sample of theirs (Sprint 7).
6. Audit chain end-to-end verifiable via a single API call; signed by a TSA; daily Merkle anchored to S3 Object Lock (Sprint 3).
7. Validation pack signed and PDF-rendered for the release tag they will use (Sprint 7 + 10).
8. EU AI Act conformity package v1 published (Sprint 8).
9. Per-tenant rate limit and per-job cost ceiling visible on a dashboard (Sprint 10).
10. Vendor security questionnaire passes; HIPAA BAA available; GDPR DPA published; SOC 2 evidence-collection started (Sprint 11).
11. 25-scenario acceptance test pack signed off by their QA team (Sprint 11).

If any of items 1–8 slip past 2 August 2026, the EU AI Act compliance posture has to absorb the slip.

---

## 7. Decisions Owed Before Sprint 3 Starts

Three Programme-Lead decisions are still owed and gate downstream work. Each has a recommendation in the existing ADRs and the descope note; only the signature is missing.

1. **D-3 IdP** — Auth0 per ADR-0003. Without this, Sprint 4 cannot start. *Sign this week.*
2. **D-5 Region** — Single EU region, Frankfurt or Dublin per descope §8. Without this, Auth0 tenant region cannot be picked, deployment specs cannot be drawn, GDPR DPA cannot be finalised. *Sign this week.*
3. **D-1 Pilot accounts** — Two named mid-market pharma per descope §4.1. Without this, Sprint 11 cannot start customer-specific sandbox provisioning. *Sign by end of Sprint 4.*

Two further decisions can wait but should be parked for Sprint 6 planning:

4. **Observability backend** — Honeycomb vs Tempo vs Grafana Cloud (recommendation: Honeycomb for time-to-value; ADR needed). Sprint 7 depends.
5. **OCR vendor** — AWS Textract vs Azure Document Intelligence vs on-prem Tesseract (recommendation: Textract under D-5 if AWS region; ADR needed). Sprint 9 depends.

---

## 8. Things to NOT Build

The Sprint 2 chain succeeded partly because the team did not chase scope. The next ten sprints maintain the same discipline. Explicitly out of scope until Sprint 13+:

| Capability | Why not | When to reconsider |
| --- | --- | --- |
| TypeScript SDK | Customer engineering in pharma is Python and Java | Phase 3, after three production customers |
| CLI binary | DevOps buyers do not exist in regulatory and clinical teams | Phase 3, on customer demand |
| Full MCP server hardening (auth, scopes, idempotency at MCP transport) | Ecosystem still nascent in 2026; will not move pilots | Phase 2, when an MCP customer asks |
| Knowledge graph with MedDRA / IDMP / MeSH | Licensed datasets, integration heavy, no TMS competitor offers in 2026 | Phase 3, with first MDR/IVDR customer |
| Per-reviewer confidence calibration | Pharma reviewers are designed to be interchangeable | Drop entirely |
| LaTeX support for SAPs and protocols | SAPs are written in English and stay in English | Drop entirely |
| Cross-tenant anonymised boilerplate library | Politically toxic; legally fraught | Drop entirely |
| Figures pipeline with SVG-text walking and label re-rendering | DTP work, not translation work; partner integration cheaper | Phase 3, with figure-heavy customer |
| Multi-region deployment beyond single EU | Pilot customers are EU; US in Phase 2 | Phase 2, at second-region customer |
| BYOK / on-prem deployment | Customers above €20M ARR | Phase 3 |
| Self-service signup, billing, marketing site | Managed-service-first holds for 12 months | Phase 2 |
| Public bug bounty scope wider than REST + MCP | Phase 2 | After SOC 2 Type II issued |
| `quality_gate.py` per-defect-class split (TMX-3412) | Cosmetic; module is 717 lines but functional | Sprint 13+, only if a defect class can't be added cleanly |
| Mega-migration `430291da76c3` unwind (TMX-3017) | GAMP 5 traceability of new schema is in place; old schema is stable | Sprint 14+, only if a mid-migration schema change is needed |
| Postgres advisory-lock optimisation on audit writer (TMX-3101a) | Premature; unobserved load | Sprint 13+, when 100+ events/sec is observed |
| OTel child spans on every LangGraph node | Costly span volume | Sprint 13+, when cost telemetry is the bottleneck |
| Per-slice calibration models with MLflow | Per-tenant evidence thin | Sprint 13+, when six months of reviewer behaviour is captured |

When a customer asks for any of these, the answer is "yes, in the next phase, here's the trigger." When the team asks, the answer is "what customer-visible capability does this deliver this sprint?"

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| EU AI Act conformity package not ready by 2 August 2026 | Medium | High | Sprints 3–8 carry one AI Act artefact each; v1 of the conformity package publishes in Sprint 8 |
| Auth0 sign-off slips past Sprint 3 planning | Medium | High | ADR-0003 is signed material; recommend a 30-minute decision sync this week |
| Pilot customer profile not picked by Sprint 5 | Medium | Medium | ZS account leadership identifies three accounts; descope note recommends two mid-market pharma at €500M–€2B |
| Audit v1→v2 historical migration corrupts old chain | Low | High | One-time non-destructive migration; v1 entries readable forever; v2 chain seeded from boundary marker |
| OCR quality breaks pharma scanned PDFs | Medium | Medium | Confidence-gated escalation; below-threshold PDFs route to human; never silently translate |
| Validation pack signature workflow blocks releases | Medium | Medium | 3-of-3 signers required; configure Slack notifications; SLA 24 hours |
| Format-fidelity QA gate flags too many false positives | Medium | Medium | Severity bands (Critical / Major / Minor); only Critical blocks; per-tenant tuning of thresholds |
| Determinism Library curation overhead | Medium | Low | EDQM bulk import; EMA QRD canonical phrases pre-bundled; signing in batches under existing approver workflow |
| Calibration ground truth thin for first month | High | Low | Single global model first; per-slice models only when slice has 5,000+ reviewer actions |
| Sprint scope drift from customer feedback after Sprint 11 | High | Medium | Sprint 12 carries a 30% emergent-fix buffer; customer-validation council quarterly |

---

## 10. Recommended Immediate Actions

In the next 48 hours:

1. Sign D-3 (Auth0). Recorded in `.context/lead_decisions.md`. Unblocks Sprint 4.
2. Sign D-5 (EU region). Recorded in `.context/lead_decisions.md`. Unblocks Sprint 11 region picks and downstream Auth0 tenant configuration.
3. Push the ratchet TODO drift fix (`TMX-AUDIT-RATCHET-TODO-SWEEP`) before Sprint 3 starts — keeps the metric green.
4. File the Sprint-3 tickets per Section 4. Link each to the worksheet template.
5. Ask the team to choose between this roadmap's Option (a) (run a fresh four-agent verify-audit over `HEAD~30..HEAD`) and Option (c) (pause for review) — given Sprint 2 closed cleanly with 55/55 worksheets reconciled to `origin/main`, Option (c) followed by Sprint 3 kickoff is the higher-leverage call.

Within the next two weeks (before Sprint 3 closes):

6. Sign D-1 (pilot customer accounts). Two named accounts.
7. ADR-0005 — choose observability backend (Honeycomb recommended).
8. ADR-0006 — choose OCR vendor (Textract recommended if AWS).
9. ADR-0007 — choose region operator (AWS or Azure for EU-Central).
10. Pilot customer outreach scheduled — by end of Sprint 4, both target accounts in NDA + scoping conversation.

---

## 11. Closing

The Sprint 2 chain is the work of a team that has internalised the loop discipline. The cryptography is right, the multi-tenancy primitive is sound, the regulatory pack scaffold is in place, the reviewer surface is sanitised, and the lying-backlog item is honestly closed. None of this was inevitable; many teams ship velocity without depth.

The next ten sprints turn that depth into a customer-signable platform. The principle is unglamorous: every sprint exits on a customer-visible capability or a regulator-visible artefact. Sprint 3 finishes the audit ledger. Sprint 4 puts a real reviewer in front of a real document. Sprint 5 closes the round-trip. Sprint 6 reduces the LLM bill. Sprint 7 enforces regulatory presence. Sprint 8 publishes the AI Act package. Sprint 9 takes on the format breadth. Sprint 10 hardens production. Sprint 11 onboards the first two customers. Sprint 12 takes feedback and re-baselines.

If the team holds the descope discipline — if they do not build the TypeScript SDK or the knowledge graph or the per-reviewer calibration just because they could — then by end of Sprint 12 transmax is what the May review hoped for: an agentic-first, pharma-native, regulator-defensible translation platform with real customers, real attestations, and a credible roadmap to category leadership.

The chain that closed last week is the proof that the team can do this. The next ten sprints are the work.

---

*End of roadmap.*
