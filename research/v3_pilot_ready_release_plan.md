# TransMax v3.0 "Pilot Ready" — Release Plan, Backlog & Specs

**Prepared for**: Kapil Pant (CEO)
**Prepared by**: Antigravity (Program Lead)
**Date**: 2026-05-01
**Status**: Draft for CEO sign-off before sprint kickoff
**Reads alongside**: `Transmax_Review_and_Upgrade_Path.docx` (the May 2026 review/diagnosis)

---

## 0. Reading guide

The May 2026 review doc is the **diagnosis**. This is the **prescription** — the executable next-big-release plan that takes us from "credible prototype" to "pilot-signable Pharma SaaS" in 90 days.

It applies four expert lenses on top of the existing review:

- **PM lens** — what scope ships, in what order, with what exit criteria, what's parked.
- **Pharma lens** — which regulatory primitives are non-negotiable for v3 versus deferable to v3.1+.
- **UX lens** — which surfaces a regulatory reviewer will actually live in, and what's broken about them today.
- **AI lens** — the model/prompt/agent architecture that has to land in v3 so v4 multi-agent fabric is a refactor, not a rebuild.

Where the review doc identifies an issue (e.g. C-04 audit chain weakness), this doc names the **ticket**, the **acceptance criteria**, the **owner pod**, the **sprint**, and where applicable a **detailed spec**.

If you read nothing else, read **§1 (the thesis)**, **§4 (the epics)**, and **§9 (decisions only you can make)**.

---

## 1. Release thesis

**Codename**: Pilot Ready
**Version**: TransMax v3.0
**Window**: 12 weeks / 6 two-week sprints, target ship 2026-07-24
**Headline**: A version of TransMax that a regulatory affairs lead at a top-20 pharma can run through a vendor security questionnaire and a CSV/IQ-OQ-PQ readiness review **without it being thrown out on day one**.

### What v3.0 is built around

1. **Auth-first, audit-first, soft-delete-first** — the three irreducible primitives of any GxP system. Today all three are weak.
2. **Audit ledger v2** — domain-separated chained hashing, per-event UTC timestamps, daily Merkle root anchored to S3 Object Lock, server-side verification API. The current ledger is *the* strongest conceptual asset in the codebase; the cryptography just doesn't survive a 30-minute expert review yet.
3. **Validation pack as build artefact** — every release renders URS / FS / IQ / OQ / PQ + RTM + signed manifest. We make CSV (Computer System Validation) a **CI job**, not a Word document somebody updates after the fact.
4. **Reviewer cockpit that doesn't lie** — fix the mock-data fallback, the silent admin-fallback, the dual IA, the unsaved edits, the polling storms, the no-keyboard-nav. A reviewer signs off real translations on a real audit chain or sees an explicit error — never a fake.
5. **Agent fabric foundation + prompt registry** — promote prompts to versioned YAML, formally name the four agents already implicit in the LangGraph (Translator / Terminology / Regulatory / Reviewer / BackTranslator), wire OTel spans, enforce per-tenant cost ceilings. v4's multi-agent expansion becomes additive, not a rewrite.

### What v3.0 explicitly does NOT do (the cutline)

- ❌ **eCTD / Veeva Vault / Documentum connectors** — Phase 2 (3-6 months). v3 ships REST + signed-URL + SFTP only.
- ❌ **ISPOR linguistic-validation graph** (forward / reconciliation / back / cognitive debriefing) — Phase 3. v3 ships forward + back-translation reconciliation only.
- ❌ **SOC 2 Type II report**, **ISO 27001 certificate**, **ISO 17100/18587** — Phase 2-3. v3 starts evidence collection and ships the BAA/DPA/CAIQ-Lite triad.
- ❌ **eCTD module 1 v3.1.1 / IDMP SPOR connectors** — Phase 2.
- ❌ **EDQM Standard Terms live integration** — Phase 2 (subscription + ETL is a 4-week piece on its own). v3 ships the **terminology-lock primitive** that EDQM will plug into.
- ❌ **Multi-region deployment, customer-managed keys via KMS, BYOK** — Phase 2. v3 is single-region (EU-Central) with vendor-managed keys, but architected so KMS is a swap not a refactor.
- ❌ **Mobile reviewer surface** — Phase 3. v3 is desktop-first responsive.
- ❌ **Per-tenant LoRA adapters / fine-tuning** — Phase 3.
- ❌ **MCP server productisation** — keep the prototype; productise in v4.

### Frozen-by-design (architecture decisions we will not revisit in v3)

- **Postgres + pgvector** stays the primary store. The dual-model layer in `app/models/` (database.py vs translation.py) gets rationalised in v3 (E1.6) but we don't switch DBs.
- **LangGraph** stays the orchestrator. We name the agents and add a registry, but we don't rewrite to a custom orchestrator.
- **Next.js 16 / React 19** stays the frontend. We consolidate IA but don't migrate to a different framework.
- **OAuth 2.1 + OIDC** for human auth via a hosted IdP (Auth0 / Keycloak — see §9 Open Decision D-3). API tokens via signed JWT.
- **The PRD v1.1** (`research/draft_PRD.md`) stays the spec for what TransMax does. v3 makes good on its FR1-FR9, plus closes the gaps the May 2026 review found.

### Definition of Done for v3.0 (release-level)

| # | Exit criterion | Verified by |
|---|---|---|
| 1 | All 13 Critical findings (C-01 to C-13) and all 7 Critical frontend findings (F-C01 to F-C05 + Phase 0 build/auth) **closed** | Review doc Appendix A walked, signed by Tech Lead |
| 2 | Vendor security questionnaire **CAIQ-Lite** drafted, all answers backed by either evidence or a stated mitigation roadmap | Reviewed by external CISO advisor |
| 3 | DPA, BAA, sub-processor list **published** under `compliance/` | Approved by external pharma counsel |
| 4 | Validation pack (URS / FS / DS / IQ / OQ / PQ / RA / VSR / RTM) renders for the v3.0 release tag | CI job `validation-pack` green |
| 5 | Audit ledger v2 verifies a 100k-event chain in **≤ 60s** with cryptographic guarantee no past event was altered | New test suite `test_audit_ledger_v2.py` passes |
| 6 | Frontend build **green** in CI; Vitest unit + Playwright e2e (upload → translate → review → sign → audit) gate every PR | GitHub Actions |
| 7 | EMA QRD validators pass for golden SmPC sample en→es, en→fr, en→de | New test suite `test_qrd_compliance.py` |
| 8 | Reviewer cockpit on `/workspace/review/[jobId]` passes WCAG 2.1 AA (axe + manual screen-reader pass on AR + JA) | A11y audit attached to release |
| 9 | At least **2 paid pilots** signed (LOI + master agreement), with a pilot-to-production conversion clause | Sales record |
| 10 | EU AI Act technical-documentation skeleton + per-language-pair model cards published internally | Reg Affairs Lead sign-off |

If any of 1-8 is red the release does not ship.

---

## 2. Four expert lenses on the work

### 2.1 PM lens — sequence, scope, exit criteria

**The trap**: trying to ship 25 things in 12 weeks. The Top 25 backlog in your review doc is the right backlog, but if a 10-engineer team picks up 25 work-items in parallel they finish 25 work-items badly. v3.0 picks **the 8 epics that compound** — each epic enables the next, each ships a *defensible artefact*, each has a single named owner pod.

**The shape**: classic dependency-aware sequencing.

```
Sprint 0  Sprint 1-2     Sprint 3-4         Sprint 5         Sprint 6
─────────────────────────────────────────────────────────────────────
[Stop the bleeding]
                ├─ Auth + RBAC + secrets
                │       ├─ Audit ledger v2
                │       │       ├─ Validation pack
                │       │       │       ├─ Pilot pack
                ├─ Soft-delete + migrations
                ├─ Document fidelity ─┐
                                       ├─ QRD + term lock ─┐
                ├─ PII + segmentation ─┘                    │
                                       ├─ Agent fabric ──── │
                ├─ Frontend IA + build ┘                    │
                                       ├─ Reviewer cockpit ─┤
                                                            └─ E2E + signoff
```

**What I'm watching**: the scope ratchet. Mid-sprint requests to add Veeva connectors / Slack bot / mobile app / blockchain anchoring will appear. The release-thesis cutline (§1) is the answer; everything else is v3.1.

**Cadence rituals** (lightweight):
- Daily 10-min standup per pod, async if all-hands not present
- Weekly cross-pod sync (Tuesday 30 min) — risk register, dependencies, decisions
- Bi-weekly demo + retro (end of each sprint)
- Monthly CEO readout (one-pager: KPI movement, decisions needed, risk register delta)

**Pod structure** (10 eng + 2 QA + 1 Reg + 1 Design + 1 PM + 0.5 SecEng — matches the existing review's Phase 1 envelope):

| Pod | Headcount | Owns |
|---|---|---|
| Auth & Tenancy | 1 BE + 0.5 SecEng | E1 |
| Audit & Validation | 1 BE + 1 QA | E2, E3 |
| Document Pipeline | 2 BE | E4, E5 |
| Quality & Regulatory | 1 BE + 1 Reg | E6, parts of E10 |
| Agent & AI | 2 BE | E7 |
| Reviewer Frontend | 2 FE + 1 Design | E8 |
| Platform & Observability | 1 BE | E9 |
| Pilot/GTM | 1 PM + Reg | E10 |

This is intentionally loose — pairs cross-train across pod boundaries — but it gives every epic an unambiguous owner.

---

### 2.2 Pharma lens — regulatory primitives that must land

The review doc enumerates the full compliance gap matrix. In v3.0 we must bank the primitives below; everything else can wait without losing the pilot.

**MUST land in v3.0**:

| Primitive | Why pilot-blocking | Where in plan |
|---|---|---|
| **Authoritative access control** (Auth on, RBAC enforced at every API, MFA, session timeout) | 21 CFR Part 11 §11.10(d) — without it there is no audit subject and no defensible pilot | E1 |
| **Tamper-evident audit chain** (domain-separated hashing + per-event UTC timestamps + daily Merkle anchor + verify API) | Part 11 §11.10(e) audit trail; survives 30-min expert review | E2 |
| **E-signature** (sign with reason, 2FA challenge, signed manifest export, trusted-timestamp authority) | Part 11 §11.50, §11.70 | E2 |
| **Soft-delete + redaction-by-tombstone** | Audit references must outlive the records they describe; immutability principle | E1.6 |
| **Validation pack as code** (URS / FS / IQ / OQ / PQ / RTM / VSR rendered per release with signed manifest) | GAMP 5 Cat 4; Annex 11; what an internal CSV team will actually ask to see | E3 |
| **Real document ingestion** (DOCX with tracked changes preservation, PDF with OCR + table extraction, XLIFF in/out) | Without this the agent corrupts SmPC/PIL inputs and the rest is theatre | E4 |
| **Production PII redaction** (Microsoft Presidio or AWS Comprehend Medical, structured token round-trip in audit chain) | HIPAA / GDPR — regex is a known false-pos/false-neg machine, won't survive a DPIA | E5 |
| **Sentence-aware segmentation** (replace `text.split('.')`, handle abbreviations, lists, tables) | EMA QRD section integrity depends on it | E5 |
| **EMA QRD validators** (SmPC + PIL section presence, order, mandatory phrases, per language) | The actual differentiator versus Phrase / Smartling / DeepL — pharma-native, not pharma-flavoured | E6 |
| **Terminology lock primitive** (which v3.1 hooks EDQM into) | Stops glossary drift; ISO 17100-aligned | E6 |
| **DPA + BAA + CAIQ-Lite + sub-processor list** | Vendor security questionnaire pass | E10 |
| **EU AI Act technical-documentation skeleton + model cards per LLM × language pair** | High-risk AI obligations enforce **2026-08-02** — we cannot ship a translator into pharma after that date without these | E10 |

**CAN wait for v3.1+ without losing the pilot**:

- ISPOR linguistic-validation graph (forward → reconciliation → back → cognitive debriefing): defer; ship forward + back-reconciliation primitive only.
- EDQM Standard Terms live data feed: defer the subscription + ETL; ship the lock primitive.
- IDMP/SPOR connectors: defer.
- eCTD module-1 mapping: defer; design the data model so it's a v3.1 add.
- ISO 13485 (medical-device QMS): defer until first MDR/IVDR customer.
- FDA AI/ML credibility framework executed evidence: defer execution to v3.1; v3 ships the *plan*.

**Hard constraint**: the LLM providers we depend on (OpenAI, Anthropic, DeepL) become "qualified suppliers" the moment we sell into pharma. Annex 11 §3 explicitly requires supplier assessment. The Pilot/GTM pod owns producing **vendor assessment files** for each provider (SOC 2 report, ISO 27001 certificate, terms-of-service no-training clause, BAA where applicable, sub-processor disclosures). This is a 1-week task that can't be skipped.

---

### 2.3 UX lens — trust by design

The reviewer is the human who decides whether to ship a translated SmPC to a regulator. v3 must make their job **fast, audited, and impossible to fake**.

**The five UX principles for v3**:

1. **Never show a fake**. Today the review screen silently substitutes mock translations on backend errors (F-C03), and the auth provider injects a hardcoded admin user on backend failure (F-C01). For pharma both are disqualifying — a reviewer can sign off mock content as real, including a deliberate negation flip in the mock. v3 replaces every silent fallback with an explicit error state with a retry button. **No exceptions, no flags, no debug mode bypass.**
2. **The audit chain is visible, verified, and clickable**. Every audit timeline event has a chain-state badge (✅ Verified / ⚠ Broken-at-event-N) computed by a server-side `/audit/{job_id}/verify` call rendered into the UI. Clicking an event opens its full payload, hashes, and Merkle path. Compliance optics become compliance reality.
3. **Reviewer keyboard-first**. A regulatory reviewer working through a 200-segment PIL needs a keyboard cockpit:
   - `j` / `k` — next / previous segment
   - `a` — accept current
   - `r` — reject (opens reason field)
   - `e` — edit (focus the target editor)
   - `f` — flag for second review
   - `g` `s` — go to sign-off panel
   - `⌘ ↩` — sign accepted batch (opens 2FA challenge)
   - `?` — keyboard help overlay
   The review canvas virtualises the segment list (TanStack Virtual) so 1,000 segments stay at 60fps.
4. **One IA**. Today there are two parallel surfaces — top-level `/`, `/document/[id]`, `/translate/[id]`, `/review/[id]` and `/workspace/{audit,documents,jobs,projects,…}`. Two document workstations, two themes (slate-50 vs slate-950), two ways to start a job. v3 picks `/workspace/*` as canonical and retires the rest. Old routes 301-redirect.
5. **Severity colour scale conforms to defect taxonomy and WCAG AA**. Critical / Major / Minor / Info from `app/core/defect_taxonomy.py` map to four named tokens (`--severity-critical-{bg,fg,border}`, …) with measured contrast ratios. Status is **never** colour-only; every coloured chip carries a glyph and a label. Dark and light themes both pass.

**Minimum design-system delta in v3**: Input, Form, Dialog, Tooltip, Tabs, Breadcrumb, Table primitives, Severity chip, Audit-state badge, Progress orb, Signature panel. (Today: Button, Card, GlassCard + bespoke. Half built.)

**i18n minimum**: `next-intl`, EN + DE + FR + ES + JA + AR with **RTL CSS for AR**. The reviewer surface and auth screens must work in all six. Marketing surfaces stay English-only in v3.

**A11y minimum**: WCAG 2.1 AA on `/workspace/review/[jobId]`, `/workspace/documents/[id]`, `/workspace/audit`, `/login`. Verified by axe + a manual screen-reader pass on AR and JA. (Other surfaces ship "AA-targeted" with known gaps logged.)

---

### 2.4 AI lens — agent fabric foundation

The review doc rightly identifies that v3 must build the *primitives* multi-agent v4 will sit on. Doing this without committing to the multi-agent rebuild now is the trick.

**The seven AI deliverables for v3**:

1. **Prompt registry as code**. Move every prompt from `app/agents/prompts.py` string constants into `app/agents/prompts/<agent>/<version>.yaml`, with frontmatter (`semver`, `model_default`, `temperature`, `max_tokens`, `tags`, `eval_set`). Loader in `app/agents/prompt_registry.py`. Every `JobConfigSnapshot` records `(agent_name, prompt_version, model_id, model_version)` for every node touched. Required for reproducibility under GxP and for EU AI Act technical documentation.
2. **Agent fabric naming** (no rewrite). The four agents already implicit in the LangGraph become formally named subgraphs:
   - `TranslatorAgent` (translate node)
   - `BackTranslatorAgent` (reverse_translate node)
   - `RegulatoryAgent` (run_quality_gates node)
   - `RefinerAgent` (refine_translation node)
   Plus one new optional node:
   - `TerminologyAgent` (NEW — pre-translate; resolves glossary, EDQM term, TM, language-pack tokeniser into a single constraint pack with provenance)
   Each agent has its own folder under `app/agents/`, its own prompt subdirectory, its own tests, its own model-card stub. v4's multi-agent expansion becomes "add agents" not "rewrite the orchestrator".
3. **Deterministic agent router**. `app/agents/router.py` picks model by `(source_lang, target_lang, regulatory_profile, risk_level, tenant_cost_ceiling)`. Routing config is YAML in Git. Default routing:
   - `en→es` SmPC: `gpt-4o` primary + `claude-sonnet-4-6` reflexion
   - `en→ar` PIL: `gpt-4o` primary + `claude-sonnet-4-6` reflexion (RTL-safe)
   - `en→ja` SmPC: `gpt-4o` primary + `claude-sonnet-4-6` reflexion + `janome` tokenisation verifier
   - All pairs have a `deepl` fallback for low-risk content under cost ceiling
4. **Real PII pipeline**. Replace `app/services/pii_service.py` regex chain with **Microsoft Presidio** (Spanish/Arabic/Japanese custom recognisers required) or **AWS Comprehend Medical** behind the same interface. Round-trip uses opaque token IDs (`<<PII:0001>>`) carried into the audit chain so the *de-identified* text is what the LLM sees and the *re-identified* text is what the reviewer sees, with a signed mapping in storage.
5. **Sentence segmentation v2**. Replace `text.split('.')` with a `SegmentationService` keyed on language pack: stanza/spaCy SeqSegmenter for Latin-script languages, janome for JA, custom rule pack for AR. Handles abbreviations (incl. pharma-specific "i.v.", "p.o.", "b.i.d."), preserves table cells and list items as discrete segments, preserves ordering, emits stable `segment_id` derived from `(doc_hash, segment_offset, segment_text_hash)`.
6. **Cost & token governance**. Replace the hard-coded gpt-4o-mini pricing in `translation_engine.py` with a pricing table keyed by `(provider, model)` and read from a Git-tracked `app/services/model_pricing.yaml`. Move token counters to per-run scope (not engine instance). Add per-tenant cost ceilings stored in `tenant_settings`; circuit-break and emit a structured event when 80% of ceiling is reached, hard-block at 100%. Surface in the dashboard.
7. **Eval harness**. `tests/evals/` holds golden sets per language pair (en→es, en→fr, en→de, en→ar, en→ja) with safety-critical cases (negation, decimal, frequency, unit conversion traps, mixed script). `pytest tests/evals` runs every PR; release-blocking if **critical-defect rate > 0** on the golden set. Drift report (per-pair quality KPIs vs last 4 weeks) renders into the dashboard weekly.

**Out of scope for v3, into v4**: per-tenant LoRA adapters, on-prem open-weight LLM (Llama/Mistral), automated prompt promotion from reviewer edits, multi-modal (figure / table / image translation), regulatory writing agents.

---

## 3. Architecture deltas (the few foundational shifts)

These are the architectural pieces that need to be agreed *before* sprint 0. After agreement they become inputs to sprint planning, not debate items.

### Δ-A. Auth-first, multi-tenant, soft-delete-by-default

- `AUTH_MODE` is **removed as a dev convenience** for production builds. CI rejects deployment artefacts where `AUTH_MODE=none`.
- All API routes wrap `require_permission(...)` via FastAPI `Depends`. UI gating via `RequireRole` continues but is **never authoritative**.
- Every domain table grows `organization_id` (NOT NULL FK to `organizations`), `is_deleted` (BOOL DEFAULT FALSE), `deleted_at`, `deleted_by`. `tenant_session_factory` filters every query.
- A new `redaction_service` performs **redaction by tombstone**: replaces the body of a deleted record with a hash of the original and a tombstone marker, preserves PK + audit references, and adds an audit event chained into the v2 ledger.

### Δ-B. Audit ledger v2

Domain-separated SHA-256 over canonical bytes (sequence_index || previous_hash || domain_tag || payload_hash). Daily Merkle root anchored to **S3 Object Lock with compliance-mode retention** (cheapest verifiable option; QLDB deferred to v4 after AWS deprecated QLDB GA in 2024 and the path forward is unclear). Per-event UTC timestamps from a **trusted timestamp authority** (FreeTSA or DigiCert TSA). Server-side `verify_chain_integrity(job_id, since_seq?, until_seq?)` returns `{intact: bool, broken_at?: int, anchor_intact: bool, last_anchor_at: ts}`. Detailed spec in §6.A.

### Δ-C. Agent fabric + prompt registry

Single LangGraph stays. Nodes become formally named **agents** with their own folders, prompts, model cards, tests. Prompts are versioned YAML loaded by `prompt_registry.py`. `JobConfigSnapshot.config_blob` schema bumps from v1 → v2 with explicit `agent_topology[]` and `prompt_version` per agent. Migration tool re-anchors v1 snapshots to v2 schema. Detailed spec in §6.B and §6.C.

### Δ-D. Frontend IA consolidation

Pick `/workspace/*` as canonical. Retire top-level `/document/[id]`, `/translate/[id]`, `/review/[id]`, `/new`, `/knowledge`, `/design-system` (the last one moves to `/workspace/design-system` for designers). 301-redirects via `next.config.ts` rewrites. Single theme — light by default, dark via `prefers-color-scheme` only. AuthProvider, API client, permissions stay where they are.

### Δ-E. Observability + cost governance

OpenTelemetry SDK is already imported but unused (H-15). v3 wires:
- One span per LangGraph node, attributes: `job_id`, `tenant_id`, `agent_name`, `prompt_version`, `model`, `tokens_in`, `tokens_out`, `latency_ms`.
- One span per LLM provider call with `provider`, `model`, `usd_cost`.
- One span per quality-gate check with `gate_name`, `severity`, `defect_count`.
- Prometheus counters: `translation_jobs_total{tenant,status}`, `defects_total{tenant,severity,category}`, `llm_cost_usd_total{tenant,model}`, `audit_events_total{tenant}`.
- Histograms: `translation_duration_seconds{tenant,target_lang}`, `llm_call_duration_seconds{provider,model}`, `refinement_iterations{tenant}`.

Backend: OTEL collector → Tempo (traces) + Mimir (metrics) self-hosted, or Grafana Cloud Free for pilot scale.

---

## 4. Epics

| ID | Epic | Owner pod | Sprints | Story points |
|---|---|---|---|---|
| **E1** | Security baseline & multi-tenancy | Auth & Tenancy | 0-2 | 21 |
| **E2** | Audit ledger v2 + e-signature | Audit & Validation | 1-4 | 34 |
| **E3** | Validation pack as code | Audit & Validation | 3-6 | 21 |
| **E4** | Document ingestion fidelity (DOCX/PDF/XLIFF) | Document Pipeline | 1-4 | 26 |
| **E5** | PII v2 + segmentation v2 | Document Pipeline | 1-4 | 21 |
| **E6** | Quality gate hardening + EMA QRD validators + term-lock primitive | Quality & Regulatory | 2-5 | 26 |
| **E7** | Agent fabric naming + prompt registry + cost governance + agent router | Agent & AI | 1-5 | 29 |
| **E8** | Frontend IA consolidation + reviewer cockpit + design system v1 | Reviewer Frontend | 0-6 | 42 |
| **E9** | Observability, tracing, evals | Platform & Observability | 1-5 | 18 |
| **E10** | Pilot readiness pack (BAA / DPA / CAIQ / model cards / EU AI Act skeleton) | Pilot/GTM | 2-6 | 21 |

Total ≈ 259 story points across 12 weeks × 10 engineers ≈ 21 SP/eng/week — aggressive but achievable given the team's existing depth and the absence of greenfield uncertainty.

---

## 5. Sprint plan

### Sprint 0 — "Stop the bleeding" (week 0; 5 working days)

The non-negotiable list from review doc Phase 0. None of it is sprint-planned — it's day-1 work for everyone.

| Ticket | Title | Pod | Hours |
|---|---|---|---|
| **TMX-3000** | Rotate exposed OpenAI API key + history-purge .env via `git filter-repo` | Auth | 2 |
| **TMX-3001** | Move secrets to vault (1Password Secrets Automation or AWS Secrets Manager); GHA env injection only | Auth + Platform | 6 |
| **TMX-3002** | `.gitignore` *.db, *.log, .env, debug_*, *.txt artefacts; `git rm --cached` historical artefacts | Platform | 2 |
| **TMX-3003** | Force `AUTH_MODE != none` in production (refuse to start); break build on default `SECRET_KEY` | Auth | 4 |
| **TMX-3004** | Strip mock-data fallback from `app/review/[jobId]/page.tsx`; replace with explicit error UX | Frontend | 4 |
| **TMX-3005** | Strip admin-fallback in `lib/auth.tsx`; replace with retry / re-auth UX | Frontend | 3 |
| **TMX-3006** | Fix `tailwindcss-animate` import in `tailwind.config.ts`; get the frontend build green | Frontend | 2 |
| **TMX-3007** | Add `SECURITY.md`, incident-response runbook stub, privacy notice | Pilot/GTM | 4 |
| **TMX-3008** | Stand up Dependabot + gitleaks pre-commit + secret scanning in GHA | Platform | 4 |
| **TMX-3009** | CI gates: backend pytest + frontend build + ESLint + secret scan; PRs blocked on failure | Platform | 6 |

**Sprint 0 exit**: clean history, vault-backed secrets, build green, no production "auth off", no mock-fallback. Can survive a brief security review without being summarily rejected.

### Sprint 1 (weeks 1-2)

Theme: foundations everyone else needs.

- E1.1 `organizations` table; `organization_id` columns on all domain tables; tenant-scoped session factory
- E1.2 Replace custom auth with **Auth0** (or Keycloak — D-3 decision) integration; OIDC + SAML; MFA enforced
- E1.3 RBAC enforcement at every API route via `Depends(require_permission(...))`; integration tests
- E1.4 Soft-delete columns + `is_deleted` filters in tenant session factory
- E2.1 Audit ledger v2 schema + new `audit_events_v2` table; migration plan from v1 events
- E4.1 Real DOCX ingestion via `python-docx` + `mammoth` for tracked-changes preservation
- E5.1 Sentence segmentation v2 service skeleton (language-pack hook)
- E7.1 Prompt registry v1 — directory structure + loader + first migration of `prompts.py` constants
- E8.1 Frontend IA migration plan + redirect map; pick canonical theme tokens
- E9.1 OTel SDK wired; first spans on FastAPI + LangGraph entry/exit

### Sprint 2 (weeks 3-4)

Theme: lock down the floor.

- E1.5 Tenant-scoped data tests (cross-tenant queries return 0 rows; verified)
- E1.6 Migration unwinding — split mega-migration into semantic Alembic revisions
- E2.2 Audit ledger v2 hashing implementation (domain-separated, canonical bytes)
- E2.3 Trusted timestamp authority integration (FreeTSA + signed Merkle root)
- E2.4 `verify_chain_integrity(job_id)` API
- E4.2 PDF ingestion v2 via Azure Document Intelligence or AWS Textract — OCR + tables
- E4.3 XLIFF 2.1 in/out + TMX in/out
- E5.2 Sentence segmentation language packs (en, es, fr, de, ar, ja) + abbreviations + lists/tables
- E5.3 PII v2 (Presidio) integration + structured token round-trip
- E7.2 `JobConfigSnapshot` schema v2 with `agent_topology[]` + `prompt_version`
- E7.3 Model pricing table + per-run cost counters + tenant ceilings
- E8.2 Workspace IA migration; old routes redirect; theme unified
- E8.3 Design system primitives shipped (Input, Form, Dialog, Tooltip, Tabs, Breadcrumb, Table)
- E9.2 Prometheus metrics scaffolding + dashboard skeleton

### Sprint 3 (weeks 5-6)

Theme: regulatory primitives.

- E2.5 E-signature flow — sign-with-reason, 2FA challenge, signed manifest export
- E2.6 Soft-delete + redaction-by-tombstone preserving the chain
- E3.1 Validation pack templates (URS / FS / DS / IQ / OQ / PQ / RA / VSR)
- E3.2 RTM (Requirements Traceability Matrix) generator from pytest markers
- E6.1 EMA QRD validators v1 — SmPC + PIL section presence/order/mandatory phrases for en, es, fr, de
- E6.2 Terminology lock primitive — glossary version pinning + drift report
- E6.3 Quality gate v2 — instance-based, thread-safe, deterministic on retry (closes C-08)
- E7.4 Agent fabric formal naming — folders, model-card stubs, tests per agent
- E7.5 Deterministic agent router (`router.py`) with YAML config
- E8.4 Bilingual review canvas v1 — synced scrolling, segment list virtualised, severity chips

### Sprint 4 (weeks 7-8)

Theme: reviewer flow + agent intelligence.

- E2.7 Audit timeline component v2 — server-verified chain state badges, click-to-expand events
- E3.3 Signed release manifest (cosign + SLSA provenance + SBOM)
- E3.4 CI job `validation-pack` rendering on every release tag
- E6.4 EMA QRD validators v2 — ar + ja with language-pack-aware tokenisation
- E6.5 Defect taxonomy v2 — wired into severity colour scale (frontend) + telemetry (backend)
- E7.6 BackTranslator agent v2 — structural similarity (BERTScore) instead of text-equality reflexion
- E7.7 Cost dashboard — per-tenant, per-model, with ceiling alerts
- E8.5 Reviewer keyboard cockpit (j/k/a/r/e/f/g s/⌘↩/?)
- E8.6 Sign-and-save reviewer flow with reason capture + 2FA challenge → signed audit event
- E8.7 i18n via next-intl — en/de/fr/es/ja/ar wired on reviewer + auth surfaces

### Sprint 5 (weeks 9-10)

Theme: harden everything that's already shipped.

- E1.7 Resilience module v2 — circuit breaker backed by Redis (closes C-07), instance-based
- E1.8 Idempotency keys on job submission; dead-letter queue (closes H-14)
- E2.8 Audit chain replay & verification soak test (100k events ≤ 60s)
- E3.5 Risk assessment YAML per feature; aggregate per release into VSR
- E6.6 Learning service rule promotion — remove auto-approval; require human-signed promotion (closes C-13)
- E7.8 Eval harness `tests/evals/` — golden sets per language pair; CI release-blocker on critical-defect > 0
- E8.8 A11y audit + WCAG AA fixes on reviewer + auth surfaces (axe + manual screen-reader pass on ar/ja)
- E8.9 RTL CSS for arabic; LTR/RTL toggle wired to user preference + browser
- E9.3 Drift detection — weekly per-pair quality report; auto-rollback to prior prompt version on threshold breach
- E10.1 CAIQ-Lite drafted; mapped against actual evidence
- E10.2 BAA template + sub-processor list

### Sprint 6 (weeks 11-12)

Theme: pilot ship.

- E2.9 Daily Merkle root anchoring to S3 Object Lock; anchor verification job
- E3.6 v3.0 release tag rendered with full validation pack + signed manifest
- E6.7 Golden EMA SmPC sample passes 100% QRD validation en→es/fr/de/ar/ja
- E8.10 Pilot polish — reviewer cockpit perf budget (≤200ms input latency at 500 segments), error states audited end-to-end
- E9.4 Production observability live — alerts on cost ceiling breach, drift threshold, audit-chain break
- E10.3 EU AI Act technical-documentation skeleton + per-language-pair model cards published internally
- E10.4 GDPR DPA published; DPIA template; transfer-impact assessment template
- E10.5 FDA AI/ML credibility framework — context-of-use defined, model risk class assigned, credibility plan v1
- E10.6 Pilot security questionnaire pass — verified by external CISO advisor
- E10.7 Pilot LOIs → pilot master agreements signed

**Sprint 6 exit = v3.0 release.** All 10 release-DoD criteria green.

---

## 6. Detailed specs (the non-obvious pieces)

For tickets where the design is not self-evident from the title, here are full specs. Each is meant to be a one-pager a senior engineer can pick up and execute against.

### 6.A. Spec — Audit ledger v2

**Owner pod**: Audit & Validation
**Tickets**: TMX-3100 to TMX-3109
**Sprints**: 1-4
**Closes findings**: C-04, C-05, F-C05, parts of H-06

#### Goals
1. Domain-separated chained hashing that an external cryptographer cannot trivially break.
2. Per-event UTC timestamps from a trusted source (not module-load time).
3. Daily Merkle root anchored externally so even a compromised application database cannot rewrite history.
4. Server-side verification API that the frontend can call to render a verified state.
5. Non-destructive migration from v1 chain.

#### Schema

```sql
CREATE TABLE audit_events_v2 (
  event_id          UUID PRIMARY KEY,
  organization_id   UUID NOT NULL REFERENCES organizations(id),
  job_id            UUID NOT NULL REFERENCES translation_jobs(id),
  sequence_index    BIGINT NOT NULL,             -- per-job monotonic
  domain_tag        TEXT NOT NULL,               -- 'audit:event:v2'
  event_type        TEXT NOT NULL,               -- 'JOB_STARTED', 'SEGMENT_TRANSLATED', ...
  actor_id          UUID,                        -- user / system actor
  actor_kind        TEXT NOT NULL,               -- 'user' | 'system' | 'agent:translator'
  payload           JSONB NOT NULL,
  payload_hash      BYTEA NOT NULL,              -- SHA-256(canonical_json(payload))
  previous_hash     BYTEA NOT NULL,              -- prev event hash, or zeros for sequence_index=0
  event_hash        BYTEA NOT NULL,              -- the chained hash; see §Hashing
  event_ts_utc      TIMESTAMPTZ NOT NULL,        -- per-event, NOT module-load
  tsa_token         BYTEA,                       -- RFC 3161 timestamp token (nullable for non-signed events)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (job_id, sequence_index),
  CHECK (length(event_hash) = 32),
  CHECK (length(payload_hash) = 32),
  CHECK (length(previous_hash) = 32)
);
CREATE INDEX ON audit_events_v2 (organization_id, job_id, sequence_index);
CREATE INDEX ON audit_events_v2 (event_ts_utc);

CREATE TABLE audit_anchors (
  anchor_id         UUID PRIMARY KEY,
  organization_id   UUID NOT NULL REFERENCES organizations(id),
  anchor_date       DATE NOT NULL,                -- one anchor per (org, day)
  merkle_root       BYTEA NOT NULL,
  event_count       BIGINT NOT NULL,
  first_event_id    UUID NOT NULL,
  last_event_id     UUID NOT NULL,
  s3_object_uri     TEXT NOT NULL,                -- s3://transmax-audit/...
  s3_version_id     TEXT NOT NULL,
  s3_object_lock_until TIMESTAMPTZ NOT NULL,      -- compliance-mode retention end
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, anchor_date)
);
```

#### Hashing

Canonical bytes for the event hash:

```
sequence_index_be64
|| previous_hash_32B
|| len_be32(domain_tag) || domain_tag_utf8
|| len_be32(event_type) || event_type_utf8
|| event_ts_utc_iso_8601_utf8
|| payload_hash_32B
```

`event_hash = SHA-256(canonical_bytes)`.

Genesis (`sequence_index = 0`): `previous_hash = 32 zero bytes`. **No** hardcoded GENESIS_HASH constant — closes C-04 properly.

`payload_hash = SHA-256(canonical_json(payload))` where canonical-JSON sorts keys, normalises numbers, and uses NFC unicode form.

#### Trusted timestamps

For events with `actor_kind = 'user'` and any e-signature event, request an RFC 3161 timestamp token from FreeTSA (free) or DigiCert TSA (paid SLA). Store the token in `tsa_token`. For high-volume system events (`actor_kind = 'system'`), use the daily Merkle anchor's TSA token instead of per-event tokens.

#### Daily Merkle anchor

A scheduled job at 00:05 UTC per organization:

1. Selects all events for `(org, anchor_date = yesterday)` in `sequence_index` order.
2. Builds a Merkle tree (SHA-256) over event hashes.
3. Writes the tree-root + event-count + first/last event-id to S3 Object Lock with **compliance-mode retention** (default 10 years, configurable per tenant).
4. Requests an RFC 3161 timestamp token for the Merkle root.
5. Inserts an `audit_anchors` row.
6. The daily anchor itself becomes an event of type `DAILY_ANCHOR` chained into the v2 ledger.

#### Verification API

```
GET /api/v1/audit/{job_id}/verify
  ?since_seq=N   (optional)
  ?until_seq=M   (optional)
```

Returns:

```json
{
  "intact": true,
  "first_seq": 0,
  "last_seq": 1234,
  "broken_at": null,
  "anchor_intact": true,
  "last_anchor_at": "2026-07-15T00:05:12Z",
  "checked_events": 1235,
  "verification_duration_ms": 412
}
```

Verification:
1. Walks events in sequence; recomputes each `event_hash`; rejects on mismatch.
2. Re-validates `payload_hash` against canonical-JSON of payload.
3. For each anchor in range, recomputes Merkle root from events; compares to `audit_anchors.merkle_root`; fetches the S3 object; verifies S3 object hash + version-id.
4. Returns the first sequence index where any check fails as `broken_at`.

Frontend `AuditTimeline` calls this on render; renders ✅ Verified (intact + anchor_intact), ⚠ Anchor missing (intact + !anchor_intact), ❌ Broken at #N (!intact + broken_at).

#### Migration from v1

One-shot script `scripts/migrate_audit_v1_to_v2.py`:

1. For each existing v1 audit chain, walks events in original order.
2. Re-derives v2 event hashes using v2 canonical bytes (v1 timestamps stay; we don't backdate).
3. Writes `audit_events_v2` rows with `event_type = 'V1_MIGRATED:' + original_type`.
4. Writes a single `MIGRATION_FROM_V1` event at the head of each chain with the v1 chain's last hash in `payload`.
5. v1 events stay in place (read-only) for forensic reference.

#### Tests

- `tests/audit/test_v2_hashing.py` — known-answer tests against fixed inputs (regression-proof).
- `tests/audit/test_v2_chain_integrity.py` — tamper detection at each position; partial-write recovery; replay attack rejection.
- `tests/audit/test_v2_anchor.py` — daily anchor end-to-end with mocked S3 + FreeTSA.
- `tests/audit/test_v2_migration.py` — v1→v2 migration round-trip on golden test data.
- `tests/audit/test_v2_perf.py` — verify 100k-event chain in ≤ 60s on CI hardware.

---

### 6.B. Spec — Prompt registry

**Owner pod**: Agent & AI
**Tickets**: TMX-3200 to TMX-3206
**Sprints**: 1-3
**Closes findings**: M-03, parts of EU AI Act technical documentation

#### Layout

```
app/agents/
├── prompts/
│   ├── translator/
│   │   ├── v1.0.0.yaml           # current prompt
│   │   ├── v1.1.0.yaml           # next iteration in flight
│   │   └── _shared/
│   │       └── pharma_safety_preamble.txt
│   ├── back_translator/
│   │   └── v1.0.0.yaml
│   ├── refiner/
│   │   └── v1.0.0.yaml
│   ├── regulatory_qrd/
│   │   ├── en.v1.0.0.yaml
│   │   ├── es.v1.0.0.yaml
│   │   └── ...
│   └── terminology/
│       └── v1.0.0.yaml
└── prompt_registry.py
```

#### YAML schema

```yaml
agent: translator
version: 1.0.0
status: active                    # draft | active | deprecated
default_model:
  provider: openai
  model: gpt-4o
  temperature: 0.2
  max_tokens: 4000
applies_to:
  source_languages: [en]
  target_languages: [es, fr, de, ar, ja]
  content_types: [SmPC, PIL, label_fragment, patient_facing]
  risk_levels: [low, medium, high, critical]
  regulatory_profiles: [EMA, FDA, MHRA]
eval_set: tests/evals/translator/golden_v1.jsonl
guardrails:
  forbid_pii_in_output: true
  enforce_glossary: true
  enforce_term_lock: true
prompt:
  system: |
    You are a translator working on regulated pharmaceutical content for the
    European Medicines Agency. Translate the source segments into {{target_language}}.
    Preserve every number, unit, drug name, and negation literally. Apply the
    constraint pack and glossary. Refuse to invent content.
  user_template: |
    Constraints (JSON): {{constraint_pack_json}}
    Segments (JSON): {{segments_json}}
    Output format: ...
metadata:
  created_at: 2026-05-15T12:00:00Z
  created_by: kapil@transmax.io
  signed_by: kapil@transmax.io
  signature: <pgp signature>
  changelog:
    - v1.0.0 — initial release
```

#### Loader

```python
class PromptRegistry:
    def get(self, agent: str, version: Optional[str] = None,
            target_language: Optional[str] = None) -> PromptTemplate:
        """Resolve a prompt for an agent.

        - If version is None, returns the latest 'active' version.
        - If target_language is provided, prefers a language-specific override.
        - Raises PromptNotFound if no match.
        """

    def render(self, template: PromptTemplate, **vars) -> List[Message]:
        """Render the system + user templates with vars; verify all
        {{placeholders}} resolved; return as LangChain messages."""
```

#### JobConfigSnapshot extension

```python
class AgentInvocation(BaseModel):
    agent: str
    prompt_version: str
    model_provider: str
    model_id: str
    model_temperature: float
    invocation_count: int
    total_tokens_in: int
    total_tokens_out: int

class JobConfigSnapshotV2(BaseModel):
    schema_version: Literal["v2"] = "v2"
    job_id: UUID
    started_at: datetime
    regulatory_profile: str
    risk_level: str
    source_language: str
    target_language: str
    agent_topology: List[AgentInvocation]   # ordered by invocation
    glossary_version: Optional[str]
    language_pack_version: str
    integrity_hash: bytes                    # SHA-256 over canonical JSON of above
```

Migration: on read, v1 snapshots upgrade lazily — `agent_topology` synthesised from inferred history; `schema_version` set to `v1_upgraded`.

#### Tests

- `tests/agents/test_prompt_registry.py` — load, version resolution, language override, missing prompt error, signature verification.
- `tests/agents/test_render.py` — placeholder resolution, unfilled-placeholder detection.
- `tests/agents/test_snapshot_migration.py` — v1 → v2 lazy upgrade.

---

### 6.C. Spec — Deterministic agent router

**Owner pod**: Agent & AI
**Tickets**: TMX-3210 to TMX-3214
**Sprints**: 3-4
**Closes findings**: M-04, M-05, parts of M-07

#### Goal

Given a translation job, deterministically pick the agent topology + per-agent model based on:
- source_language, target_language
- regulatory_profile (EMA / FDA / MHRA / SFDA / EDQM)
- risk_level (low / medium / high / critical)
- tenant_cost_ceiling

The same inputs always produce the same routing. Routing is recorded in the JobConfigSnapshot.

#### Routing config (`config/routing.yaml`)

```yaml
default_topology: [terminology, translator, regulatory_qrd, back_translator, refiner]

rules:
  - match: { target_language: es, risk_level: [high, critical] }
    topology: [terminology, translator, regulatory_qrd, back_translator, refiner]
    models:
      translator: { provider: openai, model: gpt-4o, temperature: 0.2 }
      back_translator: { provider: anthropic, model: claude-sonnet-4-6, temperature: 0.0 }
      regulatory_qrd: { provider: openai, model: gpt-4o-mini, temperature: 0.0 }
      refiner: { provider: openai, model: gpt-4o, temperature: 0.1 }
      terminology: { provider: openai, model: gpt-4o-mini, temperature: 0.0 }

  - match: { target_language: ja }
    topology: [terminology, translator, regulatory_qrd, back_translator, refiner]
    models:
      translator: { provider: openai, model: gpt-4o, temperature: 0.2 }
      # janome verifier is wired into the regulatory_qrd agent for JA tokenisation
      regulatory_qrd: { provider: openai, model: gpt-4o, temperature: 0.0, language_pack: ja }

  - match: { target_language: ar }
    topology: [terminology, translator, regulatory_qrd, back_translator, refiner]
    models:
      translator: { provider: openai, model: gpt-4o, temperature: 0.2, system_extras: [rtl_safe] }

  - match: { risk_level: low, content_type: marketing }
    topology: [translator]
    models:
      translator: { provider: deepl, model: pro }
```

#### Resolver

```python
class AgentRouter:
    def __init__(self, config_path: Path): ...

    def route(self,
              source_lang: str, target_lang: str,
              regulatory_profile: str, risk_level: str,
              content_type: str,
              tenant_id: UUID) -> RoutingDecision:
        """Returns the agent topology + per-agent model + estimated cost.
        Raises CostCeilingExceeded if the resolved cost would breach the tenant ceiling."""
```

`RoutingDecision` is recorded in the JobConfigSnapshot v2 as `agent_topology[]`.

#### Tests

- `tests/agents/test_router.py` — golden cases per `(src, tgt, profile, risk)` combination; assert deterministic output.
- `tests/agents/test_router_cost_ceiling.py` — verify hard-block when ceiling exceeded.
- `tests/agents/test_router_config_validation.py` — malformed routing.yaml fails on load, not at runtime.

---

### 6.D. Spec — Reviewer save-and-sign + e-signature

**Owner pod**: Reviewer Frontend (UI) + Audit & Validation (backend)
**Tickets**: TMX-3300 to TMX-3309
**Sprints**: 3-4
**Closes findings**: F-C03, F-M03, F-C05, parts of E2

#### Goal

A reviewer's edit + sign-off flow that:
1. Persists every edit to the database with full change-reason capture.
2. Requires explicit sign-off (single segment OR batch) with **2FA challenge** before producing a Part 11-compliant signed manifest.
3. Writes a chained audit event for every edit and every signature.
4. Surfaces the audit chain state inline so the reviewer never signs against a broken chain.

#### Backend API

```
PATCH /api/v1/segments/{segment_id}
  Body: { translated_text: string, change_reason: string }
  → 200 { segment, audit_event_id }
  → 409 if segment is in 'signed' state (must reopen first)

POST /api/v1/segments/{segment_id}/reopen
  Body: { reason: string }
  → 200 { audit_event_id }

POST /api/v1/jobs/{job_id}/sign
  Body: {
    segment_ids: [uuid],            # batch sign
    signing_reason: enum('approval', 'review_complete', 'release_to_publishing', 'rejection', 'other'),
    signing_reason_text: string,    # required if 'other'
    twofa_token: string             # OTP from TOTP / WebAuthn assertion
  }
  → 200 { signed_manifest_url, audit_event_ids: [uuid], signature_id: uuid }

GET /api/v1/jobs/{job_id}/manifest/{signature_id}
  → 200 application/pdf  (the signed manifest, suitable for archival)
```

#### Sign-flow details (Part 11-aligned)

1. Reviewer presses `⌘↩` on the reviewer cockpit with N segments accepted.
2. Modal opens: "Sign N segments. Reason: [dropdown + free text]. 2FA challenge below."
3. Reviewer completes 2FA (TOTP via authenticator app v3.0; WebAuthn via passkey v3.1).
4. Backend:
   - Verifies the 2FA token.
   - For each segment, writes a `SEGMENT_SIGNED` audit event (chained, timestamped).
   - Writes a `BATCH_SIGNATURE_APPLIED` event with the signing reason.
   - Renders a PDF manifest containing: signer identity, signing reason, timestamp, segment IDs, source + target text, integrity hashes, and the v2 chain proof (Merkle path to last anchor).
   - Stores the PDF in S3 with Object Lock; URL is signed (24h expiry) and returned.
5. Frontend shows the signed manifest in a pop-over with download and "View audit timeline" links.

#### Manifest PDF contents

- TransMax logo + version
- Job ID, document name, source/target language, regulatory profile
- Signer's verified identity (display name + email + organization)
- Signing reason code + text
- Trusted timestamp (TSA token, with TSA name + URL)
- Per-segment table (ID, source, target, accepted-at, accepted-by)
- v2 audit-chain proof: last sequence index, last event hash, last anchor's Merkle root + S3 URL + Object Lock retention end
- QR code linking to the verification page

#### Frontend cockpit interaction

- Editing a segment fires `PATCH /segments/{id}` on blur with debounce (1s) — but also queues a draft locally so a flaky network doesn't lose work.
- Local drafts visible in segment list with "Unsaved" badge until backend confirms.
- `⌘↩` opens the sign modal only when there is at least one segment in `accepted` state.
- A `chain-broken` indicator at the top of the cockpit hard-disables sign actions (and explains why) if `verify` returns broken.

#### Tests

- `tests/api/test_segment_edit.py`
- `tests/api/test_signature_flow.py` — happy path, missing 2FA, invalid reason, segment-already-signed
- `tests/audit/test_signature_audit_events.py` — events chain correctly, manifest PDF contains right hashes
- Playwright `e2e/reviewer_sign_off.spec.ts` — full upload→translate→review→sign→download manifest
- `tests/security/test_signature_replay.py` — same TOTP cannot be used twice

---

### 6.E. Spec — EMA QRD validators

**Owner pod**: Quality & Regulatory
**Tickets**: TMX-3400 to TMX-3409
**Sprints**: 3-4
**Closes findings**: H-20, parts of compliance gap matrix

#### Goal

Deterministic validators that confirm a translated SmPC or PIL contains the required QRD sections, in the right order, with the mandatory phrases per language. The output is a typed defect list slotted into the existing quality gate.

#### Reference

EMA QRD templates (currently v10.3 for SmPC, v10.3 for PIL) define mandatory sections and standard phrasings per language. We bake these into:

```
app/core/qrd/
├── smpc/
│   ├── v10_3.yaml                 # canonical section list + order
│   ├── translations/
│   │   ├── en.v10_3.yaml          # mandatory phrases per section, en
│   │   ├── es.v10_3.yaml          # mandatory phrases per section, es
│   │   ├── fr.v10_3.yaml
│   │   ├── de.v10_3.yaml
│   │   ├── ar.v10_3.yaml
│   │   └── ja.v10_3.yaml
└── pil/
    └── ... (same shape)
```

#### Section spec (`smpc/v10_3.yaml`)

```yaml
template: SmPC
template_version: 10.3
sections:
  - id: "1"
    title_en: "NAME OF THE MEDICINAL PRODUCT"
    required: true
    order: 1
  - id: "2"
    title_en: "QUALITATIVE AND QUANTITATIVE COMPOSITION"
    required: true
    order: 2
  - id: "3"
    title_en: "PHARMACEUTICAL FORM"
    required: true
    order: 3
  - id: "4"
    title_en: "CLINICAL PARTICULARS"
    required: true
    order: 4
    subsections:
      - id: "4.1"
        title_en: "Therapeutic indications"
        required: true
      # ... 4.2 through 4.9
  # ... sections 5 through 10
```

#### Translation spec (`smpc/translations/es.v10_3.yaml`)

```yaml
language: es
template_version: 10.3
sections:
  "1":
    title: "NOMBRE DEL MEDICAMENTO"
  "2":
    title: "COMPOSICIÓN CUALITATIVA Y CUANTITATIVA"
  # ...
mandatory_phrases:
  "4.4":
    - phrase: "Advertencias y precauciones especiales de empleo"
      kind: heading
    - phrase: "Información importante sobre alguno de los componentes"
      kind: standard_phrase
      severity: major
  "4.6":
    - phrase: "Embarazo"
      kind: heading
      severity: critical
```

#### Validator

```python
class QRDValidator:
    def __init__(self, template: str, version: str, language: str): ...

    def check(self, translated_segments: List[Segment],
              language_pack: LanguagePack) -> List[Defect]:
        """Returns defects for:
        - missing required section
        - sections in wrong order
        - missing mandatory phrase (with language-pack-aware tokenisation)
        - title mismatch (translated heading not matching expected title)
        """
```

#### Wiring

A new `QRD_COMPLIANCE` defect category in `app/core/defect_taxonomy.py`:

| Defect type | Default severity | Effect |
|---|---|---|
| `qrd_section_missing` | critical | BLOCKED |
| `qrd_section_out_of_order` | major | REVIEW_REQUIRED |
| `qrd_mandatory_phrase_missing` | major | REVIEW_REQUIRED (configurable per phrase) |
| `qrd_section_heading_mismatch` | minor | logged, no blocking |

The `RegulatoryAgent` (formerly `run_quality_gates` node) instantiates a `QRDValidator` per `(template, version, target_language)` and emits defects into the existing pipeline.

#### Tests

- `tests/regulatory/test_qrd_smpc_es.py` — golden EMA SmPC sample en→es passes 100%
- Same for fr, de, ar, ja
- Tampered samples (section dropped, section reordered, mandatory phrase missing) produce the right defect types
- `tests/regulatory/test_qrd_pil_es.py` — same for PIL
- Performance: validator over a 200-segment SmPC ≤ 100 ms

---

### 6.F. Spec — Validation pack as code

**Owner pod**: Audit & Validation
**Tickets**: TMX-3500 to TMX-3508
**Sprints**: 3-6
**Closes findings**: GAMP 5 / Annex 11 gap, C-06 unwound migrations

#### Goal

Every release tag `v3.x.y` produces a validation bundle with URS, FS, DS, IQ, OQ, PQ, RA, VSR, RTM, SBOM, and a cosign-signed manifest. The bundle is what an internal CSV team can take, read, and (mostly) accept.

#### Repo layout

```
validation/
├── templates/
│   ├── URS.md.j2
│   ├── FS.md.j2
│   ├── DS.md.j2
│   ├── IQ.md.j2
│   ├── OQ.md.j2
│   ├── PQ.md.j2
│   ├── RA.md.j2                  # risk assessment
│   ├── VSR.md.j2                 # validation summary report
│   └── RTM.csv.j2                # requirements traceability matrix
├── requirements/
│   ├── URS-001.yaml              # one file per requirement
│   ├── URS-002.yaml
│   └── ...
├── risks/
│   ├── RA-001.yaml
│   └── ...
└── build_pack.py                 # CI entry point
```

#### Requirement schema (`URS-001.yaml`)

```yaml
id: URS-001
title: System shall enforce role-based access control on every API route
category: security
priority: critical
acceptance_criteria:
  - id: AC-001
    description: "Every route in app/api decorated with require_permission()"
    test: tests/auth/test_rbac.py::test_every_route_has_permission
  - id: AC-002
    description: "Forbidden requests return 403 with structured WWW-Authenticate header"
    test: tests/auth/test_rbac.py::test_forbidden_response_shape
linked_fs: [FS-003, FS-004]
linked_ds: [DS-002]
linked_oq: [OQ-001]
```

#### CI job

`/.github/workflows/validation_pack.yaml` runs on every release tag:

1. Render each template against the requirements/risks YAML files.
2. Generate the RTM by walking pytest markers (`@pytest.mark.urs("URS-001")`) + linking to requirement files.
3. Run the full test suite; embed pass/fail per AC into the OQ output.
4. Run an SBOM generator (`syft` for the python and node dep trees).
5. cosign-sign the assembled bundle.
6. Attach the bundle as a GitHub Release artefact.
7. Mirror to S3 Object Lock (compliance retention).

#### RA structure

Each risk YAML has:

```yaml
id: RA-001
title: LLM hallucination produces a confident but wrong translation
gamp_5_category: 4
likelihood: medium
impact: critical
risk_score: 12   # likelihood (1-3) × impact (1-5)
mitigations:
  - back_translation_reflexion
  - quality_gate_critical_block
  - reviewer_sign_off
residual_likelihood: low
residual_impact: critical
residual_score: 4
linked_oq: [OQ-005, OQ-006]
```

#### VSR (Validation Summary Report)

Auto-generated, readable executive summary:
- Release tag, build date, signed-by
- Coverage table: URS / FS / DS / IQ / OQ / PQ
- Test results aggregated per requirement
- Open NCRs (non-conformance reports) — pulled from a `nc/` folder of YAMLs
- RA residual-risk table
- Sign-off line for QA / Validation Engineer + Tech Lead + Reg Affairs Lead

---

### 6.G. Spec — Bilingual review canvas

**Owner pod**: Reviewer Frontend
**Tickets**: TMX-3600 to TMX-3614
**Sprints**: 3-6
**Closes findings**: F-C03, F-H06, F-M03, F-M04, F-L04, parts of UX work

#### Layout (3-pane)

```
┌─────────────────────────┬─────────────────────────┬───────────────────┐
│ Source (LTR EN)         │ Target (LTR/RTL TGT)    │ Evidence panel    │
│ ─────────────           │ ─────────────           │ ─────────────     │
│ §4.1 Therapeutic ind.   │ §4.1 Indicaciones ter.  │ Defects (3)       │
│ Reduces blood pressure… │ Reduce la presión…      │  ⚠ Major: term…   │
│                         │ [highlighted defect]     │  ⚠ Minor: …       │
│ §4.2 Posology           │ §4.2 Posología          │                    │
│ Take 10 mg b.i.d…       │ Tome 10 mg dos veces…   │ Provenance        │
│                         │                         │  Model: gpt-4o    │
│                         │                         │  Prompt: trans@1  │
│                         │                         │  TM hit: none      │
│                         │                         │                    │
│                         │                         │ Audit chain ✅    │
│                         │                         │ Verified at #1234  │
└─────────────────────────┴─────────────────────────┴───────────────────┘
[← j prev] [k next →] [a accept] [r reject] [e edit] [⌘↩ sign batch] [?]
```

#### Synced scroll

The source and target panes scroll together by `segment_id` (not by pixel) so visually mismatched paragraph heights stay aligned by content.

#### Per-segment provenance pop-over

Click any segment → opens evidence panel showing:
- Model + prompt version + temperature used
- TM hit (if any) with similarity score
- Glossary terms applied
- Defects (typed; click each to see the source-target evidence pair)
- Edits history (who/when/why)
- Audit-chain position

#### Severity colour scale (WCAG AA)

| Severity | Light bg | Light fg | Dark bg | Dark fg | Glyph |
|---|---|---|---|---|---|
| Critical | `#FCE4E4` | `#7A1A1A` | `#3B0E0E` | `#FCC8C8` | ⛔ |
| Major | `#FFF3CD` | `#7A5500` | `#3B2900` | `#FFE08A` | ⚠ |
| Minor | `#E6F3FF` | `#0F4C81` | `#0A2540` | `#A8D0FF` | ℹ |
| Info | `#E8F5E8` | `#1F5A1F` | `#0F2D0F` | `#A8D8A8` | ✓ |

Contrast ratios all ≥ 4.5:1 (verified by Tailwind `--severity-*` tokens with computed values).

#### Performance

- TanStack Virtual for the segment list (only render visible + 5 above / 5 below).
- Edits debounced 1s before PATCH; local optimistic update.
- Verify-chain call cached for 30s per job.
- Target: ≤200ms input latency on a 500-segment doc on a 4-year-old MacBook.

#### i18n + RTL

`next-intl` for UI strings. RTL CSS via `dir="rtl"` on the target pane when target language is Arabic. The whole UI flips when the user's preferred language is Arabic (set in profile). Tested on Safari, Chrome, Firefox.

#### Tests

- Vitest unit tests on virtualisation, severity rendering, keyboard handlers.
- Playwright e2e scenarios: edit-and-sign a 500-segment SmPC; reject a critical defect; sign-off batch with reason.
- Visual regression via Playwright screenshots on light + dark themes per language.
- axe-core a11y check in CI.

---

## 7. Backlog (per epic)

Tickets are abbreviated; each ID resolves to an `active_tasks.md` ticket created in Sprint 0. Sizes: S = ≤2 days, M = 3-5 days, L = 1-2 weeks, XL = 2-3 weeks.

### E1 — Security baseline & multi-tenancy (21 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3010 | Add `organizations` table + tenant model | Auth | M | 1 | New table, FK from users; tests pass |
| TMX-3011 | Add `organization_id` to all domain tables | Auth | M | 1 | All tables have NOT NULL FK; backfill migration |
| TMX-3012 | Tenant-scoped session factory | Auth | M | 1 | `get_db_session(tenant_id)` filters every query; bypass blocked |
| TMX-3013 | Auth0 (or Keycloak — D-3) integration; OIDC + SAML | Auth | L | 1-2 | SSO works; MFA enforced; session timeout |
| TMX-3014 | RBAC enforcement at every API route | Auth | M | 2 | Every route in `app/api/**` decorated; integration test asserts |
| TMX-3015 | Soft-delete columns + filter logic | Auth | M | 1 | `is_deleted`, `deleted_at`, `deleted_by` on every table; hard-delete refused |
| TMX-3016 | Tenant data-isolation tests | Auth | S | 2 | Cross-tenant query returns 0 rows; verified |
| TMX-3017 | Migration unwinding into semantic Alembic revisions | Auth + Platform | L | 2 | Mega-migration replaced by 8-12 smaller revisions; downgrade path tested |
| TMX-3018 | Resilience module v2 — Redis-backed circuit breaker | Platform | M | 5 | Multi-worker setup shares circuit state; chaos-test green |
| TMX-3019 | Idempotency keys + DLQ on job submission | Platform | M | 5 | Duplicate POST same-key returns 409 with first response |

### E2 — Audit ledger v2 + e-signature (34 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3100 | `audit_events_v2` schema + migration | Audit | M | 1 | Table + indexes + constraints |
| TMX-3101 | v2 hashing implementation (canonical bytes) | Audit | M | 2 | Known-answer tests green |
| TMX-3102 | Per-event UTC timestamps; remove module-load formatTime | Audit | S | 2 | All events have unique correct ts |
| TMX-3103 | Trusted timestamp authority (FreeTSA) integration | Audit | M | 2 | Signed events carry RFC 3161 token |
| TMX-3104 | `verify_chain_integrity()` API | Audit | M | 2 | 100k-event chain ≤ 60s |
| TMX-3105 | E-signature flow + 2FA challenge | Audit + Frontend | L | 3-4 | Sign with reason; PDF manifest produced |
| TMX-3106 | Soft-delete + redaction-by-tombstone | Audit | M | 3 | Tombstone preserves chain; tested |
| TMX-3107 | Daily Merkle anchor to S3 Object Lock | Audit | L | 5-6 | Daily job; anchor verifiable; 10y retention |
| TMX-3108 | Audit timeline v2 component (server-verified state) | Frontend | M | 4 | Verified/Broken-at-N badge correct |
| TMX-3109 | v1→v2 migration script + tests | Audit | M | 4 | All historical chains migrated; v1 read-only |

### E3 — Validation pack as code (21 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3500 | `validation/templates/` URS/FS/DS/IQ/OQ/PQ/RA/VSR/RTM | Audit | M | 3 | Templates render with sample data |
| TMX-3501 | Requirement YAML schema + 30 initial requirements | Audit + PM | L | 3 | URS-001..030 cover top 25 backlog |
| TMX-3502 | RTM generator from pytest markers | Audit | M | 3 | Walks `@pytest.mark.urs(...)`; outputs CSV |
| TMX-3503 | Risk YAML schema + 12 initial risk entries | Reg + Audit | M | 4 | Cover Cat 4 LLM risks |
| TMX-3504 | CI job `validation-pack` on release tag | Audit + Platform | M | 4 | Bundle attached to GH release |
| TMX-3505 | cosign-signed release manifest + SBOM | Platform | M | 5 | Verifies offline |
| TMX-3506 | S3 Object Lock mirror for validation bundles | Platform | S | 6 | Compliance-mode retention 10y |
| TMX-3507 | VSR auto-generation from test results + RA + open NCRs | Audit | M | 6 | Reads as a real validation report |

### E4 — Document ingestion fidelity (26 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3700 | DOCX ingestion v2 with tracked-changes preservation | Pipeline | L | 1-2 | Round-trip test: open + edit + save preserves track-changes |
| TMX-3701 | DOCX export styles map + per-run formatting | Pipeline | L | 2 | Existing roundtrip refactor (in-flight) extended + tested |
| TMX-3702 | PDF ingestion v2 with OCR + tables (Azure DocIntel) | Pipeline | XL | 2-3 | Real SmPC PDF parses with tables |
| TMX-3703 | XLIFF 2.1 import / export | Pipeline | L | 3 | Round-trip with metadata preserved |
| TMX-3704 | TMX import / export | Pipeline | M | 4 | Standard interchange works |
| TMX-3705 | File-type sniffing + size cap + AV scan trigger | Pipeline | M | 1 | Rejects bad uploads |
| TMX-3706 | Page anchors preserved for review-side highlight | Pipeline | M | 4 | PDF page → segment mapping |

### E5 — PII v2 + segmentation v2 (21 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3800 | Sentence segmenter service skeleton + interface | Pipeline | M | 1 | Plug-point per language pack |
| TMX-3801 | en/es/fr/de segmenters (stanza/spaCy) + abbreviation handling | Pipeline | M | 2 | Pharma abbrev `i.v.` `b.i.d.` ok |
| TMX-3802 | ja segmenter (janome) | Pipeline | M | 3 | Tokenisation tested on golden Japanese SmPC |
| TMX-3803 | ar segmenter rules + RTL handling | Pipeline | M | 3 | RTL preserved through segmentation |
| TMX-3804 | Lists + tables preserved as discrete segments | Pipeline | M | 2 | Round-trip preserves structure |
| TMX-3805 | PII v2 — Microsoft Presidio integration | Pipeline | L | 2-3 | Replaces regex chain |
| TMX-3806 | Presidio custom recognisers for es/ar/ja | Pipeline | M | 3 | F1 ≥ 0.85 on golden PII set |
| TMX-3807 | Structured token round-trip in audit chain | Pipeline + Audit | M | 3 | Mapping is signed and recoverable |

### E6 — Quality gate hardening + EMA QRD + term-lock (26 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3400 | QualityGateService refactored — instance-based, thread-safe | Quality | M | 2 | Concurrent-runs determinism test green |
| TMX-3401 | Defect taxonomy v2 — wired to severity colour scale + telemetry | Quality | M | 4 | Tokens match `defect_taxonomy.py` |
| TMX-3402 | EMA QRD validators v1 — SmPC + PIL en/es/fr/de | Quality + Reg | L | 3-4 | Golden samples pass 100% |
| TMX-3403 | EMA QRD validators v2 — ar + ja with language-pack tokenisation | Quality + Reg | L | 4 | Golden samples pass 100% |
| TMX-3404 | Terminology lock primitive (glossary version pinning + drift report) | Quality | M | 3 | Locked terms enforced; drift reported |
| TMX-3405 | Learning service rule promotion — remove auto-approval | Quality | S | 5 | Human-signed only; tested |
| TMX-3406 | Risk-tier policy matrix verified against PRD §FR7 | Reg | S | 4 | High-risk Arabic defaults REVIEW_REQUIRED |
| TMX-3407 | New defect category: QRD_COMPLIANCE | Quality | S | 3 | Severity mapping in `defect_taxonomy.py` |
| TMX-3408 | Quality gate regression compare — fix index-error edge case | Quality | XS | 2 | First-run path safe; H-10 closed |

### E7 — Agent fabric + prompt registry + cost governance + router (29 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3200 | Prompt registry directory layout + loader | Agent | M | 1 | Loads YAML prompts; signature verifiable |
| TMX-3201 | Migrate `prompts.py` constants to v1.0.0 YAML files | Agent | M | 1 | All prompts versioned; tests still green |
| TMX-3202 | JobConfigSnapshot v2 schema with agent_topology | Agent | M | 2 | Lazy v1→v2 upgrade on read |
| TMX-3203 | Agent fabric folder rename — translator/back_translator/regulatory_qrd/refiner/terminology | Agent | M | 3 | LangGraph still works; nodes have model-card stubs |
| TMX-3204 | TerminologyAgent (NEW pre-translate node) | Agent | L | 3 | Resolves glossary + TM + EDQM lock + language pack into constraint pack |
| TMX-3205 | Deterministic agent router (`router.py`) + YAML config | Agent | L | 3-4 | Determinism tests green |
| TMX-3206 | Model pricing table + per-run cost counters | Agent | M | 2 | Reset per-run; per-tenant ceiling enforced |
| TMX-3207 | Replace hard-coded gpt-4o-mini pricing in translation_engine | Agent | S | 2 | Pricing read from YAML; in-flight bug closed |
| TMX-3208 | BackTranslator agent v2 — BERTScore-based reflexion | Agent | M | 4 | Replaces text-equality; reflexion accuracy ↑ |
| TMX-3209 | Eval harness `tests/evals/` + golden sets | Agent + QA | L | 5 | Critical-defect > 0 release-blocks |
| TMX-3210 | Drift detection job + auto-rollback on threshold breach | Agent + Platform | M | 5 | Weekly report; auto-rollback tested |
| TMX-3211 | Iteration-count refinement-loop hack removed | Agent | XS | 2 | Replace `iteration_count = 999` with explicit `force_finalize` flag |
| TMX-3212 | Audit timestamp bug — datetime UTC ISO instead of formatTime() | Agent | XS | 1 | C-05 closed |
| TMX-3213 | Output_hash placeholder replaced with real hash | Agent + Audit | XS | 4 | Real hash chained |

### E8 — Frontend IA + reviewer cockpit + design system (42 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3600 | Pick canonical IA = `/workspace/*`; redirect map | Frontend | S | 0-1 | Old routes 301 to new |
| TMX-3601 | Theme unification — light default, dark via prefers-color-scheme | Frontend + Design | M | 1 | One token system; `/new` retired |
| TMX-3602 | Design system v1 primitives — Input, Form, Dialog, Tooltip, Tabs, Breadcrumb, Table | Frontend + Design | L | 2 | All used in cockpit |
| TMX-3603 | Severity chip + audit-state badge components | Frontend + Design | M | 4 | WCAG AA contrast verified |
| TMX-3604 | Bilingual review canvas v1 — synced scroll + virtualised list | Frontend | L | 3 | 500 segments at 60fps |
| TMX-3605 | Provenance pop-over per segment | Frontend | M | 4 | Model/prompt/TM/audit position shown |
| TMX-3606 | Keyboard cockpit — j/k/a/r/e/f/g s/⌘↩/? | Frontend | M | 4 | All shortcuts work; `?` shows help overlay |
| TMX-3607 | Sign-and-save reviewer flow with reason + 2FA | Frontend + Auth + Audit | L | 4 | Manifest PDF rendered |
| TMX-3608 | Audit timeline v2 — server-verified state | Frontend + Audit | M | 4 | Click-to-expand events |
| TMX-3609 | Reviewer edit persistence + draft state | Frontend | M | 3 | Network blip preserves work |
| TMX-3610 | next-intl wired with en/de/fr/es/ja/ar | Frontend | M | 4 | All cockpit + auth strings translated |
| TMX-3611 | RTL CSS for arabic | Frontend | M | 5 | Cockpit flips correctly |
| TMX-3612 | Polling → SSE for job status (or polling with backoff) | Frontend + Platform | M | 5 | No QPS storms |
| TMX-3613 | A11y audit + WCAG AA fixes | Frontend + Design | M | 5 | axe + manual screen-reader pass on ar/ja |
| TMX-3614 | Vitest unit + Playwright e2e suites; CI gate | Frontend + Platform | M | 1-2 | Upload→translate→review→sign→audit happy path |
| TMX-3615 | CSP / HSTS / X-Frame-Options / Permissions-Policy via next.config.ts | Frontend | S | 1 | Security headers verified |
| TMX-3616 | Cookie hardening — httpOnly Secure SameSite=Strict + CSRF tokens | Frontend + Auth | M | 1 | Penetration test passes |
| TMX-3617 | Tiptap output sanitisation via DOMPurify | Frontend | S | 2 | Stored-XSS test passes |
| TMX-3618 | File upload validation + size cap + AV trigger | Frontend + Pipeline | M | 1 | Bad uploads rejected |
| TMX-3619 | Wizard state in URL not component state | Frontend | S | 3 | Refresh + back-button preserve state |

### E9 — Observability, tracing, evals (18 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3900 | OpenTelemetry SDK wired across LangGraph nodes | Platform | M | 1 | One span per node + LLM call |
| TMX-3901 | Prometheus metrics — counters + histograms | Platform | M | 2 | Metrics scrape clean |
| TMX-3902 | Grafana dashboards — translation, quality, cost, audit | Platform | M | 4 | Pilot-readable |
| TMX-3903 | Cost dashboard with per-tenant ceiling + alerts | Platform | M | 4 | Alert + hard-block tested |
| TMX-3904 | Drift detection + weekly per-pair quality report | Platform | M | 5 | Report rendered into dashboard |
| TMX-3905 | Auto-rollback to prior prompt version on drift breach | Platform + Agent | M | 5 | Tested with synthetic regression |
| TMX-3906 | Structured log schema + redaction (PII never in logs) | Platform | M | 5 | Audit verifies no PII leaks |

### E10 — Pilot readiness pack (21 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-4000 | CAIQ-Lite drafted + evidence-mapped | Pilot | M | 5 | External CISO advisor signs off |
| TMX-4001 | DPA template + sub-processor list | Pilot + Reg | M | 5 | Pharma counsel approves |
| TMX-4002 | BAA template (HIPAA) | Pilot + Reg | M | 5 | Pharma counsel approves |
| TMX-4003 | LLM provider qualified-supplier files (OpenAI / Anthropic / DeepL) | Pilot + Reg | M | 5 | SOC 2 + ISO + ToS no-training + DPA assembled per provider |
| TMX-4004 | EU AI Act technical documentation skeleton | Reg + PM | L | 6 | Technical doc + risk mgmt + post-market mon templates |
| TMX-4005 | Per-LLM × language-pair model cards | Reg + Agent | L | 5-6 | 5 langs × 3 LLMs = 15 cards |
| TMX-4006 | FDA AI/ML credibility framework — context of use + model risk + credibility plan | Reg + PM | M | 6 | Doc reviewed by external regulatory adviser |
| TMX-4007 | Vendor security questionnaire pass (CAIQ-Lite ≥ 80%) | Pilot + SecEng | S | 6 | Verified |
| TMX-4008 | Pilot agreement template + conversion-to-production clause | Pilot + Sales | M | 6 | Counsel-approved |
| TMX-4009 | First 2 pilot LOIs → master agreements | Sales + Pilot | XL | 5-6 | At least 2 signed |
| TMX-4010 | Vendor questionnaire response runbook | Pilot | M | 6 | Reusable across pilots |
| TMX-4011 | Privacy notice + DPIA template + transfer-impact assessment template | Reg | M | 5 | Aligned with EDPB guidance |

---

## 8. KPIs per sprint

A small number of metrics that should move every two weeks. If they don't, the release is in trouble — not "behind schedule" trouble, *off-strategy* trouble.

| KPI | Sprint 0 | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | Sprint 5 | Sprint 6 |
|---|---|---|---|---|---|---|---|
| Frontend build pass rate | **100%** | 100% | 100% | 100% | 100% | 100% | 100% |
| Critical/High open from review doc | 25→23 | 23→17 | 17→11 | 11→6 | 6→3 | 3→1 | 1→**0** |
| Test coverage (backend) | unmeasured | ≥40% | ≥55% | ≥65% | ≥70% | ≥75% | ≥**80%** |
| Audit chain v2 verify time (10k events) | n/a | n/a | ≤30s | ≤20s | ≤15s | ≤10s | ≤**8s** |
| Reviewer cockpit input latency at 500 segments | n/a | n/a | n/a | ≤500ms | ≤300ms | ≤200ms | ≤**200ms** |
| Critical defect rate on golden eval set | n/a | n/a | n/a | n/a | ≤2 / 1000 segs | ≤1 / 1000 | **0** |
| Vendor questionnaire pass rate | 0% | 20% | 40% | 60% | 70% | 80% | ≥**80%** |
| Validation pack rendered for tag | no | no | no | partial | partial | yes | **yes** |
| Pilots in conversation → signed | 0 → 0 | 1 → 0 | 2 → 0 | 3 → 0 | 4 → 0 | 4 → 1 | 4 → **2** |
| Per-tenant cost telemetry live | no | no | no | partial | yes | yes | **yes** |
| RTL + i18n on cockpit | no | no | no | no | en/de/es | + ja/ar/fr | **all 6** |

If any KPI stalls for **two consecutive sprints**, the program lead escalates to CEO at the next CEO readout (we don't wait for the post-mortem).

---

## 9. Decisions only the CEO can make

These are the items I cannot decide alone. Each blocks one or more workstreams; ideally all are decided before Sprint 0.

### D-1 — Pilot customer profile (target two)
**Question**: Which two pilot customers should we go after? Options:
- **(a) One top-20 pharma + one global CRO.** Highest credibility / highest validation friction.
- **(b) Two mid-market pharma (€500M-€2B revenue).** Faster sale, smaller validation team, more willing to be a reference.
- **(c) One pharma + one medical-device (MDR/IVDR).** Extends use-case but loads ISO 13485 onto v3.
- **(d) Two CROs.** Volume play; less regulatory depth required.

**Recommendation**: (b) — fastest revenue, lowest validation friction, highest probability of converting on time. (a) is the right *second* pair after v3.0 ships.

**Blocks**: E10 pilot agreement scope.

### D-2 — Audit anchor strategy
**Question**: Where do daily Merkle roots get anchored?
- **(a) S3 Object Lock with compliance-mode retention.** Cheapest, AWS-native, accepted by most CSV teams.
- **(b) AWS QLDB.** Was the original suggestion in your review doc; AWS announced QLDB end-of-life in mid-2024. **Not recommended.**
- **(c) A public ledger (Ethereum / Bitcoin testnet via OpenTimestamps).** Most cryptographically defensible; raises "blockchain" objections from some pharma buyers.
- **(d) Both (a) and (c).** Belt and braces; tells a fantastic story to reviewers.

**Recommendation**: (a) for v3.0 (ship fast); evaluate (d) for v3.1 once a customer asks.

**Blocks**: E2.7 daily Merkle anchor.

### D-3 — Auth provider
**Question**: Which IdP for v3.0?
- **(a) Auth0.** Hosted, fastest integration, expensive at scale. Good for v3 pilot, may renegotiate later.
- **(b) Keycloak self-hosted.** Free, requires ops work; gives more control + pharma customers prefer "no third-party identity custodian".
- **(c) Okta.** Enterprise-popular but slower-to-integrate; some pilot buyers will already have Okta tenants and prefer SAML federation.
- **(d) Build it ourselves on top of `python-jose` + WebAuthn.** Don't.

**Recommendation**: (a) for the pilot — speed-to-market wins. Architect the integration so swap to (b) or (c) is a config change, not a refactor.

**Blocks**: E1.13 auth integration.

### D-4 — LLM strategy
**Question**: Hosted only, BYOK only, or hybrid for v3.0?
- **(a) Hosted only — TransMax pays OpenAI/Anthropic/DeepL.** Fastest for pilot; commercial risk on us if a customer demands BYOK after pilot.
- **(b) BYOK only — customer provides keys.** Pushes governance burden to customer; some will refuse pilot on this alone.
- **(c) Hybrid — hosted by default, BYOK optional with surcharge.** Best of both, more engineering work; about 1-2 weeks of E1 / E7 effort.

**Recommendation**: (a) for v3.0 pilot; promise (c) for v3.1. Limits scope; gives commercial cover.

**Blocks**: E10 pilot agreement, E7 cost governance.

### D-5 — Hosting & data residency
**Question**: Single-region or multi-region for v3.0?
- **(a) Single region, EU-Central (Frankfurt).** Simplest; fits EU pilot customers; US customers may refuse on residency.
- **(b) Single region, US-East.** Mirrors most US pharma; misses EU GDPR posture.
- **(c) Two regions, EU-Central + US-East.** Doubles infra work; better story, but slower to v3.0.

**Recommendation**: (a) — pair with D-1 EU-focused pilot strategy. v3.1 adds US-East.

**Blocks**: E1 / E10 GTM positioning.

### D-6 — Pricing model for pilot
**Question**: How do we price pilots?
- **(a) Flat €25k–€75k for 90-day pilot, capped scope, conversion-to-production clause.** Standard.
- **(b) Per-word with €5k minimum.** Aligns to LSP pricing; harder to forecast revenue.
- **(c) Hybrid: €25k base + €0.05/word above 100k words.** Hedged.

**Recommendation**: (a) — clearest commercial story; pilot is about validation not maximising MRR.

**Blocks**: E10 pilot agreement template, sales motion.

### D-7 — Branding & positioning
**Question**: Are we "TransMax — agentic regulatory translation platform" or "TransMax — pharma-grade AI for regulated content"? The first is a feature claim, the second is a product claim.

**Recommendation**: positioning is a Phase 1 GTM exercise. Defer formal positioning to Sprint 2 — by then E1-E5 will have shaken out which differentiator (agentic vs. compliance-deep) is more credible to ship.

**Blocks**: marketing site, pitch deck, customer comms.

### D-8 — Open-source strategy
**Question**: Do we open-source the LangGraph quality-gate library and prompt registry as a "TransMax Audit Kit", to acquire developer mindshare?
- Pros: distribution, hiring signal, regulator goodwill, hardens our own code.
- Cons: gives competitors a free template; takes ~4 weeks of effort to extract cleanly.

**Recommendation**: defer to v3.1 unless a compelling distribution partner appears (e.g. LangChain wants to feature us). The quality gate is one of our two strategic assets; don't give it away for free until pilots are signed.

**Blocks**: marketing motion (not v3.0 release).

---

## 10. Risks (release-scoped)

The May 2026 review doc captured the strategic risk register. These are **release-specific** risks that have a real chance of slipping v3.0.

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Auth integration takes longer than planned (Auth0 quirks at SAML federation) | Medium | High | Buffer Sprint 1-2; if blocking, accept "OIDC only, SAML in v3.1" | Auth pod |
| Audit-chain v1→v2 migration loses historical data | Low | Critical | Staging dry-run; v1 stays read-only forever; CSV review of migration script | Audit pod |
| EMA QRD validators ship without ar/ja in time | Medium | Medium | Sprint 4 buffer for ar/ja; if slipping, accept "v3.0 ships en/es/fr/de; ar/ja in v3.1" | Quality+Reg pod |
| Reviewer cockpit performance budget missed at 500 segments | Medium | Medium | Sprint 5 buffer; virtualisation library swap option (TanStack → react-window) | Frontend pod |
| Validation pack templates rejected by external CSV review | Medium | High | Engage external CSV consultant in Sprint 3; review templates against ISPE GAMP 5 reference | Audit pod |
| LLM provider terms-of-service change blocks pharma data use mid-release | Low | Critical | Multi-provider abstraction lands Sprint 2; on-prem fallback ready as v3.1 backstop | Agent pod |
| Pilot customers don't sign by end of Sprint 6 | Medium | High | Three pilots in pipeline minimum; conversion target 2/3; LOIs by Sprint 5 | Pilot pod |
| EU AI Act enforcement starts before our conformity skeleton is ready (2026-08-02) | Medium | High | E10.4 lands in Sprint 6; if slipping, ship "conformity skeleton + roadmap" rather than nothing | Reg pod |
| Sprint 3 audit-ledger work blocks E3 validation pack | Low | Medium | E3 templates can be drafted independently in Sprint 3; integration in Sprint 4 | Audit pod |
| Frontend a11y audit reveals deeper-than-expected gaps | Medium | Medium | Run preliminary axe-core in Sprint 2 (not 5); surface gaps early | Frontend pod |

A risk that isn't on this list because it's *certain*: the team will discover something hard in week 4 that wasn't in the plan. v3 carries a 15% schedule contingency (effectively half a sprint of unallocated time across the team) for that.

---

## 11. Working agreement (how this team operates for 12 weeks)

Borrowed from `COLLABORATION.md`, refined for v3.0:

- **Tickets are claimed, not assigned.** Engineers move tickets from `[READY]` → `[WIP]` → `[Done]` in `.context/active_tasks.md`. The Program Lead (me) keeps the backlog ordered; if the next-priority ticket isn't being picked up, the standup says so and we re-plan in real time.
- **Every PR carries a ticket ID and an AC checklist.** Reviewers check AC, not vibes.
- **Every PR carries the validation-pack delta**: which URS / FS / RA / OQ entries this PR creates or modifies. RTM is regenerated by CI; PRs with no validation-pack tie are flagged at review.
- **No mock-fallback merges, ever.** If the backend can't be called, the frontend shows an explicit error. Reviewer code that simulates results is rejected at review by default.
- **No `iteration_count = 999` patterns.** If a control-flow exit needs a sentinel, it's an explicit boolean state field, not a magic number.
- **Trunk-based development.** Feature branches live ≤ 3 days. Long-running work hides behind feature flags read from a config-of-truth in DB (not env vars).
- **Signed releases.** Every release tag is cosign-signed. Unsigned releases cannot deploy to production.
- **Daily 10-min async standup** in `.context/handoff_log.md` — what I shipped, what I'm doing, what's blocking. The Program Lead reads it at 09:00 daily.
- **Retro after every sprint.** The retro produces three things: kept (what worked), changed (what we'll do differently), blocked (what only the CEO can unblock).
- **CEO readout monthly** (or sooner if a KPI stalls): one-pager, KPI table, decisions needed, risk register delta. Always under 1,000 words.

---

## 12. Appendices

### Appendix A — How my code-review findings (2026-05-01) map to v3.0 tickets

This is the bridge from my earlier "in-flight + tech-debt" review (saved in memory at `tech_debt.md` + `inflight_work.md`) to the v3.0 plan.

| Memory entry | v3.0 ticket | Note |
|---|---|---|
| `graph.py:141` model hard-coded "gpt-4o" placeholder in audit | TMX-3202 | Model captured in JobConfigSnapshot v2 from agent_topology |
| `graph.py:149,438` formatTime() bogus timestamp | TMX-3212 / TMX-3102 | Per-event UTC ISO timestamps |
| `graph.py:432` iteration_count=999 hack | TMX-3211 | Explicit force_finalize flag |
| `graph.py:615` placeholder_hash | TMX-3213 | Real output hash chained |
| `runner.py:48` doc.status="error" non-enum | TMX-3015 (peripheral) | New ERROR status added to enum |
| `transmax.db` committed in git | TMX-3002 | gitignore + history-rm |
| Dual model layer (database.py vs translation.py) | TMX-3017 | Migration unwinding rationalises overlapping models |
| Hard-coded gpt-4o-mini pricing in translation_engine | TMX-3207 | Pricing table |
| Per-engine token counter scoping | TMX-3206 | Per-run scope |
| DOCX export content-map collision risk | TMX-3701 | segment_id propagated through to export |
| 30+ debug log artefacts at repo root | TMX-3002 | gitignore expansion |
| requirements.txt no version pins | (out of scope v3.0) | Pin in v3.1 with renovate-driven updates |

### Appendix B — Cross-walk to the May 2026 review doc

| Review doc section | v3.0 epic | Notes |
|---|---|---|
| §3.2 Critical (C-01 .. C-13) | E1, E2, E5, E6, E7 | All 13 closed in v3.0 |
| §4.2 Frontend Critical (F-C01 .. F-C05) | E8 | All 5 closed in Sprint 0-1 |
| §3.3 High (H-01 .. H-20) | E1-E10 distributed | Most closed; H-15 (OTel) → E9; H-20 (QRD) → E6 |
| §3.4 Medium (M-01 .. M-12) | E4, E5, E7, E8 | Closed where pilot-blocking; M-04 cost cap → E7; M-11 PDF/A → v3.1 |
| §4.3 Frontend H/M (F-H01 .. F-M06) | E8 | All closed in v3.0 |
| §5 Compliance gap matrix | E1, E2, E3, E6, E10 | Part 11 + GDPR + EU AI Act + EMA QRD covered; ISO certs are Phase 2 |
| §6 Competitive benchmark | (informs positioning) | Drives D-7 |
| §7 Strategic positioning | (informs all) | Validates "agentic-first, pharma-native" thesis |
| §8.1 Phase 0 (now) | Sprint 0 | All actions banked |
| §8.2 Phase 1 (90 days) | Sprints 1-6 (this release) | This document is the operational unfolding of Phase 1 |
| §8.3 Phase 2 (3-6 mo) | (v3.1+) | Out of scope for v3.0 |
| Appendix A (Top 25 backlog) | Tickets in §7 | Each Top-25 item has a TMX-3xxx ticket |
| Appendix B (Certification roadmap) | E10 | v3.0 ships skeletons; certs are Phase 2-3 |

### Appendix C — Backlog summary (count by epic and pod)

| Epic | Tickets | Story points |
|---|---|---|
| E1 | 10 | 21 |
| E2 | 10 | 34 |
| E3 | 8 | 21 |
| E4 | 7 | 26 |
| E5 | 8 | 21 |
| E6 | 9 | 26 |
| E7 | 14 | 29 |
| E8 | 20 | 42 |
| E9 | 7 | 18 |
| E10 | 12 | 21 |
| **Total** | **105** | **259** |

| Pod | Tickets | Approximate workload share |
|---|---|---|
| Auth & Tenancy | 12 | 12% |
| Audit & Validation | 19 | 18% |
| Document Pipeline | 13 | 13% |
| Quality & Regulatory | 10 | 10% |
| Agent & AI | 14 | 13% |
| Reviewer Frontend | 20 | 19% |
| Platform & Observability | 9 | 8% |
| Pilot/GTM | 8 | 7% |

### Appendix D — What v3.1 should pick up (post-pilot)

For when the pilot is signed and we're scoping the next release. Strictly *parking lot* — do not pull these into v3.0:

- Veeva Vault PromoMats / RIM connector
- Documentum / SharePoint connector
- eCTD module 1 v3.1.1 mapping + LORENZ docuBridge connector
- IDMP / SPOR connector
- ISO 17100 / ISO 18587 process documentation + certification
- ISO 27001 / SOC 2 Type II evidence collection (Phase 2)
- ISPOR linguistic-validation graph (forward / reconciliation / back / cognitive debriefing)
- EDQM Standard Terms live subscription + ETL
- Multi-region deployment + customer-managed keys
- BYOK option for LLM providers
- Mobile read-only reviewer surface
- WebAuthn passkeys for e-signature
- Per-tenant LoRA adapters / fine-tuning
- Open-source "TransMax Audit Kit" extraction
- Marketing site + first-party content

---

## 13. Closing note

The May 2026 review told us **what's wrong**. This plan tells us **what we ship next, in what order, by whom, against what acceptance criteria, with what evidence**.

The deliverable of v3.0 is not a feature set. It is a **defensible artefact**: a TransMax that a pharma's QA / RA / IT-security triad can put through their normal vendor-onboarding gauntlet, and that emerges with a vendor-questionnaire score above 80%, a validation pack that survives an internal CSV review, and a signed pilot agreement.

If we land that, v3.1 (connectors + ISPOR + certifications) and v4.0 (multi-agent fabric + open-source kit + regulator-grade attestation) are scope choices. If we don't, every other future ambition rests on sand.

— *Antigravity*
*Program Lead, TransMax*
*Drafted 2026-05-01, awaiting CEO sign-off*

---

# Part II — Headless Agent Integration Addendum

**Added**: 2026-05-01 (later same day, after reading `TRANSMAX_HEADLESS_AGENT_SPEC.md` v0.9, May 2026)
**Reads alongside**: `TRANSMAX_HEADLESS_AGENT_SPEC.md` (the headless spec) and Part I of this document (the 12-week plan).

## A. What this addendum is

The headless-agent spec articulates a **vision** I had under-served in Part I: TransMax as **regulated infrastructure**, callable from a UI, REST, MCP, SDK, CLI, webhooks, review-handoff URL, connectors, and agent-to-agent runtimes — one engine, many surfaces, the same audit ledger every time.

Re-reading the v3.0 plan against the headless spec, the right move is **not** to absorb the entire headless spec into v3.0 (that would 2-3× the scope and lose the pilot). The right move is:

1. **Adopt the design principles** as v3.0 design principles retroactively.
2. **Adopt the canonical job lifecycle and the surface-adapter pattern** as v3.0 architecture.
3. **Add a new epic E11 — Headless Foundation** with the *minimum* surface set that hardens what already exists (REST + MCP + Python SDK + Webhooks + S3/SFTP connector) without inventing new surfaces.
4. **Replace my E3 (validation pack) with the headless spec's 9-track validation strategy and per-release validation bundle**. The headless spec's validation thinking is more mature than mine; my E3 and E9 collapse into the headless spec's Tracks 1-9.
5. **Adopt the headless spec's pricing model**, closing Decision D-6.
6. **Defer** TypeScript SDK, CLI, Review-handoff URL, Veeva / SharePoint / eCTD connectors, Agent-to-agent registrations, public `verify.transmax.io` page to v3.1+.
7. **Reconcile** one inconsistency: the headless spec mentions AWS QLDB in §7.5, which AWS announced end-of-life mid-2024. Sticking with my recommendation (S3 Object Lock + OpenTimestamps option) — the headless spec needs an editorial pass to update §7.5.

The rest of this addendum specifies each move.

---

## B. Design principles adopted into v3.0 (retroactive)

The headless spec's nine principles become v3.0's design principles. They were implicit in Part I; making them explicit costs nothing and aligns the engineering and regulatory teams.

1. **One engine, many surfaces.** All surfaces (UI, REST, MCP, SDK, CLI, connectors) call the same orchestration core. There is no "lite" engine.
2. **Contract-first.** Every surface is specified as an OpenAPI 3.1 document, an MCP tool schema, or a typed SDK interface, before code. Schemas are versioned and code is generated from them.
3. **Async-first.** Translation jobs are long-running. All surfaces are designed for async submission with webhook or poll callbacks.
4. **Audit-by-default.** Every call lands on the same hash-linked ledger with the same JobConfigSnapshot, regardless of surface.
5. **Tenant-isolated by construction.** Multi-tenancy enforced at the data layer, not at the surface.
6. **Idempotent and retry-safe.** Every state-mutating call accepts an idempotency key.
7. **Explainable.** Every translation, every defect, every quality-gate verdict has a structured evidence object and a human-readable rationale.
8. **Reviewer optional, not absent.** Headless mode supports a *review-handoff URL* (deferred to v3.1) so customers deep-link from their own portal into a hosted review surface. The UI is optional, never mandatory, but always available.
9. **Compliance is shipped, not configured.** EU AI Act conformity package, 21 CFR Part 11 attestation, GAMP 5 VSR and EMA QRD validators are part of every release — they are not opt-in features.

These are non-negotiable. Any v3.0 PR that violates them is rejected at review.

---

## C. Architecture delta: Internal Service API + surface adapter pattern

The single most important architectural insight in the headless spec is in §5.1: **surfaces are thin adapters; one Internal Service API does all the work**. This must land in v3.0 because every surface added later (TS SDK, CLI, connectors) becomes a mechanical translation rather than a re-implementation of business logic.

### Concrete shape

```
transmax/
├── core/
│   ├── service.py            # the Internal Service API — typed, in-process
│   ├── lifecycle.py          # canonical job lifecycle (the state machine)
│   ├── middleware/           # idempotency, RBAC, audit, rate-limit, cost-ceiling
│   └── ...
├── adapters/
│   ├── rest/                 # FastAPI; thin
│   ├── mcp/                  # FastMCP / custom; thin
│   ├── sdk/                  # generated client
│   ├── webhooks/             # dispatcher + signer
│   └── connectors/
│       ├── s3/
│       └── sftp/
└── ...
```

### Internal Service API (the only surface-of-truth)

```python
class TransmaxService(Protocol):
    def submit_job(self, request: SubmitJobRequest, *, ctx: CallContext) -> Job: ...
    def get_job(self, job_id: UUID, *, ctx: CallContext) -> Job: ...
    def list_jobs(self, query: ListJobsQuery, *, ctx: CallContext) -> Page[Job]: ...
    def cancel_job(self, job_id: UUID, *, ctx: CallContext) -> Job: ...
    def request_review(self, job_id: UUID, policy: ReviewPolicy, *, ctx: CallContext) -> ReviewHandle: ...
    def sign_off(self, request: SignOffRequest, *, ctx: CallContext) -> SignedManifest: ...
    def verify_audit_chain(self, job_id: UUID, *, ctx: CallContext) -> ChainStatus: ...
    def export_evidence_bundle(self, job_id: UUID, *, ctx: CallContext) -> EvidenceBundleRef: ...
    def register_glossary_term(self, request: RegisterTermRequest, *, ctx: CallContext) -> Term: ...
    def register_rule(self, request: RegisterRuleRequest, *, ctx: CallContext) -> Rule: ...
    # ... full surface in core/service.py
```

`CallContext` carries `tenant_id`, `actor`, `actor_kind`, `surface` (`web|rest|mcp|sdk|cli|webhook|connector_s3|...`), `correlation_id`, `idempotency_key`. Every audit event records the full context — closing the headless spec's §7.5 requirement.

### Canonical job lifecycle

The headless spec's §5.2 lifecycle becomes the canonical state machine. v3.0 retires the implicit lifecycle scattered across `Document.status` + `Segment.status` + `TranslationJob.status` and replaces it with a single `Job` aggregate with explicit transitions:

```
SUBMITTED → VALIDATED → SEGMENTED → CONSTRAINTS_LOADED → TRANSLATED →
QUALITY_GATED → [REFINING ↻ ≤3] → BACK_TRANSLATED → REVIEW_REQUIRED →
REVIEWED → SIGNED_OFF → EXPORTED → ARCHIVED
```

Plus terminal-error states `CANCELLED` and `FAILED`. Each transition emits a typed event on the audit ledger AND a webhook event (where webhooks are subscribed). Migration: existing `Document.status` values map onto the new lifecycle in the v1→v2 audit migration (TMX-3109).

This lands in **Sprint 2** as a refactoring ticket (new TMX-3220) blocking E7 (agent fabric).

---

## D. New epic E11 — Headless Foundation (minimum viable headless)

Add to §4 and §7 of Part I:

| ID | Epic | Owner pod | Sprints | Story points |
|---|---|---|---|---|
| **E11** | Headless Foundation: REST v2 + Python SDK + MCP harden + Webhooks + S3/SFTP | Platform & Observability + Agent & AI | 2-6 | 26 |

Rationale: pilots will sign on the hosted UI, but a usable headless surface is what makes a CRO partner or a Veeva-embedded workflow viable for v3.1 — and the work to extract the Internal Service API has to happen *now* so the engine doesn't fork between UI logic and headless logic.

### E11 backlog (26 SP)

| ID | Title | Pod | Size | Sprint | AC short |
|---|---|---|---|---|---|
| TMX-3220 | Internal Service API extraction (`transmax/core/service.py`) | Platform | L | 2 | All routes call the new API; no business logic in adapters |
| TMX-3221 | Canonical job lifecycle state machine | Agent + Audit | M | 2 | Job aggregate; transitions tested |
| TMX-3222 | Idempotency middleware (24h cache; 409 on hash mismatch) | Platform | M | 2 | Tests pass; SDK emits keys |
| TMX-3223 | RBAC middleware between adapter and Internal Service API | Auth | M | 2 | Surfaces never rule on permissions |
| TMX-3224 | OpenAPI 3.1 source-of-truth at `openapi/transmax-v2.yaml` | Platform | M | 3 | Generated types feed Python SDK; Spectral lint green |
| TMX-3225 | REST API v2 (POST jobs, GET job, GET events SSE, GET evidence, POST sign-off, GET audit/verify) | Platform | L | 3 | All endpoints conform to OpenAPI; integration tests green |
| TMX-3226 | Webhooks v1 — Ed25519-signed POST, retry up to 24h, DLQ to audit ledger | Platform | M | 4 | Customer receiver verifies signature; replay protection works |
| TMX-3227 | Python SDK 1.0.0 (`transmax-sdk` on PyPI) — sync + async, retry, idempotency-key gen | Platform | L | 3-4 | Round-trip tested against staging; package signed |
| TMX-3228 | MCP server hardening — bearer auth, schema parity with OpenAPI | Agent | M | 4 | Tools registered; mcp-tools.json generated |
| TMX-3229 | S3 connector v1 — object-arrived → submit job | Platform | M | 5 | E2E test: drop file in S3 → job appears in dashboard |
| TMX-3230 | SFTP connector v1 — watch folder → submit job | Platform | M | 5 | E2E test |
| TMX-3231 | Customer-provided webhook receiver — inbound POST → submit job | Platform | S | 5 | Signed-payload validation |
| TMX-3232 | Surface-parity test harness (Track 2 of validation strategy) | QA + Platform | L | 4-5 | Top 12 journeys pass on REST + Python SDK + MCP + UI server actions |

### What E11 explicitly does NOT do (deferred to v3.1+)

- ❌ TypeScript SDK (`@transmax/sdk`) — Phase 2
- ❌ CLI binary (`transmax`) — Phase 2
- ❌ Review-handoff URL with SAML/OIDC federation — Phase 2 (architect for it now)
- ❌ Veeva Vault / SharePoint Online / Documentum / eCTD connectors — Phase 2
- ❌ Agent-to-agent registrations (Anthropic Agent SDK, OpenAI Agents SDK, LangGraph Cloud, AutoGen) — Phase 3
- ❌ Public `verify.transmax.io` chain-verification page — Phase 3
- ❌ `trust.transmax.io` customer trust centre — Phase 2 (we ship the bundles; the public site is later)
- ❌ Self-service "validation playground" sandbox (Track 7 customer acceptance) — Phase 2

### Impact on existing epics

E11 changes work in earlier epics:

- **E1.13** (Auth0 / Keycloak) gains a requirement: **scoped API keys** with `jobs:submit`, `jobs:read`, `audit:verify`, `glossary:write`, `webhooks:manage` etc. Not just user-bearer JWTs.
- **E2.4** (`verify_chain_integrity` API) becomes a **public REST endpoint** at `GET /v2/orgs/{org_id}/audit/verify` — same internals, but exposed.
- **E5** (PII v2) gains a requirement: **PII redaction at the structured-log boundary** (per headless spec §7.6). PII never reaches logs.
- **E7.6** (BackTranslator BERTScore) plus the **`evidence_refs`** field on every audit entry (per headless spec §7.5) — every defect carries a pointer to the evidence document.
- **E8** (Reviewer cockpit) gains a requirement: the cockpit must be **renderable without the workspace shell** (per headless spec §6.7), so v3.1 review-handoff URL is "remove the chrome" not "rebuild the page".

These are minor amendments to existing tickets, not new tickets — they slot in at sprint planning.

---

## E. Validation strategy: replace Part I's E3 with the headless spec's 9 tracks

The headless spec's §10 is more mature than my E3 / E9 sketch. **Adopting it wholesale** for v3.0:

| Track | Purpose | What it produces per release | Maps to my Part I epics |
|---|---|---|---|
| **Track 1 — Contract Validation** | Surface conforms to schema | Spectral report; Schemathesis report; Pact verification report | E3 + E11 (subsumes my E3.4 CI job) |
| **Track 2 — Surface Parity** | Identical inputs through different surfaces produce identical outcomes | Surface Parity Matrix CSV | E11 (TMX-3232) |
| **Track 3 — Behavioural & Golden-Path** | Documented behaviours hold under normal and adverse | Golden corpus pass rate; snapshot diff; failure-injection report | E6 + E9 (subsumes E9 evals) |
| **Track 4 — Security Validation** | No unauthn / unauthz / replay / forge / excess succeeds | Authn matrix; Authz matrix; SAST; DAST; SBOM; pen-test summary | E1 + E10 |
| **Track 5 — Performance & SLO** | Documented SLOs hold under load | SLO conformance; load-test artefacts | E9 (extends my dashboards into a release deliverable) |
| **Track 6 — Compliance** | Regulator-facing artefacts shipped per release | VSR signed by Programme Lead + RA Lead; Part 11 attestation; GAMP 5 lifecycle docs; EU AI Act technical documentation; FDA credibility framework artefacts; EMA QRD validator runs; EDQM dataset version note; ISO 17100/18587 process evidence | E3 + E10 (this *is* the validation pack) |
| **Track 7 — Customer Acceptance & Sandbox** | Customers can self-validate before signing | Sandbox tenants; self-service playground; acceptance test pack; customer-validation council notes | **Deferred to Phase 2** (out of v3.0) |
| **Track 8 — Independent Third-Party Attestation** | External parties confirm what we claim | Annual SOC 2 / ISO 27001 / pen-test / chain-anchor review reports | **Deferred to Phase 2-3** (we engage the auditor in v3.0; the attestation lands in Phase 2-3) |
| **Track 9 — Continuous Validation in CI/CD** | All of the above runs on every commit | PR gates; merge gates; nightly; weekly; monthly chaos | E9 (this *is* the CI strategy) |

### Per-release validation bundle (replaces my Part I §6.F deliverable list)

Adopt the headless spec §10.10 bundle structure verbatim. Every v3.x.y release tag produces:

```
release-bundle-v3.x.y/
├── vsr.pdf                        # Validation Summary Report, signed
├── openapi.yaml                   # pinned API surface
├── mcp-tools.json                 # pinned MCP surface
├── sbom.cdx.json                  # signed CycloneDX SBOM
├── slsa-attestation.intoto.jsonl  # SLSA L3 supply-chain provenance
├── surface-parity.json            # Track 2 results
├── golden-corpus.json             # Track 3 pass rate
├── slo-report.json                # Track 5 conformance
├── security-summary.pdf           # Track 4 summary
├── compliance-pack/
│   ├── part11_attestation.pdf
│   ├── gamp5_vsr.pdf
│   ├── eu_ai_act_technical_docs/
│   ├── fda_credibility_artefacts/
│   ├── ema_qrd_validator_runs.pdf
│   └── edqm_dataset_version.txt
└── manifest.json                  # signed manifest with hashes of every other file
```

Customers download via `GET /api/v2/orgs/{org_id}/releases/{tag}/validation-bundle` (gated behind the Regulatory Pack scope per §F).

### CI gates (Track 9 — adopted into our CI policy)

- **PR gate** (≤ 12 min): unit tests; contract lint (Spectral); contract conformance (Schemathesis quick); surface-parity quick suite (3 journeys × 3 surfaces); SAST (Semgrep); secret scanning.
- **Merge-to-main gate**: full surface-parity suite; snapshot regression; SBOM generation; signed artefact build.
- **Nightly**: full golden-corpus regression; SLO load test on staging; full audit-chain integrity test (1M events synthetic); failure-injection suite; dependency vulnerability scan.
- **Weekly**: DAST surface scan (OWASP ZAP); review handoff browser test (Playwright on Chrome / Firefox / Safari / Edge — once review-handoff lands in v3.1).
- **Monthly**: chaos engineering on staging — kill an LLM provider, kill the audit anchor, kill a region.
- **Per-release**: full Validation Summary Report assembled and signed.

### What this changes in Part I

- **E3 (Validation pack as code)** → re-scoped as "Track 6 + Track 9 implementation" with the bundle structure above.
- **E9 (Observability + evals)** → re-scoped as "Track 5 + Track 9 implementation".
- **New ticket TMX-3508**: Spectral + Schemathesis + Pact in CI (Track 1).
- **New ticket TMX-3509**: Performance budget gates (10% regression fails CI) (Track 5).
- **New ticket TMX-4012**: Engage SOC 2 auditor; evidence collection scaffolding via Drata/Vanta (Track 8 prep).

---

## F. Pricing — closes Decision D-6

The headless spec §8 has already made the pricing decision. **D-6 in Part I is now resolved**:

| Tier | Inclusions | Indicative price |
|---|---|---|
| **Headless Foundation** | REST API + Python SDK + MCP + Webhooks; standard rate limits; shared region; community support | €0.04–€0.08 per word + €5,000/mo platform fee |
| **Headless Enterprise** | Foundation + TS SDK + CLI + connectors + dedicated region + SLA + 24/7 support + customer-managed keys | €0.08–€0.15 per word + €15,000–€40,000/mo platform fee |
| **Platform** | Hosted UI + reviewer seats + everything in Headless Enterprise | + €120/seat/mo |
| **Regulatory Pack (add-on)** | Part 11 attestation, GAMP 5 VSR, EU AI Act conformity package, FDA credibility artefacts, EMA QRD validators, EDQM standard-term enforcement, signed evidence bundle export | €30,000–€80,000/yr |

For v3.0 pilots we sell **Platform + Regulatory Pack** (since both pilot customers will be using the hosted UI and need the regulatory artefacts). Priced as a flat €25k–€75k 90-day pilot fee with a conversion-to-production clause that activates the standard tier rates from month 4. This collapses my D-6 (a) into the headless spec's tiering.

The Regulatory Pack is **contractually required** for any production regulatory-submission use — every pilot agreement enforces this. Customers cannot use the headless API for an EMA SmPC submission without the Regulatory Pack scope on their key.

---

## G. New tickets added to v3.0 (full delta)

Total story points added: **26 (E11) + 4 (Track 1 + Track 5 + SOC 2 prep) = 30 SP**

That brings v3.0 from 259 SP to **289 SP**. To stay within the 12-week / 10-engineer envelope, the Pilot/GTM pod takes a load shift: TMX-4004 (EU AI Act technical-doc skeleton) and TMX-4005 (model cards) move 1 sprint earlier (start Sprint 4 instead of Sprint 5-6) — they were padding sprints anyway and a 2-week shift gives Reg + PM enough room to also produce the Regulatory Pack contract artefacts (TMX-4008) and the customer-facing trust centre prep (TMX-4013, new).

| ID | Title | Pod | Size | Sprint | Notes |
|---|---|---|---|---|---|
| TMX-3220 | Internal Service API extraction | Platform | L | 2 | E11 |
| TMX-3221 | Canonical job lifecycle state machine | Agent + Audit | M | 2 | E11 |
| TMX-3222 | Idempotency middleware | Platform | M | 2 | E11 |
| TMX-3223 | RBAC middleware between adapter and Internal Service API | Auth | M | 2 | E11 |
| TMX-3224 | OpenAPI 3.1 source-of-truth | Platform | M | 3 | E11 |
| TMX-3225 | REST API v2 — core endpoints | Platform | L | 3 | E11 |
| TMX-3226 | Webhooks v1 (Ed25519, retry, DLQ) | Platform | M | 4 | E11 |
| TMX-3227 | Python SDK 1.0.0 on PyPI | Platform | L | 3-4 | E11 |
| TMX-3228 | MCP server hardening + schema parity | Agent | M | 4 | E11 |
| TMX-3229 | S3 connector v1 | Platform | M | 5 | E11 |
| TMX-3230 | SFTP connector v1 | Platform | M | 5 | E11 |
| TMX-3231 | Customer webhook receiver | Platform | S | 5 | E11 |
| TMX-3232 | Surface-parity test harness | QA + Platform | L | 4-5 | E11 / Track 2 |
| TMX-3508 | Spectral + Schemathesis + Pact in CI (Track 1) | Platform | M | 3 | extends E3 |
| TMX-3509 | Performance budget gates (Track 5) | Platform | S | 5 | extends E9 |
| TMX-4012 | SOC 2 / ISO 27001 evidence scaffolding (Drata or equivalent) | Pilot + SecEng | M | 5-6 | Track 8 prep |
| TMX-4013 | Trust-centre staging — release bundle download endpoint | Pilot + Platform | M | 6 | Internal-only in v3.0; public in v3.1 |

Updated epic table:

| ID | Epic | Owner pod | Sprints | Story points |
|---|---|---|---|---|
| E1 | Security baseline & multi-tenancy | Auth & Tenancy | 0-2 | 21 |
| E2 | Audit ledger v2 + e-signature | Audit & Validation | 1-4 | 34 |
| E3 | Validation pack as code (Track 6 + 9) | Audit & Validation | 3-6 | 21 |
| E4 | Document ingestion fidelity | Document Pipeline | 1-4 | 26 |
| E5 | PII v2 + segmentation v2 | Document Pipeline | 1-4 | 21 |
| E6 | Quality gate hardening + EMA QRD + term lock | Quality & Regulatory | 2-5 | 26 |
| E7 | Agent fabric + prompt registry + cost gov + router | Agent & AI | 1-5 | 29 |
| E8 | Frontend IA + reviewer cockpit + design system | Reviewer Frontend | 0-6 | 42 |
| E9 | Observability, tracing, evals (Track 5 + 9) | Platform & Observability | 1-5 | 22 |
| E10 | Pilot readiness pack | Pilot/GTM | 2-6 | 25 |
| **E11** | **Headless Foundation (REST + SDK + MCP + Webhooks + S3/SFTP)** | **Platform + Agent** | **2-6** | **26** |
| **Total** | | | | **293** |

---

## H. Updated Definition of Done for v3.0 (release-level)

Replace Part I §1 "Definition of Done" with the merged criteria below. New / changed in **bold**.

| # | Exit criterion | Verified by |
|---|---|---|
| 1 | All 13 Critical findings (C-01 .. C-13) and 5 frontend Critical findings (F-C01 .. F-C05) closed | Review doc Appendix A walked, signed by Tech Lead |
| 2 | **Vendor security questionnaire CAIQ-Lite drafted; SAST + DAST + SBOM + dependency scan in CI** | External CISO advisor signs |
| 3 | DPA, BAA, sub-processor list, **Regulatory Pack contract template** published under `compliance/` | Pharma counsel approves |
| 4 | **Per-release Validation Bundle** (vsr.pdf + openapi.yaml + mcp-tools.json + sbom + slsa-attestation + surface-parity.json + golden-corpus.json + slo-report.json + security-summary.pdf + compliance-pack/) renders for v3.0 release tag | CI job `validation-bundle` green |
| 5 | Audit ledger v2 verifies a 100k-event chain in ≤ 60s with cryptographic guarantee | New test suite green |
| 6 | Frontend build green; **Vitest + Playwright + Schemathesis + Pact + Spectral** gate every PR | GitHub Actions |
| 7 | EMA QRD validators pass for golden SmPC sample en→es, en→fr, en→de | Track 6 deliverable |
| 8 | Reviewer cockpit on `/workspace/review/[jobId]` passes WCAG 2.1 AA | Track 4 / a11y audit |
| 9 | At least 2 paid pilots signed (LOI + master agreement + Regulatory Pack rider) | Sales record |
| 10 | EU AI Act technical-documentation skeleton + per-language-pair model cards published internally | Reg Affairs Lead sign-off |
| **11** | **REST API v2 published; Python SDK 1.0.0 on PyPI; MCP server hardened; Webhooks v1 live; S3/SFTP connectors v1 live** | E11 ACs |
| **12** | **Surface Parity Matrix shows ≥ 12/12 top journeys passing across REST + Python SDK + MCP + UI server actions** | Track 2 deliverable |
| **13** | **Internal Service API extracted; surfaces are pure adapters with no business logic** | Architecture review |
| **14** | **Canonical job lifecycle state machine in production; old `Document.status` mappings retired or aliased** | Refactor PR signed |

If any of 1-14 is red the release does not ship.

---

## I. Updated KPIs (release-level)

Add to Part I §8:

| KPI | Sprint 0 | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 | Sprint 5 | Sprint 6 |
|---|---|---|---|---|---|---|---|
| **Surfaces live** (UI / REST / SDK / MCP / Webhooks / S3 / SFTP) | UI | UI | UI | UI + REST | UI + REST + SDK + MCP | + Webhooks + S3 + SFTP | **all 7** |
| **Surface Parity score** (top 12 journeys) | n/a | n/a | n/a | 3 / 12 | 8 / 12 | 11 / 12 | **12 / 12** |
| **Contract conformance** (Schemathesis pass on `/v2/*`) | n/a | n/a | n/a | partial | full | full | **full** |
| **Per-release Validation Bundle generated** | no | no | no | partial | partial | yes | **yes** |
| **PyPI Python SDK download (smoke)** | no | no | no | no | yes | yes | **yes** |

---

## J. New decisions for CEO (additions to Part I §9)

The headless spec §13 adds eight open questions. Five matter for v3.0:

### D-9 — CLI binary distribution language
**Question**: When CLI lands in v3.1, Rust, Go, or Python (PyOxidizer)?
- (a) **Rust**: smallest, fastest startup, single static binary, harder to hire.
- (b) **Go**: easy single binary, broad pharma DevOps familiarity.
- (c) **Python (PyOxidizer)**: same language as engine, biggest binary, slowest startup.

**Recommendation**: Rust for portability + supply-chain story (cargo-vet, cargo-audit). v3.0 doesn't ship the CLI, but starting the Rust scaffolding in Sprint 6 hedges v3.1 start.

**Blocks**: v3.1 only.

### D-10 — Hosted review domain
**Question**: When review-handoff URL lands in v3.1, same origin as workspace UI (`app.transmax.io/review/...`) or separated (`review.transmax.io`)?
- (a) **Same origin**: simpler auth; iframe embedding may be blocked by customer CSP.
- (b) **Separated**: cleaner customer-portal embedding; requires SAML/OIDC federation infra.

**Recommendation**: separated `review.transmax.io` from day one — customer portal embedding is the killer GTM feature; pay the federation infra cost early.

**Blocks**: v3.1 only.

### D-11 — Customer-managed keys (CMK) breadth
**Question**: AWS KMS only, or BYOK across AWS / Azure / GCP from day one?
- (a) **AWS KMS only**: matches our hosting; pharma customers on Azure complain.
- (b) **Multi-cloud BYOK**: triples KMS integration work; but matches "we sell into pharma" reality.

**Recommendation**: AWS KMS only for v3.1 (extends to Azure Key Vault in v3.2). v3.0 does not offer CMK.

**Blocks**: v3.2.

### D-12 — On-premise / air-gapped deployments
**Question**: Top-tier pharma sometimes requires fully air-gapped deployments. Do we support, ever?
- (a) **Yes, as v3.x premium SKU**: doubles release engineering work; opens top-3 pharma deals.
- (b) **No, multi-tenant SaaS only**: simpler; loses some top-3 deals.
- (c) **Hybrid: dedicated single-tenant cloud, not air-gapped**: middle ground; matches Smartcat / Lilt strategy.

**Recommendation**: (c) for the foreseeable future. Air-gapped is too expensive a SKU until €20M+ ARR.

**Blocks**: v3.2-3.3 sales motion.

### D-13 — Public bug-bounty scope
**Question**: When (and how broad) is the bug bounty?
- (a) **Phase 2 launch on REST + MCP only**: low risk, fast.
- (b) **Phase 3 broad scope including connectors and SDK**: bigger reward pool.
- (c) **Never**: rely on internal pen-test only.

**Recommendation**: Phase 2 launch on REST + MCP via HackerOne; broaden in Phase 3.

**Blocks**: v3.1 / v3.2 GTM.

---

## K. Risk register additions (extends Part I §10)

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Surface drift over time (one surface evolves faster than others) | High | High | Single OpenAPI source-of-truth (TMX-3224); generated SDKs (TMX-3227); surface-parity gate (TMX-3232); Track 2 weekly | Platform pod |
| AWS QLDB referenced in headless spec §7.5 but is end-of-life — risk we silently keep using a deprecated service | Low | High | Editorial pass on headless spec to replace QLDB with S3 Object Lock + OpenTimestamps; tracked under TMX-3107 | Audit pod |
| Customers use headless API without Regulatory Pack and self-attest compliance | Medium | Medium | Contract enforcement; usage telemetry; gate the signed evidence bundle export behind Regulatory Pack scope (TMX-3225 AC) | Pilot/GTM pod |
| Long-running jobs leak through synchronous endpoints | Medium | Medium | Hard cap on synchronous endpoint scope (single segment ≤ 200 tokens); 202-only for full-document submit | Platform pod |
| MCP transport vulnerabilities (young protocol) | Medium | Medium | Bearer-token MCP extension; close monitoring of MCP CVE feed; network-isolated runtime | Agent pod |
| Validation overhead slows v3.0 ship | High | Medium | Automate Tracks 1-5 entirely in CI; treat Tracks 6-8 as quarterly cadence with auto-collected evidence; budget 20% of engineering capacity for validation infrastructure | Platform pod |
| EU AI Act notified-body capacity in 2026-2027 | High | High | Engage a Big-Four advisor or notified body in Sprint 1; pre-book conformity assessments; build evidence pipeline before policy bites | Reg pod |
| Internal Service API extraction takes longer than Sprint 2 | Medium | High | Architectural spike in Sprint 1 to size the refactor; if blocking Sprint 3, the CEO must approve descoping E11 (REST API v2 slips to v3.1) | Platform pod |

---

## L. What I'd tell engineering on day one (executive summary)

If you have 5 minutes for the team kickoff, this is the briefing:

> "We're shipping v3.0 in 12 weeks. The customer is a top-20 pharma's regulatory affairs lead who has to put TransMax through a vendor security questionnaire and a CSV review **and not laugh**. We are not building features; we are banking **defensible artefacts**. Every PR carries a ticket ID, an AC checklist, and a validation-pack delta. Every release ships a signed bundle with a VSR, an OpenAPI, an SBOM, an SLSA attestation, a surface-parity matrix, a golden-corpus run, an SLO report, a security summary, and a compliance pack.
>
> The architecture has one new principle: **one engine, many surfaces**. There is *one* Internal Service API. The UI, the REST API, the MCP server, the SDK, and the connectors are thin adapters. If you find yourself adding business logic in an adapter, stop and refactor.
>
> The principles are non-negotiable: contract-first, async-first, audit-by-default, tenant-isolated, idempotent, explainable, reviewer-optional, compliance-shipped. If a PR violates them, it's rejected.
>
> We are explicitly **not** doing TS SDK, CLI, Veeva connector, eCTD connector, multi-region, BYOK, public verify page, agent-to-agent registrations, ISPOR linguistic validation, or open-sourcing the audit kit. Those are v3.1+. If you find yourself working on those, stop.
>
> Two pilots, signed by sprint 6. That is the release."

---

*End of Part II addendum. Part I + Part II form the v3.0 release plan as of 2026-05-01.*

---

# Part III — Capabilities Spec + Descope Integration & Counter-Descope

**Added**: 2026-05-01 (later same day, after reading `TRANSMAX_PLATFORM_CAPABILITIES_SPEC.md` v0.9 and `TRANSMAX_DESCOPE_NOTE.md`).
**Reads alongside**: those two docs plus Parts I and II above.

## A. What this addendum is

`TRANSMAX_PLATFORM_CAPABILITIES_SPEC.md` is the **most ambitious** of the four design documents. It articulates four pillars: (1) layered rules + knowledge graph, (2) determinism library + 4-tier resolution cascade, (3) eight-signal calibrated confidence + check-and-recheck, (4) format fidelity covering XLIFF + DOCX + RTF/TLF + formulas + figures.

`TRANSMAX_DESCOPE_NOTE.md` is **Kapil's own corrective** to that spec (and the headless spec, and the May 2026 review): it cuts 13 ambitious items, elevates 5 underweighted ones, and recommends **managed-service-first + embedded-first** for 12 months, then dual-track from month 13.

The descope note already moves us from "competitively complete" toward "actually shippable in 90 days." This Part III does two things:

1. **Adopts** the descope note's cuts/elevations/strategic recommendations into the v3.0 plan, with concrete epic / ticket deltas.
2. **Counters with further descope** — what I'd cut on top, framed as: *what's the absolute minimum a focused regulated-translation agent needs to win 2 paid pilots in 90 days?*

Then I log everything deferred under `parking_lot/deferred_features.md` so nothing is lost. The parking-lot registry is the canonical revisit-later list.

---

## B. Adopting the descope note (no resistance)

The 13 cuts and 5 elevations are right; I adopt them in full.

### B.1 The 13 cuts — adopted into v3.0 (and into the parking lot)

| # | Item | v3.0 disposition |
|---|---|---|
| 1 | Six-layer rule taxonomy (L0–L5) | **Cut to 2 layers** (regulator + tenant). My counter (§C) cuts further to "1 + 1": one regulator pack + one tenant glossary file per customer. |
| 2 | MedDRA / MeSH / ATC / IDMP knowledge graph | **Phase 3** as note says |
| 3 | Eight confidence signals | **Phase 1: 3 signals** (TM-match, glossary-adherence, severity-weighted defect rate). My counter (§C) goes further: skip the *composite score* in v3.0; ship raw defect-tier routing only. |
| 4 | Per-slice MLflow-versioned calibration models | **Phase 2** |
| 5 | Per-reviewer calibration | **Drop entirely** |
| 6 | TypeScript SDK + CLI | **Phase 3** |
| 7 | MCP server hardening | **Phase 2** (the prototype stays; we don't productise) |
| 8 | eCTD v4.0 native publisher | **Reposition as integration only** with LORENZ/Extedo/EXT-DM |
| 9 | LaTeX support for SAPs/protocols | **Drop** |
| 10 | Cross-tenant anonymised boilerplate | **Drop** |
| 11 | Figures pipeline (SVG-text walking + label re-render) | **Drop / partner** |
| 12 | Eleven TLF cell types | **5 cell types** (header/label/numeric/statistical/footnote). My counter (§C) goes further: TLFs out of v3.0 entirely. |
| 13 | Annual notified-body assessment per release | **Once for the platform**; per-release internal-only |

### B.2 The 5 elevations — adopted

| # | Elevated to | Reflected in v3.0 as |
|---|---|---|
| 1 | Glossary + TM management UX → Phase 1 deliverable | New backlog: **TBX/TMX bulk import**, term-conflict resolution, term lifecycle, term-impact telemetry. Slots into E6 (was: Quality gate + QRD + term-lock primitive) and into E8 (Reviewer cockpit). |
| 2 | Reviewer ergonomics → Phase 1 deliverable | E8 already has keyboard cockpit (j/k/a/r/e/f/⌘↩/?), virtualised list, severity colour scale; reinforced. |
| 3 | Customer onboarding → explicit programme | **New epic E13** (Customer Onboarding Playbook). Templates, demo data, sandbox tenant per pilot, "one-week onboarding" runbook. |
| 4 | TBX/TMX import on day one | Folded into E6 + E11 (now further descoped per §C). |
| 5 | Pricing simplicity → 2 tiers + Regulatory Pack | **D-6 closed differently** than Part II said. Pricing model becomes: **Pilot tier** (€25-75k flat 90-day) + **Enterprise tier** (per-engagement pricing under managed-service model) + **Regulatory Pack** add-on. |

### B.3 The 2 strategic decisions — adopted with rationale

**Managed-service-first** (12 months), then dual-track from month 13. Adopted. Knock-on effects on v3.0:

- E10 (Pilot readiness pack) becomes a **ZS-mediated sales motion** rather than self-service marketing. Self-service onboarding, billing, public marketing site, public docs, free-tier SDK distribution all defer.
- E11 (Headless Foundation) **further descopes** under the embedded-first thesis (§C): REST API v2 + Python SDK move to v3.1; the UI is the demo for v3.0 pilots.
- Investment envelope drops to €0.4M-€0.6M for v3.0 (was €0.6M-€0.9M).
- Headcount drops to 8 engineers + 1 PM + 2 QA + 1 RA + 1 Design + 0.5 SecEng + 1 Solution Architect (managed-service path) + 1 consultant-enablement = 14.5 FTE (descope note says 15.5, but I'd cut deeper — see §C).

**Embedded-first**. Adopted. Knock-on effects:

- The UI in v3.0 is **a credible reviewer surface, not a beautiful product.** Investment is consistency and reliability, not novel UX.
- E8 (Frontend) drops from 42 SP → 28 SP. Drop i18n / RTL / mobile in v3.0. en-only UI for the pilot.
- Headless surfaces (REST API v2, Python SDK) become Phase 1.5 / v3.1 deliverables — not v3.0.
- Format-fidelity work (E4) is the differentiator, not UX. v3.0 invests there.

### B.4 Phase 1 honest scope (descope note §5) — mostly adopted

The descope note's 23 Phase 1 items are mostly the right floor. I keep all of §5.1 (security/hygiene non-negotiables — auth on, audit ledger v2, soft-delete, mega-migration unwind, mock-fallback strip) and §5.5 (validation + onboarding). I push back on parts of §5.2 (format) and §5.4 (surfaces). See §C.

---

## C. Counter-descope — what I'd cut further

The descope note already cuts ~30% of scope. I'd cut another ~20% on top to reach a **truly focused regulated-translation agent**. The pitch is brutal: *every feature not directly inside the demo-to-signed-pilot path defers to v3.1 or later.*

### C.1 What I'd descope further

#### CD-1. REST API v2 + Python SDK 1.0 → v3.1

**Descope note has them in Phase 1 (§5.4 #17, #18).** I'd push them out by one release.

- **Why**: pilots use the UI. Two named pharma customers in 90 days do not need a public REST API or a `pip install transmax-sdk`; they need a working translation flow they can put a real SmPC through. Headless surfaces are a v3.1 sales-driven feature, sold to *partners* and *CROs*, not to the first-pilot pharma RA leads.
- **Consequence**: drop E11 from v3.0 entirely. Save 26 SP. The Internal Service API extraction (TMX-3220) **stays** in v3.0 because it's a refactor that future surfaces depend on, but the surfaces themselves wait.
- **Risk**: looks like a feature gap when an embedded-first pilot customer says "give us the API." Mitigation: Sprint 5 spike to pilot-validate that the customer is genuinely OK with UI-only for the 90-day pilot.

#### CD-2. Composite confidence score → defer; ship raw defect-tier routing only

**Descope note already cut 8 signals → 3 + global isotonic regression (§5.3 #16).** I'd defer the composite scoring entirely.

- **Why**: a calibrated probability that a reviewer will accept the segment is sophisticated. For 2 pilots, the disposition logic can be: critical defect = BLOCKED; major defect = REVIEW_REQUIRED; no critical/major = PASS (still shown to reviewer per regulatory floor). That's the PRD §FR7 logic the codebase already has. Calibrated confidence is Phase 2.
- **Consequence**: in E6, drop the "isotonic regression + tiered review thresholds + reviewer-agreement signal" work. Keep critical-defect overrides (already in `quality_gate.py`). Save ~6 SP from E6.
- **Risk**: less sophisticated story for the customer. Mitigation: the *cost story* (Determinism KPI in §C.2) is the more compelling commercial narrative anyway.

#### CD-3. Determinism Library limited to EDQM Standard Terms + EMA QRD section titles, top 3 language pairs only

**Descope note says "EDQM Standard Terms only for top six language pairs" (§5.3 #14).** I'd cut the language pairs from 6 → 3 and add EMA QRD section titles only because they are part of the QRD compliance demo.

- **Why**: EN→ES + EN→DE + EN→FR cover the EU pilot universe. EN→IT, EN→PT, EN→JA wait for v3.1 / pilot 3+. Pharma EU regulatory submissions go in 24 EU languages, but pilots target a subset.
- **Consequence**: TMX-3404 (term-lock primitive) ships only for ES/DE/FR. Save ~3 SP. The lookup primitive is identical; only the seeded data shrinks.
- **Risk**: Italian/Portuguese pilot opportunity blocked. Mitigation: explicit "we add IT/PT in 4 weeks if a pilot needs them" expansion clause.

#### CD-4. PDF (digital) ingestion in v3.0; PDF (scanned/OCR) deferred to v3.1

**Descope note has PDF (digital only) in Phase 1 (§5.2 #9), OCR in Phase 2.** I'd keep this exactly.

- This is correct as-is in the descope note. No further descope; just confirming.

#### CD-5. PPTX, HTML/XML, IDML, RTF, MathML/OOML, LaTeX → v3.1+

**Descope note keeps PPTX/HTML in Phase 1 (§5.2 #8 implicitly), defers RTF/MathML/IDML to Phase 2.** I'd push PPTX and HTML out of v3.0 too.

- **Why**: SmPC and PIL are DOCX or PDF. CSR appendices are RTF (Phase 2 territory). PPTX and HTML are not pilot-blocking. Cutting them lets E4 ship cleanly with just **DOCX (with tracked changes)** + **PDF (digital)** + **XLIFF 2.1** + **TMX**. That's 4 formats, not 9.
- **Consequence**: E4 drops from 26 SP → 16 SP. The descope-note floor is met (DOCX + XLIFF + PDF + TMX, plus PDF/A-1b export); we just don't add PPTX or HTML on top.
- **Risk**: customer ships an XLSX or PPTX. Mitigation: customer-onboarding playbook (E13) includes a "supported formats today" line; out-of-scope formats route to a manual-DTP partner.

#### CD-6. Audit ledger v2 SLSA + cosign signing → v3.1

**Headless spec / capabilities spec / Part II all want signed releases (cosign + SLSA L3).** I'd defer to v3.1.

- **Why**: pilot customers do not check our SLSA L3 attestation. Audit-chain v2 (domain-separated hashing + S3 Object Lock daily anchor + verify API) is the load-bearing piece — that survives Part 11 review. SLSA + cosign is supply-chain hygiene that matters for v3.1 SOC 2 evidence collection, not v3.0 pilots.
- **Consequence**: E2 (audit ledger) drops 6 SP. TMX-3505 (cosign-signed manifest + SBOM) defers; SBOM still generates as artefact, just without cosign signing.
- **Risk**: SOC 2 Type II auditor wants supply-chain attestation. Mitigation: that audit is Phase 2; we have time.

#### CD-7. Spectral + Schemathesis + Pact contract validation → v3.1

**Headless-spec Track 1 / Part II TMX-3508.** I'd defer.

- **Why**: contract validation matters once we have multiple surfaces (REST + SDK + MCP) drifting from each other. With CD-1 deferring REST + SDK to v3.1, the only "surface" in v3.0 is the UI calling FastAPI directly. FastAPI's auto-generated OpenAPI is enough; Spectral lint can wait.
- **Consequence**: drop TMX-3508; defer Track 1 to v3.1 alongside the surfaces it validates. Save 4 SP.
- **Risk**: the OpenAPI we build implicitly in v3.0 is messy when we formalise it in v3.1. Mitigation: design REST routes with conventions (RFC 9457 problem details, cursor pagination) so the v3.1 retrofit is mechanical.

#### CD-8. EU AI Act FDA AI/ML credibility framework artefacts → v3.1

**Part II E10.6, descope note keeps it as Phase 1.** I'd defer the *executed evidence* and ship only the *plan*.

- **Why**: EU AI Act enforcement is 2026-08-02. Our v3.0 ships 2026-07-24 — comfortably before. Per the descope note's own cut #13, the right discipline is "once for the platform; per-release internal evidence only." FDA framework executed evidence is for v3.1 once we have customers.
- **Consequence**: TMX-4006 (FDA credibility framework executed evidence) defers; replaced by TMX-4006a (FDA credibility framework *plan*, document-only) in v3.0.
- **Risk**: a US pilot customer asks for FDA evidence. Mitigation: D-1 pilot profile (EU-focused) makes this unlikely.

#### CD-9. Frontend i18n (next-intl, RTL) → v3.1

**Part II E8.10 / TMX-3610-3611.** I'd defer.

- **Why**: the UI is in English. Reviewers reading EN→ES translations are bilingual; they don't need a Spanish UI. AR/JA review surfaces wait until pilot 3+. Marketing surfaces are EN-only anyway.
- **Consequence**: E8 drops from 42 SP → 28 SP (the 14 SP bundle: i18n wiring, RTL CSS, locale switching, translated reviewer cockpit strings). The i18n is *architected* for in v3.1 (use `next-intl` keys, not literals) so it's a refactor not a rewrite.
- **Risk**: a pilot customer requires a German UI. Mitigation: D-1 pilot profile + customer-onboarding playbook addresses this in customer comms.

#### CD-10. TLF / RTF / formulas / figures → v3.1+ entirely

**Capabilities spec Pillar 4 §6.6-6.7 — descope note moves TLF/RTF/MathML to Phase 2.** I'd keep that and not invest in any TLF infrastructure in v3.0.

- This matches the descope note. No further descope here.

#### CD-11. Knowledge graph stub → drop entirely from v3.0

**Capabilities spec Pillar 1 §3.4 — descope note moves to Phase 3.** I'd not even ship the *thin tenant-scoped entity table*.

- **Why**: even a stub adds schema complexity without pilot value. Glossary + EDQM standard terms is enough vocabulary for pilots.
- **Consequence**: no schema work; no entity tables in v3.0.

#### CD-12. Multi-region deployment, BYOK, customer-managed keys → v3.1+

**Headless spec §7.2 — descope note keeps this Phase 1 EU-only.** Confirming: single EU-Central region, vendor-managed keys via AWS KMS service-managed.

- This matches the descope note (D-5 closes single-region EU). No further change.

#### CD-13. Glossary management *full* UX → minimum viable in v3.0

**Descope note elevates glossary UX (§3 #1).** I agree it's load-bearing, but I'd ship the *minimum viable* for v3.0:

- **In v3.0**: TBX import; CSV import; per-tenant glossary list; CRUD on terms; activate/deactivate per glossary; download as CSV.
- **In v3.1**: term conflict resolver; term lifecycle (draft → reviewed → approved → active → deprecated); term-impact telemetry; bulk-edit; comment threads on terms.
- **Why**: customers come WITH their existing glossary as TBX or CSV. Importing it is non-negotiable for pilot. Conflict resolution and lifecycle are Phase 2 once they have *enough* terms to conflict.
- **Consequence**: 8 SP saved (move out of E6 into E13.x v3.1).

### C.2 What I'd elevate further (on top of the descope note's 5)

#### CE-1. Determinism KPI as a customer-facing dashboard from day one

The cost story for a focused translation agent is:

> "We translated **62%** of your segments without an LLM call this month. That saved you **€18,400** vs. an LSP per-word price."

This is the conversation that wins the pilot vs. an LSP. The Determinism KPI must be visible to the customer in the pilot dashboard, with a per-month rollup. **Promote to a Sprint 4 deliverable.**

This is implicit in the capabilities spec §4.7 ("Determinism KPI is a customer-facing metric") and the descope note §6.3 mentions it; my elevation makes it a hard exit criterion.

#### CE-2. Speed-to-first-translation as a pilot demo metric

Track 5 (Performance & SLO) of the headless spec budgets P95 translate-and-review at ≤ 5 min for 1k words × 5 langs. The descope note relaxes this to ≤ 15 min Phase 1.

I'd add a separate, narrower KPI: **time from upload to first defect surfaced** for a 1-page SmPC fragment. Target: **≤ 30 seconds** for the pilot demo. This is the Shazam moment. Add to E9 KPI dashboard.

#### CE-3. One-week onboarding runbook as a pilot deliverable

The descope note elevates customer onboarding (§3 #3). I'd make it a hard v3.0 exit criterion: a documented one-week onboarding playbook tested end-to-end on the first pilot, with templates for:
- DPA + BAA + Regulatory Pack scope agreement
- Sandbox tenant provisioning checklist
- Glossary + TM intake template
- First-translation walkthrough (script + screenshots)
- Reviewer sign-off training (2-hour video)
- Validation pack handoff

This becomes E13 (new epic, 8 SP).

#### CE-4. Cost dashboard with per-tenant token + Determinism telemetry

Per the headless spec §7.4 + capabilities spec §4.6 (token-cost governance). I'd elevate this to a Sprint 4 ship and make it customer-visible (not just internal). Combines with CE-1.

This is part of E9 already (TMX-3903 cost dashboard with ceiling alerts) but should be customer-facing not internal-only in v3.0.

### C.3 Updated v3.0 epic table after counter-descope

| ID | Epic | Was (Part II) | Now (Part III) | Δ |
|---|---|---|---|---|
| E1 | Security baseline & multi-tenancy | 21 | 21 | 0 |
| E2 | Audit ledger v2 + e-signature | 34 | **28** | -6 (drop SLSA/cosign) |
| E3 | Validation pack as code (Track 6 + 9) | 21 | **17** | -4 (drop Track 1 contract validation) |
| E4 | Document ingestion fidelity | 26 | **16** | -10 (DOCX + PDF + XLIFF + TMX only) |
| E5 | PII v2 + segmentation v2 | 21 | 21 | 0 |
| E6 | Quality gate hardening + EMA QRD + 2-layer term lock + critical-defect overrides | 26 | **18** | -8 (no calibration; 2 layers not 3; 3 langs not 6) |
| E7 | Agent fabric + prompt registry + cost gov + agent router | 29 | **22** | -7 (default routing only; defer multi-tenant routing config) |
| E8 | Frontend IA + reviewer cockpit + design system v1 | 42 | **28** | -14 (drop i18n/RTL/mobile/exec sign-off) |
| E9 | Observability, tracing, evals + customer-facing cost dashboard | 22 | **22** | 0 (CE-4 customer-facing dashboard absorbed in scope) |
| E10 | Pilot readiness pack (CAIQ + DPA + BAA + EU AI Act *skeleton*) | 25 | **18** | -7 (FDA credibility executed evidence → v3.1) |
| ~E11~ | ~Headless Foundation (REST + SDK + MCP + Webhooks + S3/SFTP)~ | 26 | **0** | **-26** (DEFERRED to v3.1; only Internal Service API extraction TMX-3220 stays in E7) |
| **E12 NEW** | Determinism Library + Tier 1/2 cascade + customer-facing Determinism KPI | 0 | **16** | +16 (the cost story) |
| **E13 NEW** | Customer onboarding playbook + sales kit | 0 | **8** | +8 (CE-3) |
| **Total** | | **293** | **234** | **-59 (-20%)** |

Combined with the descope note's earlier 30% cut from the original ambition, v3.0 is now **~50% smaller** than the original PM ambition. This is achievable with **8 engineers** (vs. 10 originally; matches descope note's 15.5 → my 14.5 FTE).

### C.4 Updated v3.0 release-DoD criteria (replaces Part II §H)

| # | Exit criterion | Verified by |
|---|---|---|
| 1 | All 13 Critical findings + 5 frontend Critical findings closed | Review walked, signed by Tech Lead |
| 2 | Vendor security questionnaire CAIQ-Lite drafted; SAST + dependency scan in CI | External CISO advisor |
| 3 | DPA, BAA, sub-processor list, **Regulatory Pack contract template** published | Pharma counsel |
| 4 | Per-release Validation Bundle renders for v3.0 release tag | CI job `validation-bundle` green |
| 5 | Audit ledger v2 verifies a 100k-event chain in ≤ 60s | Test suite |
| 6 | Frontend build green; Vitest + Playwright (smoke only) gate every PR | GitHub Actions |
| 7 | EMA QRD validators pass for golden SmPC sample en→es, en→fr, en→de | Track 6 |
| 8 | Reviewer cockpit on `/workspace/review/[jobId]` passes WCAG 2.1 AA (en-only UI) | A11y audit |
| 9 | At least 2 paid pilots signed (LOI + master agreement + Regulatory Pack rider) | Sales record |
| 10 | EU AI Act technical-documentation skeleton + per-language-pair model cards published internally | Reg Affairs Lead |
| **11** | ~~REST API v2 / Python SDK / MCP / Webhooks / S3-SFTP live~~ → **DEFERRED to v3.1** | n/a |
| **12** | ~~Surface Parity Matrix 12/12~~ → **DEFERRED to v3.1** | n/a |
| 13 | Internal Service API extracted; UI is a pure adapter with no business logic | Architecture review |
| 14 | Canonical job lifecycle state machine in production | Refactor PR signed |
| **15** | **Determinism KPI customer-facing on the pilot dashboard** | E12 deliverable |
| **16** | **Time-from-upload to first-defect-surfaced ≤ 30s** for 1-page SmPC fragment | Demo video + Track 5 |
| **17** | **One-week onboarding runbook tested end-to-end on first pilot** | E13 deliverable |
| **18** | **TBX/CSV glossary import live + per-tenant glossary list** (no conflict resolver yet) | E6 deliverable |

## D. Strategic decision recommendations (the 8 owed by steering)

The descope note §8 lists 8 decisions owed before v3.0 commits. My recommendations:

| # | Decision | Recommendation | Why |
|---|---|---|---|
| 1 | Productised SaaS vs managed-service vs hybrid | **Managed-service-first 12 months, dual-track from month 13** | Faster revenue, lower capital risk, fits ZS shape, EU AI Act/FDA AI windows still settling |
| 2 | UI-first vs embedded-first | **Embedded-first 12 months** | Avoids head-on TMS feature war; UI is the demo + hosted-review-handoff target |
| 3 | Region scope | **Single EU region (Frankfurt)** for v3.0; US in Phase 2; APAC Phase 3 | Matches D-1 EU pilot focus |
| 4 | Pilot customer profile | **Top-20 pharma named accounts via ZS account leadership** | Plus one CRO as the 3rd-pilot hedge |
| 5 | Open-source posture for L0 rule pack | **Keep proprietary in v3.0**; reconsider once 3 customers signed | Don't give away the moat before PMF |
| 6 | Confidence calibration disclosure to reviewers | **Tier label only** ("light review" / "full review" / "dual review") — never raw probability | Per descope note: numbers are anxiety-provoking |
| 7 | Engineering team locality | **Single hub (Pune or London)** for v3.0; avoid follow-the-sun until Phase 2 | Coherence > coverage at this scale |
| 8 | First Regulatory Pack content | **EDQM Standard Terms + EMA QRD** only | FDA SPL / MHRA / others Phase 2 |

These are all aligned with the descope note's recommendations.

## E. The parking lot — every deferred feature, logged

To honour the "don't lose anything" requirement: every deferred feature from every doc lives in `parking_lot/deferred_features.md`. That file is the canonical revisit-later registry. When v3.0 ships and we plan v3.1, the parking lot is the input bucket.

See `parking_lot/deferred_features.md` for the full registry. Summary:

- **Deferred to v3.1** (reactivate post-pilot if customers ask): REST API v2, Python SDK 1.0, MCP server hardening, Webhooks v1, S3/SFTP connectors, surface parity testing, Spectral/Schemathesis/Pact, frontend i18n + RTL, mobile reviewer surface, FDA credibility framework executed evidence, calibrated confidence model, glossary conflict resolver + lifecycle, SLSA/cosign signed releases, OCR fallback, locale-aware date/decimal handling
- **Deferred to v3.2 / Phase 2**: TypeScript SDK, CLI, MedDRA / MeSH / ATC / IDMP knowledge graph, RTF / TLF / MathML / OOML, IDML, IT/PT/JA/AR Determinism Library expansion, eCTD publisher integration (LORENZ/Extedo/EXT-DM), Veeva Vault PromoMats / RIM / SharePoint / Documentum connectors, multi-region deployment, BYOK / customer-managed keys, ISO 27001 evidence collection, SOC 2 Type II evidence collection, ISO 17100 / 18587 process documentation, sandbox playground, public bug bounty
- **Deferred to v3.3 / Phase 3**: Agent-to-agent registrations (Anthropic Agent SDK, OpenAI Agents SDK, LangGraph Cloud, AutoGen), per-slice calibration models, per-reviewer fine-tuning, ML-assisted rule discovery, per-brand / per-study rule packs, regulator-pack marketplace, public verify.transmax.io page, customer trust centre, eCTD v4.0 native publisher, LaTeX support, IDML support, Figures pipeline, cross-tenant boilerplate library, ISPOR linguistic-validation graph
- **Permanently deferred / dropped**: Per-reviewer calibration (bias channel risk), LaTeX SAP/protocol translation (English-only), Cross-tenant boilerplate sharing (legally fraught), Annual notified-body assessment per release (overkill), 11 TLF cell types in classifier (5 covers it), Six-layer L0-L5 rule taxonomy (3-layer is enough; 2 in v3.0 → 3 in v3.1+), Eight-signal calibrated confidence (3 signals + critical-defect overrides is enough)

## F. What stays unconditionally non-negotiable

These cuts and counter-cuts do **not** touch the regulatory/safety floor. Per descope note §7, the system still must:

- Run a hash-chained audit ledger with cryptographic integrity, anchored daily
- Capture an immutable JobConfigSnapshot per job with rule-set hash, glossary hash and prompt version
- Enforce hard locks (numbers, units, drug names, EDQM terms) with Critical-defect blocking
- Produce a Validation Summary Report per release
- Hold approved rules and Determinism Library entries to a signed-by-human standard with no auto-promotion
- Default deny on access; row-level tenant isolation; soft deletes; encrypted at rest
- Produce evidence bundles a regulator can read

These are what makes TransMax pharma-grade. None is being descoped.

## G. The pilot-day demo (the spec inside the spec)

The descope and counter-descope above are scaffolding. The forcing function for v3.0 is one demo:

> *A pharma RA lead drops an EN SmPC into the workspace. Within 30 seconds they see the ES translation with one critical defect highlighted (a deliberate negation flip on segment 4) and three glossary-driven term hits. They click the segment, see the source-target side-by-side with the negation evidence, accept the AI-suggested fix, hit ⌘↩, complete the 2FA challenge, and see a signed PDF manifest with the audit chain proof and the Determinism KPI showing 62% of segments resolved without an LLM call. End-to-end in under 4 minutes.*

If v3.0 cannot deliver that demo on a real pharma SmPC, nothing else matters. If v3.0 can, every deferred feature in §E becomes a sales-driven v3.1 conversation, not a release blocker.

---

*End of Part III. Parts I + II + III together form the v3.0 release plan as of 2026-05-01. The parking lot at `parking_lot/deferred_features.md` is the canonical deferred-feature registry.*

