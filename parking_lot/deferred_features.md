# TransMax Parking Lot — Deferred-Features Registry

**Purpose**: the canonical list of every feature, capability, or work item that has been deferred from v3.0 ("Pilot Ready") to a later release, dropped permanently, or pushed to a parking lot for revisit. Created 2026-05-01 alongside the v3.0 release plan and counter-descope analysis.

**How to use this file**:

- **When picking up new work after v3.0 ships**: this is the input bucket. Promote items to a future release plan when (a) a pilot customer asks for it, (b) a regulator demands it, or (c) the trigger condition stated in the entry is met.
- **When closing v3.0**: review the "Reactivate when" column for each item. Items whose triggers have fired since deferral get promoted to v3.1 backlog.
- **When this list grows**: every new descope decision adds an entry. Never silently drop scope without a parking-lot entry.

**Source documents** (each entry cites which doc(s) introduced it):
- `R` — `Transmax_Review_and_Upgrade_Path.docx` (May 2026 review)
- `H` — `TRANSMAX_HEADLESS_AGENT_SPEC.md` (May 2026)
- `C` — `TRANSMAX_PLATFORM_CAPABILITIES_SPEC.md` v0.9 (May 2026)
- `D` — `TRANSMAX_DESCOPE_NOTE.md` (May 2026)
- `P` — `research/v3_pilot_ready_release_plan.md` (this plan, Parts I/II/III)

**Status taxonomy**:
- `defer:v3.1` — pulled from v3.0; expected target v3.1 (90 days post-v3.0 ship)
- `defer:v3.2` — Phase 2 territory (3-6 months post-v3.0)
- `defer:v3.3` — Phase 3 territory (6-12 months post-v3.0)
- `defer:Phase4+` — 12-24 months out
- `dropped` — explicitly cut, not expected to return
- `parked` — uncertain timing; revisit when trigger fires

---

## 1. Surfaces (REST / SDK / CLI / MCP / Webhooks / connectors)

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| REST API v2 (OpenAPI 3.1, OAuth 2.1, idempotency, pagination, rate limit, RFC 9457 errors) | H, P | defer:v3.1 | v3.0 E11 (TMX-3224, TMX-3225) | First partner / CRO pilot signed; or Pilot 3+ pharma asks for API access | L (~12 SP) |
| Python SDK 1.0 on PyPI (sync + async, retry, idempotency-key) | H, P | defer:v3.1 | v3.0 E11 (TMX-3227) | After REST API v2 lands | L (~10 SP) |
| TypeScript SDK 1.0 on npm | H, D | defer:v3.3 | Original Phase 1-2; descope note Phase 3 | A frontend embedded customer signs | L (~12 SP) |
| CLI binary (`transmax`) | H, D | defer:v3.3 | Original Phase 2; descope note Phase 3 | A DevOps / batch / CI customer signs | L (~10 SP) |
| MCP server hardening (bearer auth, schema parity with REST) | H, P, D | defer:v3.2 | v3.0 E11 (TMX-3228); descope note Phase 2 | MCP ecosystem matures + a customer asks for agent-to-agent integration | M (~6 SP) |
| Webhooks v1 (Ed25519 signed POST, retry up to 24h, DLQ) | H, P | defer:v3.1 | v3.0 E11 (TMX-3226) | After REST API v2 lands | M (~5 SP) |
| S3 connector v1 (object-arrived → submit job) | H, P | defer:v3.1 | v3.0 E11 (TMX-3229) | First customer asks for batch ingest | S (~3 SP) |
| SFTP connector v1 (watch folder → submit job) | H, P | defer:v3.1 | v3.0 E11 (TMX-3230) | First customer asks for SFTP delivery | S (~3 SP) |
| Customer-provided webhook receiver (inbound POST → submit job) | H, P | defer:v3.1 | v3.0 E11 (TMX-3231) | After REST API v2 + Webhooks v1 land | S (~2 SP) |
| Surface parity test harness (top 12 journeys × 4 surfaces) | H, P | defer:v3.1 | v3.0 E11 (TMX-3232) | After REST + SDK + MCP all live | M (~6 SP) |
| Review-handoff URL with SAML/OIDC federation | H, P | defer:v3.2 | Headless spec Phase 2 | First customer wants to embed our reviewer in their portal | L (~10 SP) |
| Veeva Vault PromoMats / RIM connector | H, C, D | defer:v3.2 | Phase 2 in all docs | Veeva-using pilot signs | L (~12 SP) |
| SharePoint Online connector | H, D | defer:v3.2 | Phase 2 | Microsoft-stack customer signs | M (~8 SP) |
| Documentum (D2 / xCP) connector | H, D | defer:v3.2 | Phase 2 | Documentum-using customer signs | L (~12 SP) |
| eCTD publisher connectors (LORENZ docuBridge, Extedo, EXT-DM) | H, D | defer:v3.2 | Phase 2; descope note "integration only" | First customer needs eCTD-bound dossier export | L (~15 SP per publisher) |
| Agent-to-agent registrations (Anthropic Agent SDK, OpenAI Agents SDK, LangGraph Cloud, AutoGen) | H, D | defer:v3.3 | Phase 3 | LLM orchestration platform partnership opportunity | M-L (~6 SP each) |
| Public `verify.transmax.io` page (chain-anchor verification with Merkle proofs) | H, P | defer:v3.3 | Phase 3 | After 1-year audit-chain track record + 1st regulator readout | M (~6 SP) |
| Public `trust.transmax.io` (downloadable validation bundles, status page) | H, P | defer:v3.2 | Phase 2 | Once SOC 2 Type II evidence available | M (~5 SP) |
| Self-service "validation playground" sandbox | H | defer:v3.2 | Phase 2 (Track 7 customer acceptance) | Productised SaaS path activated (vs. managed-service-first) | L (~12 SP) |
| Customer-validation council (quarterly QA-lead meeting) | H | defer:v3.2 | Phase 2 | After 3+ production customers | program (process not eng) |
| Public bug bounty (HackerOne — REST + MCP) | H, D | defer:v3.2 | Phase 2 | After SOC 2 evidence collection starts | program |

## 2. Quality / Confidence / Calibration

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Eight-signal calibrated confidence model (logprobs, COMET-22, BERTScore, chrF, TM, glossary, defect-rate, calibration prior, content-type, reviewer-agreement) | C | dropped (replaced) | Capabilities §5.2 | Replaced by 3-signal in v3.0; full 8-signal not expected to return | L+ (model-research project per descope note) |
| 3-signal composite calibrated probability + global isotonic regression | D | defer:v3.2 | Descope §5.3 #16 | Once enough reviewer-action data accumulates per language pair | M (~10 SP) |
| Per-slice MLflow-versioned calibration models per (tenant, language_pair, content_type) | C | defer:v3.3 | Capabilities Phase 2 | Per-tenant reviewer-action data sufficient for slicing | L+ (~25 SP) |
| Per-reviewer calibration / personalisation | C | dropped | Capabilities Phase 3 | NEVER — descope note §2 #5 explicitly drops as a regulator-bias-channel risk | n/a |
| Check-and-recheck regenerate-with-alternate-model loop | C | defer:v3.2 | Capabilities Phase 2 | After 3-signal confidence model lands | M (~10 SP) |
| Reviewer-agreement signal capture | C | defer:v3.2 | Signal #8 of 8-signal model | Reviewer pool exists with > 5k reviewed segments per slice | M (~8 SP) |
| BackTranslator BERTScore-based reflexion (replacing text-equality) | P (E7.6) | defer:v3.1 | v3.0 Sprint 4 | When live LLM eval suites land | M (~6 SP) |
| Drift detection + auto-rollback to prior prompt version on threshold breach | P (E9.3) | defer:v3.1 | v3.0 Sprint 5 | After prompt registry has 3+ active prompts | M (~6 SP) |

## 3. Determinism / Memory / Cost

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Determinism Library expansion to IT/PT/JA/AR (top 6 langs from descope note) | D, C | defer:v3.1 | Descope §5.3 #14 | Pilot 3+ requires those pairs | M (~4 SP per pair) |
| Determinism Library entries for ICH-harmonised wordings | C | defer:v3.2 | Capabilities §4.3 | Customer asks for ICH consent boilerplate | M (~6 SP) |
| Determinism Library entries for statistical-notation phrases (mean (SD), median [Q1, Q3], 95% CI) | C | defer:v3.2 | Capabilities §4.3 + §6.7 | TLF/CSR ingestion lands (also v3.2) | M (~6 SP) |
| Determinism Library entries for common pharmacovigilance phrases | C | defer:v3.2 | Capabilities §4.3 | Once first PV-content customer signs | S (~3 SP) |
| Fuzzy TM as RAG context (Tier 3 of 4-tier cascade) | C | defer:v3.2 | Capabilities §4.2 | After Tier 1/2 cascade live with telemetry | L (~10 SP) |
| Constraint-pack cache (TM, glossary, rule-set hash keyed) | C | defer:v3.2 | Capabilities §4.5 | After segment-result cache shows hit-rate floor | M (~6 SP) |
| Reasoning cache (segment_hash + prompt_kind + model) | C | defer:v3.2 | Capabilities §4.5 | After explanation-of-edit feature lands (also v3.2) | M (~5 SP) |
| Model routing rules engine (per-tenant per-pair model selection) | C | defer:v3.2 | Capabilities §4.6 | Once multiple LLM providers + customers want cost optimisation | L (~10 SP) |
| Per-tenant monthly LLM budget controls + 80%/100% webhook | H, C | defer:v3.1 | Headless §7.4; Capabilities §4.6 | First customer asks for budget caps | M (~6 SP) |
| Adaptive cache eviction by hit-rate × age | C | defer:v3.3 | Capabilities Phase 3 | Cache size becomes operationally painful | M (~5 SP) |
| Cross-tenant *anonymised* boilerplate library (with explicit tenant opt-in) | C | dropped | Capabilities Phase 3 | NEVER per descope note §2 #10 — politically toxic, legally fraught | n/a |
| Offline pipeline that promotes high-hit-rate fuzzy matches into Determinism Library | C | defer:v3.3 | Capabilities Phase 3 | After fuzzy TM lands and has stable hit data | L (~12 SP) |
| LLM provider prompt-caching telemetry (where supported by provider) | C | defer:v3.2 | Capabilities §4.6 | After provider abstraction supports it | M (~6 SP) |

## 4. Format Fidelity / Document Pipeline

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| OCR fallback for scanned PDFs (Tesseract / AWS Textract / Azure DocIntel) | C, D, P | defer:v3.1 | Capabilities Phase 2; descope note keeps OCR Phase 2 | First customer ships scanned-PDF pharma docs | L (~12 SP) |
| Confidence-gated OCR with escalation routing | C | defer:v3.2 | Capabilities §6.3, §6.9 | After OCR fallback lands | M (~5 SP) |
| XLSX (Excel) ingestion with cell-level segmentation | C, D | defer:v3.1 | Descope §5.2 (kept Phase 1 originally — my counter pushes to v3.1) | First customer ships translatable XLSX | M (~8 SP) |
| PPTX (PowerPoint) ingestion | C, D | defer:v3.1 | Descope §5.2 | First marketing-content customer signs | M (~8 SP) |
| HTML / XML schema-aware ingestion | C | defer:v3.1 | Capabilities §6.3 | First web-content customer signs | M (~6 SP) |
| RTF ingestion + export with TLF support | C, D | defer:v3.2 | Capabilities §6.7.4; descope note Phase 2 | First CSR/TLF customer signs | L+ (~15 SP) |
| TLF cell-level segmentation + 5-cell-type classifier (header / label / numeric / statistical / footnote) | C, D | defer:v3.2 | Descope note cuts 11 → 5; Phase 2 | First CSR customer signs | L+ (~20 SP) |
| 11-cell-type TLF classifier (header / row-label / column-label / numeric / numeric-with-marker / statistical-notation / categorical / subject-id / date-time / footnote-text / metadata) | C | dropped | Capabilities §6.7.3 | Replaced by 5-cell version per descope §2 #12 | n/a |
| Decimal-alignment preservation post-translation | C | defer:v3.2 | Capabilities §6.7.3 | After RTF/TLF lands | M (~6 SP) |
| Footnote-anchor preservation in numeric cells | C | defer:v3.2 | Capabilities §6.7.3 | After RTF/TLF lands | M (~5 SP) |
| Header propagation across page-spanning tables | C | defer:v3.2 | Capabilities §6.7.3 | After RTF/TLF lands | S (~3 SP) |
| Cross-reference preservation (Table 14.2.1.1, Listing 16.2.6.1) | C | defer:v3.2 | Capabilities §6.7.3 | After RTF/TLF lands | S (~3 SP) |
| OOML / MathML formula round-trip with structural integrity | C | defer:v3.2 | Capabilities §6.6, Phase 2 | First protocol/SAP customer signs (rare) | L (~12 SP) |
| LaTeX support for SAPs and protocols | C, D | dropped | Capabilities Phase 3 | NEVER per descope note §2 #9 — SAPs are EN-only | n/a |
| Image-of-formula OCR fallback (Mathpix Snip or equivalent) | C | defer:v3.3 | Capabilities §6.6 | After OOML/MathML lands; if customer ships image-only formulas | M (~8 SP) |
| Figures pipeline (SVG-text walking + label re-rendering for vector; OCR for raster) | C, D | dropped | Capabilities Phase 3 | NEVER as platform feature per descope §2 #11; recommend DTP partner integration | partner integration |
| IDML (InDesign) ingestion for PIL leaflets | C | defer:v3.3 | Capabilities Phase 3 | First leaflet-heavy pharma customer asks | L+ (~20 SP) |
| Markdown / reStructuredText ingestion | C | defer:v3.2 | Capabilities §6.3 | Technical-content customer signs | S (~3 SP) |
| eCTD v4.0 native publisher | C, D | dropped (repositioned) | Capabilities Phase 3; descope note "integration only" | NEVER as native; only via LORENZ/Extedo/EXT-DM integration | n/a |
| eCTD module 1 v3.1.1 mapping | H, P | defer:v3.2 | v3 plan Part I cutline | First eCTD-bound submission customer signs | L (~12 SP) |
| Locale-aware decimal / date / quotation-mark / number-grouping handling | C | defer:v3.1 | Capabilities §6.8; Phase 2 | First customer asks for non-default locale convention | M (~8 SP) |
| Signed PDF export with reviewer e-signature panel + audit-trail appendix | C | defer:v3.1 | Capabilities §6.4 | After e-signature flow lands (E2 in v3.0 partly) | M (~6 SP) |
| eCTD-ready package export (PDF/A bookmarked per Module 1/2/3) | C | defer:v3.2 | Capabilities §6.4 | First eCTD customer signs | L (~10 SP) |
| Partner-built ingestion plug-ins (Madcap Flare, Adobe FrameMaker) | C | defer:v3.3 | Capabilities Phase 3 | Customer with content in those tools signs | partner |

## 5. Rules / Knowledge Graph / Determinism Library Governance

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Six-layer rule taxonomy (L0 Regulator / L1 Industry / L2 Tenant / L3 Brand / L4 Study / L5 Reviewer) | C | dropped | Capabilities §3.2 | Replaced by 2-layer (regulator + tenant) in v3.0; descope note moves to 3-layer in Phase 1 | n/a |
| 3-layer rule system (regulator + tenant + project) | D | defer:v3.1 | Descope §5.3 #12 | After v3.0 ships and 2-layer model proves a real need for project-level | M (~10 SP) |
| L1 Industry rules (pharma-wide BID/TID/PRN, common adverse-event phrasing) | C | defer:v3.2 | Capabilities §3.2 | After 3-layer model lands | M (~8 SP) |
| L3 Brand rules (per-product / per-compound) | C | defer:v3.2 | Capabilities §3.2 | First customer with brand-specific style asks | M (~6 SP) |
| L4 Study rules (per-protocol, per-submission) | C | defer:v3.2 | Capabilities §3.2 | First clinical-content customer asks | M (~6 SP) |
| L5 Reviewer rules (documented preferences of specific reviewer) | C | dropped | Capabilities §3.2 | Reviewer-personalisation drops per descope §2 #5 | n/a |
| MedDRA / MeSH / ATC / IDMP knowledge graph | C, D | defer:v3.3 | Capabilities Phase 2; descope note Phase 3 | When customers explicitly ask for entity-aware translation | XL+ (~50 SP) |
| MedDRA license + ingestion | C, D | defer:v3.3 | Phase 3 (license $$ per descope) | Knowledge graph activates | program (license + eng) |
| IDMP / SPOR connector + MPID/PCID ingestion | C, D | defer:v3.3 | Phase 3 | Knowledge graph activates + IDMP-relevant submission customer signs | L+ (~20 SP) |
| Drug / compound entity table (INN, ATC, EDQM, IDMP MPID/PCID) | C | defer:v3.3 | Capabilities §3.4 | Knowledge graph activates | L (~12 SP) |
| Indication entity table (MedDRA preferred, ICD-10, SNOMED CT) | C | defer:v3.3 | Capabilities §3.4 | Knowledge graph activates | M (~8 SP) |
| Population entity table (ICH E14 categories) | C | defer:v3.3 | Capabilities §3.4 | Knowledge graph activates | S (~3 SP) |
| Adverse-event entity table (MedDRA LLT/PT/HLT/HLGT/SOC) | C | defer:v3.3 | Capabilities §3.4 | Knowledge graph activates + MedDRA license | M (~8 SP) |
| Glossary conflict resolver (within-layer ties + UI surfaces) | D | defer:v3.1 | Descope §3 #1 elevation | After v3.0 minimum-viable glossary CRUD ships | M (~6 SP) |
| Glossary term lifecycle (proposed → reviewed → approved → active → deprecated → archived) | C, D | defer:v3.1 | Capabilities §3.5 | First customer hits volume that needs lifecycle | M (~8 SP) |
| Term-impact telemetry (usage, override rate per term) | D | defer:v3.1 | Descope §3 #1 | After glossary lifecycle ships | S (~3 SP) |
| Bulk-edit + comment threads on glossary terms | C | defer:v3.2 | Capabilities §3 (implicit) | After glossary conflict resolver + lifecycle ship | M (~6 SP) |
| ML-assisted rule discovery from reviewer-edit history (offline pipeline) | C | defer:v3.3 | Capabilities Phase 3 | After reviewer-edit corpus reaches sufficient volume + per-tenant signing infra | L+ (~20 SP) |
| Per-brand and per-study rule packs as customer-facing artefact | C | defer:v3.3 | Capabilities Phase 3 | After L3/L4 rule layers active + customer asks | L (~12 SP) |
| Partner-built regulator-pack marketplace | C | defer:v3.3 | Capabilities Phase 3 | After 5+ regulator packs internally + partner pipeline | program |
| Auto-promotion of learnt rules at confidence ≥ 0.90 | R, C | dropped | Existing in `learning_service.py:84-88` (review C-13) | NEVER returns — descope note §2 (governance) and capabilities §3.5 explicitly remove it | n/a |
| Rule console (CRUD with approval workflow) | C, D | defer:v3.1 | Descope §5.3 #12 | After 3-layer rule system lands | L (~12 SP) |
| Ed25519 signing of approved rule sets | C, D | defer:v3.1 | Descope §5.3 #12 | After rule console + approver role | M (~5 SP) |
| Rule Approver role (new RBAC) | C | defer:v3.1 | Capabilities §8 | After rule console lands | S (~3 SP) |
| Calibration Owner role (new RBAC) | C | defer:v3.2 | Capabilities §8 | After per-slice calibration models land | S (~3 SP) |

## 6. Validation / Compliance / Certification

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Spectral + Schemathesis + Pact contract validation in CI (Track 1) | H, P | defer:v3.1 | v3 plan Part II TMX-3508 | After REST API v2 + SDK + MCP all live | M (~5 SP) |
| Surface-parity matrix testing (Track 2 — top 12 journeys × 4 surfaces) | H, P | defer:v3.1 | v3 plan E11 (TMX-3232) | After surfaces land | M (~6 SP) |
| Failure-injection suite (Track 3 — LLM 429s, vector-store down, audit-anchor unavailable) | H | defer:v3.1 | Headless §10.3 | After resilience module v2 lands | M (~6 SP) |
| Property tests on audit chain (Track 3 — fuzz over N events) | H | defer:v3.1 | Headless §10.3 | After audit ledger v2 in production for 30+ days | M (~5 SP) |
| Authn matrix tests (Track 4 — every endpoint × every auth mode) | H | defer:v3.1 | Headless §10.4 | After REST API v2 | M (~6 SP) |
| Authz matrix tests (Track 4 — every endpoint × every role × every tenant boundary) | H | defer:v3.1 | Headless §10.4 | After RBAC enforcement at every route + REST API v2 | M (~6 SP) |
| OWASP ZAP DAST gates in CI (Track 4) | H | defer:v3.1 | Headless §10.4 | After REST API v2 + browser-facing surfaces | M (~5 SP) |
| Annual external pen-test (Track 4 / 8) | H | defer:v3.2 | Headless §10.4, §10.8 | Pre-Phase 2 SOC 2 evidence collection | program |
| Locust load tests with 10% regression budget (Track 5) | H, P | defer:v3.1 | Headless §10.5; v3 plan TMX-3509 | After REST API v2 | M (~5 SP) |
| Continuous profiling in production (py-spy / pyroscope) | H | defer:v3.2 | Headless §10.5 | After Phase 2 multi-tenant scale | M (~5 SP) |
| FDA AI/ML credibility framework executed evidence | R, P | defer:v3.1 | v3 plan E10.6 | First FDA-relevant pharma submission customer signs | program (RA) |
| ISO 27001 certification (audit booked) | R, H | defer:v3.2 | v3 plan E10 / Phase 2 | After 6 months SOC 2 evidence | program (3rd-party audit) |
| ISO 27001 certified | R, H | defer:v3.3 | Phase 3 | After ISO 27001 audit + remediation | program |
| SOC 2 Type II evidence collection start (Drata or equivalent) | R, H, P | defer:v3.1 | v3 plan TMX-4012 stays | After v3.0 ships | program (RA + SecEng) |
| SOC 2 Type II report issued | R, H | defer:v3.3 | Phase 3 | After 6+ months evidence + auditor (Schellman / A-LIGN) | program |
| ISO 17100 (translation services) certification | R, H, D | defer:v3.3 | Phase 3 | After translator/reviewer competence procedure documented + cert body engaged | program |
| ISO 18587 (MT post-editing) certification | R, H, D | defer:v3.3 | Phase 3 | After ISO 17100 | program |
| ISO 13485 (medical-device QMS) certification | R, H | defer:Phase4+ | Phase 3-4 | First MDR/IVDR customer signs | program |
| Annual notified-body assessment per release (EU AI Act) | C, D | dropped | Replaced by once-for-platform per descope §2 #13 | NEVER per-release; only on material-change | n/a |
| Notified-body once-per-platform conformity assessment | D | defer:v3.2 | Descope §2 #13 | Pre 2026-08-02 EU AI Act enforcement | program (RA) |
| Trusted-timestamp authority (FreeTSA + DigiCert TSA dual) | H, P | defer:v3.1 | v3 plan E2.3 (FreeTSA only in v3.0) | After v3.0 ships; high-assurance customer asks | S (~2 SP) |
| Bug-bounty programme (HackerOne) public scope on REST + MCP | H, D | defer:v3.2 | Phase 2 | After surfaces are stable for 90+ days | program |
| Customer-validation council (quarterly QA-lead meeting) | H | defer:v3.2 | Phase 2 | After 3+ production customers | program |
| Sandbox playground for customer self-service validation | H, D | defer:v3.2 | Phase 2 | After v3.0 ships + 1st pilot completes | L (~12 SP) |

## 7. Frontend / UX

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Frontend i18n via next-intl (en/de/fr/es/ja/ar UI) | P (Part II) | defer:v3.1 | v3 plan E8.10 (TMX-3610) | First non-EN-speaking pilot reviewer | M (~8 SP) |
| RTL CSS for Arabic UI | P | defer:v3.1 | v3 plan E8.11 (TMX-3611) | After AR/JA Determinism + first MENA customer | M (~5 SP) |
| Mobile read-only review and approval surface for executives | H, P | defer:v3.3 | Phase 3 | First exec-as-approver customer signs | L (~10 SP) |
| Reviewer comparison view (alternative model outputs side-by-side) | P | defer:v3.2 | v3 plan Phase 3 originally | After multi-model routing lands | M (~6 SP) |
| Confidence-weighted diff in reviewer cockpit | P | defer:v3.2 | v3 plan Phase 3 originally | After 3-signal confidence model lands | S (~3 SP) |
| Explanation-for-edit field for the audit trail | P | defer:v3.1 | v3 plan Phase 3 originally | After basic save-and-sign matures | S (~3 SP) |
| Magic-button upload "Shazam-style" formalised (already partially done; see status.md) | P (existing) | defer:v3.1 | v3 plan A3 conformance | Revisit when reviewer cockpit is stable | M (~5 SP) |
| Storybook + design-token documentation | R | defer:v3.1 | Frontend review §4.4 | After design system v1 lands | M (~6 SP) |
| WebAuthn passkeys for e-signature (replacing TOTP) | P | defer:v3.1 | v3 plan §6.D | After v3.0 TOTP-based 2FA matures | M (~6 SP) |
| WCAG AA on every page (currently only reviewer + auth + documents + audit) | P | defer:v3.1 | v3 plan E8.13 partial | After v3.0 ships and surfaces stabilise | M (~8 SP) |

## 8. Repo / DevEx / Hygiene

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| SLSA L3 attestation + cosign-signed releases | H, P | defer:v3.1 | v3 plan TMX-3505 | Pre-SOC 2 evidence collection | M (~5 SP) |
| Reproducible builds | H | defer:v3.1 | Headless §7.8 | After SLSA lands | M (~5 SP) |
| `requirements.txt` version pinning (renovate-driven) | R | defer:v3.1 | review L4 | After v3.0 ships | S (~2 SP) |
| Dual-model layer rationalisation (`database.py` vs `translation.py`) | R | defer:v3.1 | v3 plan TMX-3017 stays in v3.0 — but full unification | After v3.0 mega-migration unwind | L (~10 SP) |
| Docker multi-stage image + non-root user + signed image attestation | R | defer:v3.1 | review L3 | After v3.0 ships | M (~5 SP) |
| Production docker-compose with secrets-via-vault + migration step on boot | R | defer:v3.1 | review L4 | After v3.0 ships | M (~5 SP) |
| `app/services/document_export.py` content-map collision risk fix (segment_id propagation) | R, P | partial in v3.0 (TMX-3701); full polish defer:v3.1 | v3 plan E4 | After in-flight DOCX work merged | M (~6 SP) |
| Frontend bundle-size CI gate | P | defer:v3.1 | v3 plan E8 | After Vitest+Playwright land in v3.0 | S (~2 SP) |
| Pyright as alternative type checker (alongside mypy) | (proposal) | parked | (none) | If mypy proves a bottleneck | S (~2 SP) |

## 9. Pricing / GTM / Operations

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Productised SaaS path (self-service, billing, support, marketing, sales) | H, D | defer:Phase4+ | Headless spec original; descope note month-13+ dual-track | Month 13 dual-track activation per descope §4.1 | program |
| Public marketing site | H, D | defer:Phase4+ | Phase 1 originally | Productised SaaS path activates | program |
| Public docs (developer portal) | H, D | defer:v3.2 | Phase 1 originally | After REST API v2 + SDK | program |
| Free-tier SDK distribution | H | defer:Phase4+ | Phase 2 originally | Productised SaaS path activates | program |
| Open-source posture for L0 rule pack | D | defer:v3.2 | Descope §8 #5 | After 3 customers signed | program |
| Open-source "TransMax Audit Kit" (LangGraph quality-gate library + prompt registry) | P | defer:v3.3 | v3 plan §9 D-8 | If LangChain partnership opportunity arises | program |
| 4-tier pricing (Foundation / Enterprise / Platform / Regulatory Pack) | H | dropped (replaced) | Headless §8 | Replaced by 2-tier (Pilot + Enterprise) + Regulatory Pack add-on per descope §3 #5 | n/a |
| US-East region deployment | H, P | defer:v3.2 | Phase 2 | First US customer signs | program (infra) |
| APAC region deployment | H, P | defer:v3.3 | Phase 3 | First APAC customer signs | program |
| BYOK (customer-managed keys) optional with surcharge | H, P | defer:v3.2 | v3 plan §9 D-4 | First customer demands BYOK | L (~12 SP) |
| Customer-managed keys via AWS KMS (full integration beyond service-managed) | H, C | defer:v3.2 | Capabilities §7.2 | After v3.0 ships + first BYOK request | M (~8 SP) |
| Customer-managed keys via Azure Key Vault | H, C | defer:v3.3 | Phase 3 | First Azure-stack customer signs | M (~10 SP) |
| Customer-managed keys via GCP KMS | H, C | defer:v3.3 | Phase 3 | First GCP-stack customer signs | M (~10 SP) |
| On-premise / air-gapped deployments | H, D | parked | Phase 3-4 originally | Per descope §2 — deferred until €20M ARR; recommend (c) hybrid (dedicated single-tenant cloud) per v3 plan §9 D-12 | program |
| ISPOR linguistic-validation graph (forward / reconciliation / back / cognitive debriefing / harmonisation / proofreading) | H, R, D | defer:v3.3 | Phase 3 | First COA/PRO customer signs | XL+ (~40 SP) |
| Cognitive debriefing capture as structured form linked to session recording | H | defer:v3.3 | Headless Phase 3 | After ISPOR graph lands | L (~12 SP) |
| Regulatory writing agents (drafting Module 2.5, IB updates, lay summaries) | H | defer:Phase4+ | Phase 4 | After 5+ pharma customers + clear demand | program (research + eng) |
| Acquisitions: linguistic-validation specialist tuck-in | H | parked | Phase 4 | M&A opportunity | n/a |

## 10. Internal / Governance / Process

| Item | Source | Status | Was scoped at | Reactivate when | Effort estimate |
|---|---|---|---|---|---|
| Trunk-based development with 2-week release cadence + biweekly customer-facing change-control notifications | R | defer:v3.1 | review §10.2 | After v3.0 release cadence settles | program |
| 24-month support window for production-tagged releases | R | defer:v3.2 | review §10.2 | After 1st production tag | program |
| Monthly external review by independent regulatory affairs adviser | R | defer:v3.2 | review §10.2 | Pre-Phase 2 SOC 2 / ISO | program |
| Quarterly internal audit | R | defer:v3.2 | review §10.2 | Pre-Phase 2 | program |
| Annual external GAMP 5 readiness audit | R | defer:v3.3 | review §10.2 | Pre-Phase 3 ISO 17100 | program |
| EU AI Act post-market monitoring dashboards | H, R | defer:v3.2 | Phase 2 | After EU AI Act conformity package signed off | M (~8 SP) |
| Per-customer drift detection (post-market monitoring) | H | defer:v3.2 | Phase 2 | After production-customer reviewer-edit data accumulates | M (~6 SP) |
| Automatic recall of regressed prompts | H | defer:v3.2 | Phase 2 | After drift detection lands | S (~3 SP) |
| Regulator-grade public attestation (cryptographic anchoring of audit roots to public ledger) | R, H | defer:Phase4+ | Phase 4 | If marketing/regulator goodwill demands it | M (~6 SP — anchor only) + program (attestation) |
| Third-party annual attestation that audit chain has not been broken | H | defer:v3.3 | Phase 3 | After 1-year track record | program |

---

## 11. Source-Doc Cross-Walk

For traceability: every recommendation in every source doc has been classified.

| Source doc | Recommendations | In v3.0 | Deferred (this list) | Dropped | Status |
|---|---|---|---|---|---|
| `Transmax_Review_and_Upgrade_Path.docx` (May 2026) — review + Phase 0-4 roadmap | ~150 fixes + roadmap items | Phase 0 + most of Phase 1 | Most of Phase 2-4 | None | Walked entry-by-entry |
| `TRANSMAX_HEADLESS_AGENT_SPEC.md` (May 2026) — surfaces + 9-track validation + pricing | ~70 capabilities | Internal Service API extraction + canonical lifecycle + design principles only | All 6 surface adapters; Tracks 1, 2, 7, 8 of validation | None | Counter-descoped per §C |
| `TRANSMAX_PLATFORM_CAPABILITIES_SPEC.md` v0.9 — 4 pillars | ~60 capabilities | EMA QRD + EDQM term lock + 2-layer rules + Determinism Library seed (EDQM) + Tier 1/2 cascade + DOCX/PDF/XLIFF/TMX format fidelity + critical-defect overrides | Most of Pillars 1, 3 + most of Pillar 4 | 11-cell TLF, 6-layer rules, 8-signal confidence, knowledge graph, LaTeX, figures, cross-tenant boilerplate, per-reviewer calibration, auto-promotion | Counter-descoped per §C |
| `TRANSMAX_DESCOPE_NOTE.md` — corrective | 13 cuts + 5 elevations + 2 strategic decisions + 23 Phase 1 items | All 5 elevations; 18 of 23 Phase 1 items | All 13 cuts; 5 of 23 Phase 1 items I further descoped (REST API v2, Python SDK, calibration, OpenAPI source-of-truth, PPTX/HTML) | None | Adopted §B + counter-descope §C |

---

## 12. Maintenance Protocol

- **When a deferred item gets pulled into a release**: move the row to that release's plan + delete from this file. If the trigger fired, note the trigger date in the commit.
- **When a new descope decision is made**: add a row here in the same shape. Cite which doc and which section.
- **When a "dropped" item gets reactivated** (rare): explain in commit why the prior decision was wrong; move row out of "dropped" status.
- **When v3.0 ships**: review the entire file and identify v3.1 candidates. The "Reactivate when" column tells you which triggers to test.

---

*Maintained as part of `research/v3_pilot_ready_release_plan.md`. The plan describes what we ship; this file describes what we deliberately don't.*
