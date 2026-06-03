# Transmax — Headless and Multi-Surface Agent Specification

**Status:** Internal design specification, draft v0.9
**Owner:** Product Management — Pharma Translation Agent
**Audience:** Engineering leads, regulatory affairs, security, validation/QA, GTM
**Date:** May 2026
**Companion document:** *Transmax — Code Review and Enterprise Upgrade Path* (Word doc, May 2026)

---

## 1. Purpose

This document specifies how transmax becomes a regulated-content translation engine that can be invoked from *any* surface — its own UI, partner UIs, customers' regulatory portals, eCTD publishers, MLR review tools, agent-to-agent runtimes — without giving up the audit-grade guarantees, the EMA QRD validators, the EDQM standard-term locks or the EU AI Act conformity package that make it pharma-grade.

It also specifies how we will *prove*, on every release, that the surfaces are behaviourally equivalent, cryptographically defensible and validated to a standard a top-20 pharma's CSV/QA team will accept without negotiation.

The spec is intended to be the contract between Engineering, Regulatory Affairs, Security and GTM. Anything not in here is out of scope for the headless and multi-surface programme.

---

## 2. Vision

> **Translation as regulated infrastructure.** Transmax is the engine that translates the regulated content the regulator will actually accept — provably, at machine speed — accessible from a UI, an API, an MCP tool, an SDK, a CLI, a webhook, or another agent. The same engine, the same audit ledger, the same evidence bundle, every time.

The product surfaces are plural. The product itself is one.

---

## 3. Design Principles

The principles below are non-negotiable. Any future feature must be readable against them; any deviation requires sign-off from the Programme Lead and the Regulatory Affairs Lead.

1. **One engine, many surfaces.** All surfaces (UI, REST, MCP, SDK, CLI, connectors) call the same orchestration core. There is no "lite" engine. Behaviour is identical across surfaces; only ergonomics differ.
2. **Contract-first.** Every surface is specified as an OpenAPI 3.1 document, an MCP tool schema, or a typed SDK interface, before code. Schemas are versioned and code is generated from them.
3. **Async-first.** Translation jobs are long-running and human-reviewed. All surfaces are designed for async submission with webhook or poll callbacks; synchronous responses are convenience over the same primitive.
4. **Audit-by-default.** Every call, every state change, every signature lands on the same hash-linked ledger with the same JobConfigSnapshot, regardless of surface.
5. **Tenant-isolated by construction.** Multi-tenancy is enforced at the data layer (row-level filters, customer-managed keys), not at the surface layer.
6. **Idempotent and retry-safe.** Every state-mutating call accepts an idempotency key; replays are no-ops.
7. **Explainable.** Every translation, every defect, every quality-gate verdict has a structured evidence object and a human-readable rationale. Black boxes are not allowed in regulated content.
8. **Reviewer optional, not absent.** Headless mode supports a *review-handoff URL* so customers can deep-link from their own portal into a hosted review surface; the UI is optional, never mandatory, but always available.
9. **Compliance is shipped, not configured.** EU AI Act conformity package, 21 CFR Part 11 attestation, GAMP 5 validation summary and EMA QRD validators are part of every release — they are not opt-in features.

---

## 4. Surface Inventory

| Surface | Form | Primary user | Status today | Phase |
| --- | --- | --- | --- | --- |
| Hosted Web UI | Next.js 16 (existing) | Reviewers, programme managers | Prototype | 1 (consolidate) |
| Public REST API v2 | OpenAPI 3.1, OAuth 2.1 | Customer engineering, partners, CROs | Stub (`app/api/v1/*`) | 1 |
| MCP Server | MCP 1.0 over stdio + HTTP-SSE | Other LLM agents, copilots | Prototype (`transmax_mcp/`) | 1 |
| Python SDK | PyPI package `transmax-sdk` | Customer Python integrators, data science | Prototype (`transmax_sdk/`) | 1 |
| TypeScript SDK | npm package `@transmax/sdk` | Front-end / Node integrations | Not started | 2 |
| CLI | `transmax` binary | DevOps, batch, CI/CD | Not started | 2 |
| Webhooks | Signed HTTPS callbacks | Customer event consumers | Not started | 1 |
| Review-Handoff URL | Signed deep-link to hosted review | Embedded customer portals | Not started | 2 |
| Connectors | Adapters (Veeva, SharePoint, S3, eCTD) | Regulatory operations teams | Not started | 2 |
| Agent-to-agent registrations | LangGraph Cloud, Anthropic Agent SDK, OpenAI Agents SDK, AutoGen | LLM orchestration platforms | Not started | 3 |

---

## 5. Engine Architecture

### 5.1 Surface adapter pattern

```
                                 ┌──────────────────────────────────────┐
                                 │      Transmax Orchestration Core      │
                                 │  (LangGraph agent, audit ledger,      │
                                 │   quality gate, regulatory profiles,  │
                                 │   JobConfigSnapshot, evidence service)│
                                 └────────────▲─────────────────────────┘
                                              │  internal Service API
                                              │  (typed, in-process)
        ┌──────────┬─────────────┬────────────┴──────────┬──────────┬──────────────┐
        │          │             │                       │          │              │
   ┌────┴────┐ ┌───┴────┐  ┌─────┴─────┐         ┌───────┴────┐ ┌───┴───┐  ┌───────┴───────┐
   │  Web    │ │  REST  │  │   MCP     │   ...   │  Webhook   │ │  CLI  │  │  Connectors   │
   │  UI     │ │  API   │  │  Server   │         │  Dispatcher│ │       │  │ (Veeva, ...)  │
   └─────────┘ └────────┘  └───────────┘         └────────────┘ └───────┘  └───────────────┘
```

* **Internal Service API.** A single typed Python interface (`transmax.core.service`) is the only thing surfaces call. It exposes job-lifecycle methods (`submit_job`, `get_job`, `list_jobs`, `cancel_job`, `request_review`, `sign_off`, `verify_audit_chain`, `export_evidence_bundle`, `register_glossary_term`, `register_rule`).
* **Surface adapters** translate transport (HTTP, MCP, Python SDK call, CLI invocation, webhook fan-out) into Internal Service API calls. Adapters carry no business logic.
* **One LangGraph graph** under the Internal Service API; surfaces are unaware of LangGraph.
* **Idempotency, RBAC, quota enforcement, audit logging** live in middleware *between* the surface adapter and the Internal Service API. This guarantees uniform behaviour regardless of how the call entered the system.

### 5.2 Job lifecycle (canonical)

```
SUBMITTED → VALIDATED → SEGMENTED → CONSTRAINTS_LOADED → TRANSLATED →
QUALITY_GATED → [REFINING ↻ ≤3] → BACK_TRANSLATED → REVIEW_REQUIRED →
REVIEWED → SIGNED_OFF → EXPORTED → ARCHIVED
```

Each transition emits a typed event on the audit ledger (`transmax.audit.v1`) and a webhook event (`transmax.webhook.v1`). Surfaces poll or subscribe; the engine is the single source of truth.

### 5.3 Async-first contract

* Submitting a job returns `202 Accepted` with a `job_id` and a poll URL. Synchronous endpoints exist only for short jobs (single segment ≤ 200 tokens) and never run a refinement loop.
* Webhook delivery uses signed HTTPS POSTs (Ed25519 signature in `X-Transmax-Signature` plus a key-rotation header). Replay window 5 minutes.
* Streaming (SSE) is supported for `/jobs/{id}/events` for customers that want a live status feed.

---

## 6. Surface Specifications

### 6.1 REST API v2

* OpenAPI 3.1 source-of-truth at `openapi/transmax-v2.yaml`, generated into Python types and TypeScript types in CI.
* OAuth 2.1 client credentials and authorization-code-with-PKCE flows; scoped API keys for service accounts; no API keys without scope.
* All resources tenant-prefixed: `/v2/orgs/{org_id}/jobs`, `/v2/orgs/{org_id}/glossaries`, etc.
* Idempotency: every POST and PATCH accepts `Idempotency-Key`; engine stores the request hash and the response for 24 hours.
* Pagination: cursor-based (`page_token`), never offset.
* Versioning: URL path version (`/v2/`); breaking changes require `/v3/`. Deprecation policy: 12 months sunset, monthly heartbeat header before removal.
* Rate limiting: leaky-bucket per tenant per scope; standard limits documented; soft (warning header) before hard (429).
* Errors: RFC 9457 problem details (`application/problem+json`) with error code, human message, retry-after where relevant, and a `correlation_id`.

#### 6.1.1 Core endpoints (Phase 1)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v2/orgs/{org_id}/jobs` | Submit a translation job. |
| GET | `/v2/orgs/{org_id}/jobs/{job_id}` | Get job status and results. |
| GET | `/v2/orgs/{org_id}/jobs/{job_id}/events` | SSE stream of lifecycle events. |
| GET | `/v2/orgs/{org_id}/jobs/{job_id}/evidence` | Download signed evidence bundle. |
| POST | `/v2/orgs/{org_id}/jobs/{job_id}/cancel` | Cancel a job. |
| POST | `/v2/orgs/{org_id}/jobs/{job_id}/sign-off` | Reviewer/PM e-signature. |
| GET | `/v2/orgs/{org_id}/audit/chain` | Audit chain head and verification. |
| GET | `/v2/orgs/{org_id}/audit/verify` | Verify chain integrity (range or full). |
| POST | `/v2/orgs/{org_id}/glossaries/{glossary_id}/terms` | Register a glossary term. |
| POST | `/v2/orgs/{org_id}/webhooks` | Register webhook subscription. |
| POST | `/v2/orgs/{org_id}/connectors/{kind}/events` | Connector callback (Veeva, SharePoint, ...). |

#### 6.1.2 Example: submit-job request

```json
POST /v2/orgs/org_42/jobs
Idempotency-Key: 3f7c5b3e-...
{
  "name": "PROD-2026-AT-SmPC-EN-DE",
  "regulatory_profile": "ema-qrd-smpc-v3",
  "source_language": "en-GB",
  "target_languages": ["de-DE", "fr-FR", "es-ES"],
  "document": {
    "kind": "docx",
    "ref": "s3://customer-bucket/uploads/abc.docx",
    "checksum": "sha256:..."
  },
  "glossary_ids": ["glos_ema_smpc_2026"],
  "term_lock_strategy": "edqm-strict",
  "review_policy": "human-required",
  "cost_ceiling_eur": 250.00,
  "callbacks": {
    "webhook_id": "wh_pm_review",
    "deep_link_template": "https://customer.com/translations/{job_id}/review"
  },
  "metadata": {
    "study_id": "AT-2026-001",
    "submission_id": "EMA-2026-04-AT-001"
  }
}
```

Response `202 Accepted`:

```json
{
  "job_id": "job_abcdef",
  "status": "SUBMITTED",
  "links": {
    "self": "/v2/orgs/org_42/jobs/job_abcdef",
    "events": "/v2/orgs/org_42/jobs/job_abcdef/events",
    "evidence": "/v2/orgs/org_42/jobs/job_abcdef/evidence"
  },
  "config_snapshot_hash": "sha256:..."
}
```

### 6.2 MCP Server

* MCP 1.0 over stdio (for desktop agents) and HTTP-SSE (for hosted agent runtimes).
* Tool surface (Phase 1): `submit_translation_job`, `get_translation_job`, `request_review`, `sign_off`, `lookup_glossary_term`, `verify_audit_chain`, `export_evidence_bundle`.
* Each tool's input schema mirrors the REST request body 1:1 (regenerated from the same OpenAPI source). No drift permitted.
* Authentication: bearer-token MCP transport extension; tokens scoped per agent runtime.
* Idempotency keys flow through the MCP `meta` object.
* Result objects include both a structured payload and a `display.summary_md` field for the calling agent to surface to its user — cuts out boilerplate for downstream agents.

### 6.3 Python SDK (`transmax-sdk`)

* PyPI distribution, semantic versioning, Python 3.11+.
* Public surface: `Transmax(api_key=..., base_url=..., region="eu")` client; resource managers (`client.jobs`, `client.glossaries`, `client.audit`, `client.webhooks`, `client.connectors`).
* Sync and async client variants (`Transmax`, `AsyncTransmax`); both share generated types.
* Built-in retry with exponential backoff and idempotency-key generation.
* Streaming helpers (`for event in client.jobs.events(job_id):`).
* Pluggable transport so customers can route through their own egress proxy.
* No leaky LangGraph or LLM-provider symbols in the public surface.

### 6.4 TypeScript SDK (`@transmax/sdk`)

* Phase 2 deliverable. Mirrors the Python SDK feature-for-feature; published to npm with TypeScript types.
* Tree-shakeable; ESM and CJS builds.
* Web-compatible (browser fetch) plus Node.js variant; isomorphic.

### 6.5 CLI (`transmax`)

* Phase 2 deliverable. Single static binary (Rust or Go preferred for distribution; Python with PyOxidizer acceptable).
* Use cases: batch ingest from a folder, daily nightly translate-and-export, CI/CD validation in customer pipelines.
* Subcommands: `transmax submit`, `transmax watch`, `transmax verify-chain`, `transmax export-evidence`, `transmax sign-off`.
* Configuration via `~/.transmax/config.yaml` plus environment variables; outputs JSON for scripting.

### 6.6 Webhooks

* Signed HTTPS POST callbacks, Ed25519 signatures, one signing key per tenant rotated 90 days.
* At-least-once delivery with exponential-backoff retry up to 24 hours, then dead-letter to the audit ledger.
* Events (Phase 1): `job.submitted`, `job.validated`, `job.translated`, `job.quality_gated`, `job.review_required`, `job.review_completed`, `job.signed_off`, `job.exported`, `job.cancelled`, `audit.chain.anchored`.
* Customer-side replay protection via the `transmax-event-id` header and 5-minute timestamp window.

### 6.7 Review-handoff URL

* When `review_policy = "human-required"`, the engine emits a signed deep-link to a hosted review surface (`https://review.transmax.io/r/{token}` where `token` is a JWT bound to job, role and TTL).
* Customers embed this link in their portal/MLR tool/Veeva workflow. The reviewer authenticates via the customer's IdP (SAML/OIDC federation).
* The hosted review surface is the same code path as the in-product `/review/[jobId]` page, but rendered without the workspace shell.
* All reviewer actions flow through the same Internal Service API as the API and SDK surfaces — same audit, same e-signature, same evidence bundle.

### 6.8 Connectors

Connectors are headless surfaces too. They listen for upstream events and call the engine.

| Connector | Trigger | Phase |
| --- | --- | --- |
| Veeva Vault PromoMats / RIM | Vault workflow webhook on document state | 2 |
| SharePoint Online | Microsoft Graph subscription on doc library | 2 |
| Documentum (D2 / xCP) | xCP event listener | 2 |
| eCTD publishers (LORENZ, Extedo, EXT-DM) | Watch-folder + signed manifest | 2 |
| Generic S3/SFTP watcher | Object-arrived event | 1 |
| Customer-provided webhook receiver | Inbound HTTPS POST | 1 |

Each connector registers itself as a *tenant-scoped* identity with a service account; uses the same scoped API keys and idempotency keys; emits the same events.

### 6.9 Agent-to-agent registrations (Phase 3)

* Anthropic Agent SDK tool registration (transmax-as-tool).
* OpenAI Agents SDK registration.
* LangGraph Cloud listed agent.
* AutoGen tool wrapper.
* Each registration is a thin wrapper over the MCP tool surface; no new business logic.

---

## 7. Cross-Cutting Concerns

### 7.1 Identity, Auth and RBAC

* OAuth 2.1 with PKCE for interactive surfaces (UI, review handoff).
* Client credentials for machine-to-machine (REST API, SDK, CLI).
* OIDC federation with customer IdPs (Okta, Azure AD/Entra, Ping, ADFS) for hosted review.
* Scoped API keys: every key has a least-privilege scope (e.g., `jobs:submit`, `jobs:read`, `audit:verify`, `glossary:write`, `webhooks:manage`). Keys hashed at rest; visible exactly once at creation.
* RBAC roles (existing in `app/auth/permissions.py`) enforced by middleware between the surface adapter and the Internal Service API; surfaces never rule on permissions themselves.
* Per-action `permission_required` decorator on the Internal Service API methods, so an unauth'd path is impossible regardless of surface.
* Session lifetime 12 hours for interactive; 90 days for service accounts with mandatory rotation reminders at 60 days.
* Audit trail of all auth events: token-issued, token-revoked, key-created, key-revoked, MFA-stepped-up.

### 7.2 Multi-tenancy and data residency

* Tenant identifier (`org_id`) is required on every Internal Service API call.
* Row-level security (PostgreSQL RLS) enforced at the database layer; no raw queries skip this.
* Per-region deployments (eu-central-1, eu-west-1, us-east-1, us-west-2, ap-southeast-1, ap-northeast-1).
* Tenants pinned to a single region; cross-region replication only for explicit DR with signed customer agreement.
* Customer-managed keys (CMK) via AWS KMS / Azure Key Vault for envelope encryption of segments, evidence bundles, audit payloads.

### 7.3 Idempotency

* All POST and PATCH endpoints accept `Idempotency-Key`. Engine stores `(org_id, key, request_hash, response_body)` for 24 hours.
* On replay: same key, same request hash → return cached response. Same key, different hash → 409 Conflict.
* SDKs auto-generate idempotency keys for retries unless overridden.

### 7.4 Rate limiting and quotas

* Per-tenant default quotas, overridable per contract.
* Cost ceiling per job (`cost_ceiling_eur` in submit) enforced at the LLM-call layer; jobs that would exceed pause for human escalation.
* Per-tenant monthly cost budget configurable; webhook `tenant.budget.threshold_reached` fires at 80% and 100%.
* 429 responses include `Retry-After` and a problem document with the rate-limit kind.

### 7.5 Audit ledger participation

* Every Internal Service API call passes through the audit middleware.
* Each entry contains: `sequence_index`, `previous_hash`, `payload_hash`, `signed_timestamp` (RFC 3161 trusted-timestamp), `actor` (user or service account), `surface` (web, rest, mcp, sdk, cli, connector_veeva, etc.), `tenant_id`, `correlation_id`, `evidence_refs`.
* Daily Merkle root anchored to AWS QLDB and to a signed S3 Object Lock artefact; chain head exported daily as a signed manifest.
* Chain verification is a public endpoint (`GET /v2/orgs/{org_id}/audit/verify`) returning Yes/No plus the Merkle proof.

### 7.6 Observability

* OpenTelemetry traces across surface → middleware → Internal Service API → LangGraph nodes → external LLM providers; trace ID is the `correlation_id`.
* Metrics (Prometheus): job latency P50/P95/P99 per surface, defect rate, refinement-loop iterations, LLM cost, audit-chain head age, webhook delivery success rate.
* Structured logs (JSON) with PII redaction at the logger boundary.
* Customer-facing status page (`status.transmax.io`) with surface-level SLOs.

### 7.7 Versioning and deprecation

* OpenAPI versioned in URL path (`/v2/`).
* MCP tool schema versioned via `tool.version` metadata.
* SDK semantic versioning; major version bumps gated by RFC review.
* Deprecation policy: 12 months minimum, customer notification at month 0, 6, 9, 11; signed contract amendment for early sunset.

### 7.8 Security baseline

* CSP, HSTS, X-Frame-Options, Permissions-Policy on all browser-facing surfaces.
* mTLS optional for high-assurance customers.
* Secrets in AWS Secrets Manager / Azure Key Vault, never in env files.
* All SDKs ship with reproducible builds and SLSA L3 attestation.
* SBOM (CycloneDX) generated and signed on every release.
* Penetration test annually plus on every major release.

---

## 8. Pricing and Packaging

| Tier | What's included | Indicative price |
| --- | --- | --- |
| **Headless Foundation** | REST API + Python SDK + MCP + Webhooks; standard rate limits; shared region; community support | €0.04–€0.08 per word + €5,000/mo platform fee |
| **Headless Enterprise** | All of Foundation + TS SDK + CLI + connectors + dedicated region + SLA + 24/7 support + customer-managed keys | €0.08–€0.15 per word + €15,000–€40,000/mo platform fee |
| **Platform** | Hosted UI + reviewer seats + everything in Headless Enterprise | + €120/seat/mo |
| **Regulatory Pack (add-on)** | Part 11 attestation, GAMP 5 validation summary, EU AI Act conformity package, FDA credibility framework artefacts, EMA QRD validators, EDQM standard-term enforcement, signed evidence bundle export | €30,000–€80,000/yr depending on scope |

The Regulatory Pack is required for any production regulatory submission use; customer purchase orders enforce this contractually. The Headless Foundation tier exists for partners and CROs who want to embed transmax in their own product.

---

## 9. Phased Delivery Plan

### Phase 1 — Headless MVP (0–90 days)

Goal: a callable, documented, audited engine that two pilot customers can integrate into a minimum-viable workflow.

**Engine**
1. Internal Service API extracted; surfaces refactored to call only it.
2. Idempotency middleware; RBAC middleware; audit middleware unified.
3. JobConfigSnapshot includes prompt version, model, region, surface metadata.
4. Audit chain rebuilt on domain-separated SHA-256 with daily Merkle anchor.

**Surfaces**
5. REST API v2 published; OpenAPI 3.1 source-of-truth; OAuth 2.1.
6. MCP server hardened with bearer auth and the same schemas.
7. Python SDK 1.0.0 on PyPI with sync + async clients.
8. Webhooks with Ed25519 signatures and at-least-once delivery.
9. S3/SFTP connector and generic webhook receiver.

**Validation**
10. Contract conformance suite (Section 10.1).
11. Surface-parity suite for the top 12 user journeys.
12. Vendor security questionnaire response template.

### Phase 2 — Multi-Surface Production (3–6 months)

13. TypeScript SDK 1.0.0 on npm.
14. CLI 1.0.0 (Rust binary).
15. Review-handoff URL with SAML/OIDC federation.
16. Veeva Vault PromoMats and RIM connector.
17. SharePoint Online connector.
18. Per-region deployments (EU + US); customer-managed keys.
19. SOC 2 Type II evidence collection in flight; ISO 27001 audit booked.

### Phase 3 — Agent-to-Agent and Differentiation (6–12 months)

20. Anthropic Agent SDK and OpenAI Agents SDK tool registrations.
21. LangGraph Cloud listed agent.
22. eCTD publisher connectors (LORENZ, Extedo, EXT-DM).
23. Documentum connector.
24. Public chain-anchor verification page (`verify.transmax.io`) with third-party attestation.
25. EU AI Act conformity package published per release; FDA credibility framework artefacts per release.

---

## 10. Validation Strategy

The validation strategy is the heart of this document. *Building* a multi-surface product is straightforward; *proving* it works correctly across all surfaces, at every release, in a way a regulator-facing QA team will sign off on, is the hard part.

We will operate eight validation tracks. Every release ships a Validation Summary Report (VSR) that documents the result of each track, signed by the Programme Lead and the Regulatory Affairs Lead.

### 10.1 Track 1 — Contract Validation

**Objective:** Every surface conforms exactly to its published schema.

* OpenAPI 3.1 is the source of truth for REST. Generated Python types (datamodel-code-generator) and TypeScript types (openapi-typescript) feed the SDKs. CI fails if generated types drift from the YAML.
* MCP tool schemas are generated from the same OpenAPI document via a custom transformer; CI verifies parity.
* Spectral lint enforces our internal API style guide on every PR.
* Schemathesis runs property-based fuzz tests against the OpenAPI: every endpoint receives randomised valid inputs and assertions check `4xx` shape and round-trip integrity.
* Pact contract tests between SDKs and the REST API run in CI; the SDKs are *consumers*, the API is the *provider*.

**Deliverables per release:** Spectral report, Schemathesis report, Pact verification report.

### 10.2 Track 2 — Surface Parity Tests

**Objective:** Identical inputs through different surfaces produce identical outcomes.

* A *parity matrix* covers the top 20 user journeys (submit, validate-and-segment, translate, quality-gate, refine, request review, sign-off, export-evidence, verify-chain, register-glossary-term, etc.).
* Each journey has a single golden test fixture (input + expected outcome).
* The test runner replays the journey through six surfaces: REST API direct, Python SDK, TypeScript SDK, CLI, MCP tool, and an internal Python harness representing the UI server actions.
* Outcomes compared field-for-field after redacting timestamps and IDs.
* Any divergence fails the build with the surface(s) and the divergent fields named.

**Deliverables per release:** Surface Parity Matrix (Yes/No per surface per journey) appended to VSR.

### 10.3 Track 3 — Behavioural and Golden-Path Tests

**Objective:** Documented behaviours hold under normal and adverse conditions.

* A corpus of *real* pharma documents: anonymised SmPC, PIL, IFU, ICF, CSR, CTD Module 2.5 sections, cleaned from public regulator submissions. Minimum 50 documents at GA, growing to 250 by Phase 3.
* For each document we record an expected segmentation, an expected QRD section presence/absence, expected EDQM-locked terms, expected defect taxonomy hits when defects are seeded, and expected exit state.
* Snapshot tests: structured outputs (segments, defects, evidence bundles) are diffed against committed snapshots. Reviewers approve snapshot changes via PR.
* Failure injection: LLM provider 429s, LLM provider timeouts, vector-store unavailability, audit-anchor unavailability, connector retries — each exercised at least once per release.
* Property tests on the audit chain: for any sequence of N events, `verify_chain_integrity(0..N)` returns true; for any tampered event, it returns false with the offending index.

**Deliverables per release:** Golden-corpus pass rate, snapshot diff report, failure-injection report.

### 10.4 Track 4 — Security Validation

**Objective:** No unauthenticated, unauthorised, replayed, forged or excessive call succeeds, on any surface.

* Authn matrix: every endpoint × every auth mode (no token, expired token, wrong-tenant token, scope-insufficient token, replayed token). Expected outcomes captured; tests run in CI.
* Authz matrix: every endpoint × every role × every tenant boundary (own tenant, other tenant). RBAC failures expected and asserted.
* Idempotency tests: same key, same body → same response; same key, different body → 409.
* Rate-limit tests: burst → 429 with `Retry-After`; sustained at threshold → 200; cool-down → 200.
* CSRF and clickjacking tests on browser-facing surfaces (review handoff).
* SDK supply-chain: SLSA L3 attestation, npm/PyPI provenance verified in release pipeline.
* Annual external pen-test plus pen-test on every major release; findings tracked in a public-facing security advisory feed.
* Secret-scanning, SAST (CodeQL or Semgrep), DAST (OWASP ZAP) gates in CI.

**Deliverables per release:** Authn matrix report, authz matrix report, SAST/DAST reports, dependency vulnerability report, signed SBOM.

### 10.5 Track 5 — Performance and SLO Validation

**Objective:** Documented SLOs hold under representative load on every surface.

| SLO | Target | Validation method |
| --- | --- | --- |
| REST submit P95 latency | ≤ 300 ms | Locust load test, 200 concurrent clients |
| Translate-and-review P95 (1k words, 5 langs) | ≤ 5 min | Synthetic batch, 50 concurrent jobs |
| Webhook delivery success ≤ 5 min | ≥ 99.5% | Synthetic webhook receiver |
| Audit-chain verification, 1M events | ≤ 30 s | Benchmark, fresh DB |
| MCP tool round-trip P95 | ≤ 300 ms | MCP harness |
| SDK retry-recovery | 100% under transient 5xx | Chaos test |

* Load tests run on every release in a staging cluster sized to one tenant's max contract.
* Performance budgets gate releases; regressions > 10% fail CI.
* Continuous profiling in production (py-spy, pyroscope) with weekly reports.

**Deliverables per release:** SLO conformance report, load-test artefacts.

### 10.6 Track 6 — Compliance Validation

**Objective:** Every release ships with the regulator-facing artefacts a CSV/QA team needs.

* **Validation lifecycle (GAMP 5).** Each release links to: User Requirements Specification, Functional Specification, Design Specification, Risk Assessment, IQ scripts (deployment), OQ scripts (function), PQ scripts (performance), Validation Summary Report. Tests are automated where possible; manual scripts are signed.
* **21 CFR Part 11.** Per-release attestation that audit trail, e-signatures, access controls and time-stamping operate as designed; evidence is the test artefacts from Track 3 and Track 4.
* **EU AI Act technical documentation.** Auto-generated from JobConfigSnapshot metadata: model card per LLM per language pair, training-data lineage statement (transmax does not train on customer data), risk management, post-market monitoring metrics, instructions for use.
* **FDA AI/ML credibility framework.** Per-release credibility plan, executed evidence, controls, post-market monitoring.
* **EMA QRD validators.** Per release, the validator suite is run against the entire golden corpus; any change to validator behaviour is documented and reviewed.
* **EDQM standard terms.** EDQM dataset version pinned per release; terminology drift report attached.
* **ISO 17100 / 18587.** Process evidence: translator and reviewer competence records (where applicable), revisions register, post-edit distance metrics.
* **SOC 2 / ISO 27001.** Continuous control monitoring (Drata, Vanta or equivalent); evidence collected by control rather than by release; quarterly internal audit.

**Deliverables per release:** Validation Summary Report, signed by Programme Lead and Regulatory Affairs Lead. Includes pointers to all artefacts and a single pass/fail per regulation.

### 10.7 Track 7 — Customer Acceptance and Sandbox Programme

**Objective:** Real customers can verify in a sandbox that the system performs as documented before signing a contract amendment.

* Sandbox tenant per prospective customer; loaded with anonymised pharma corpus.
* Self-service "validation playground": customer runs the same Track 3 golden-corpus tests against their own seed documents and gets a signed report.
* Acceptance test pack: a documented set of 25 user-acceptance scenarios that customer QA executes; results land in a co-signed acceptance certificate.
* Customer-facing changelog with breaking-change advisories, deprecations and validation impact statements.
* Quarterly customer-validation council: customer QA leads review the upcoming roadmap and surface validation concerns.

**Deliverables per release:** Customer changelog, acceptance test pack, sandbox refresh, customer-validation council notes.

### 10.8 Track 8 — Independent Third-Party Attestation

**Objective:** Independent parties confirm that what we claim is what we ship.

* Annual SOC 2 Type II audit (Schellman, A-LIGN or equivalent).
* Annual ISO 27001 surveillance audit; recertification every three years.
* Annual ISO 17100 / 18587 audit (LICS, EUATC or equivalent).
* Annual ISO 13485 audit (BSI, DNV) once MDR/IVDR customers are onboarded.
* Annual independent penetration test (NCC Group, Bishop Fox, Trail of Bits).
* Annual independent audit-chain review: a trusted third party verifies the previous year's anchored Merkle roots and signs an attestation report.
* Annual EU AI Act conformity assessment review by a notified body or equivalent advisor; FDA credibility framework review by an external biostatistical/CSV consultancy.
* Bug-bounty programme (HackerOne or equivalent) with a public scope and a documented SLA on triage.

**Deliverables annually:** External attestation reports, posted to a customer-accessible trust centre (`trust.transmax.io`).

### 10.9 Track 9 — Continuous Validation in CI/CD

**Objective:** All of the above runs on every commit, not just every release.

* Pull-request gates: unit tests, contract lint, contract conformance, surface-parity quick suite, security SAST, secret scanning. P95 PR build time ≤ 12 min.
* Merge-to-main gates: full surface-parity suite, snapshot regression, SBOM generation, signed artefact build.
* Nightly: full golden-corpus regression, SLO load tests, full audit-chain integrity test (1M events synthetic), failure-injection suite, dependency vulnerability scan.
* Weekly: pen-test surface scan (DAST), review handoff browser test (Playwright on Chrome, Firefox, Safari, Edge).
* Monthly: chaos-engineering exercise (kill an LLM provider, kill the audit anchor, kill a region) on staging.
* Per-release: full Validation Summary Report assembled and signed.

### 10.10 Validation Deliverables — Per-Release Bundle

Every GA release ships a tagged validation bundle in addition to the software artefacts. Customers can download it via `GET /v2/orgs/{org_id}/releases/{tag}/validation-bundle`. Contents:

* `vsr.pdf` — Validation Summary Report, signed.
* `openapi.yaml` — pinned API surface.
* `mcp-tools.json` — pinned MCP surface.
* `sbom.cdx.json` — signed SBOM.
* `slsa-attestation.intoto.jsonl` — supply-chain provenance.
* `surface-parity.json` — parity-matrix results.
* `golden-corpus.json` — golden-corpus pass rate.
* `slo-report.json` — SLO conformance.
* `security-summary.pdf` — Track 4 summary.
* `compliance-pack/` — Part 11 attestation, GAMP 5 VSR, EU AI Act technical documentation, FDA credibility artefacts, EDQM dataset version note.

---

## 11. Acceptance Criteria — "Done" for the Headless Programme

The headless and multi-surface programme is "done" when **all** of the following are true on a single release tag.

1. REST API v2, MCP server, Python SDK, TypeScript SDK, CLI, webhooks and review-handoff URL are all live, documented and version-pinned.
2. The Surface Parity Matrix shows Yes for all top-20 user journeys across all six surfaces.
3. Contract Validation, Surface Parity, Golden-Corpus, Security Validation, Performance/SLO, Compliance Validation, Sandbox Acceptance and Third-Party Attestation tracks have all run and reported pass.
4. At least three customers have integrated via headless surfaces in production, with co-signed acceptance certificates.
5. ISO 27001 certified, SOC 2 Type II issued, HIPAA BAA available, GDPR DPA published, EU AI Act conformity package published, FDA credibility framework artefacts published.
6. The trust centre (`trust.transmax.io`) is live with downloadable validation bundles per release tag for the last 24 months.
7. The chain-verification page (`verify.transmax.io`) is publicly accessible and serves Merkle proofs for any tenant's anchored chain.

---

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Surface drift over time (one surface evolves faster than the others) | High | High | Single OpenAPI source-of-truth; generated SDKs; surface-parity gate on every PR. |
| Audit-chain redesign breaks customer historical evidence | Low | High | One-time chain-migration tool; preserve old chain alongside new with cross-link; signed migration attestation. |
| Customers use headless API without buying the regulatory pack and self-attest | Medium | Medium | Contract enforcement; usage telemetry; gate the signed evidence bundle export behind the regulatory-pack scope. |
| Long-running jobs leak through synchronous endpoints | Medium | Medium | Hard cap on synchronous endpoint scope (single segment); 202-only for full-document submit. |
| MCP transport vulnerabilities (still a young protocol) | Medium | Medium | mTLS-optional; bearer-token MCP extension; close monitoring of MCP CVE feed; network-isolated runtime. |
| Customer connector misuse (Veeva creds leaked) | Medium | High | Per-connector scoped service accounts; key rotation alerts; ability to revoke a connector key without disabling the tenant. |
| Validation overhead slows releases | High | Medium | Automate Tracks 1–5 entirely; treat manual tracks 6–8 as quarterly cadence with auto-collected evidence; budget 20% of engineering capacity for validation infrastructure. |
| EU AI Act notified-body capacity in 2026–2027 | High | High | Engage a Big-Four advisor or notified body in Phase 1; pre-book conformity assessments; build the evidence pipeline before the policy bites. |

---

## 13. Open Questions

These are decisions still owed by the Programme Lead before kick-off.

1. CLI binary distribution: Rust, Go or Python? (Recommendation: Rust.)
2. Hosted review surface domain — same origin as workspace UI or separated (`review.transmax.io`)?
3. Customer-managed keys: AWS KMS only, or BYOK across AWS/Azure/GCP from day one?
4. Trusted-timestamp authority: in-house plus DigiCert, or external only?
5. Will we support on-premise / air-gapped deployments for top-tier customers, or insist on multi-tenant SaaS only?
6. Public bug-bounty scope: REST + MCP from day one, or staged rollout?
7. SDK languages beyond Python and TypeScript — Java? Go? .NET? Decision delayed to Phase 3.

---

## 14. Appendix A — Example Webhook Event

```json
POST https://customer.example.com/transmax/hooks
Content-Type: application/json
X-Transmax-Event-Id: evt_01J7Y2K8X9
X-Transmax-Event-Type: job.review_required
X-Transmax-Tenant: org_42
X-Transmax-Timestamp: 2026-05-12T09:14:22Z
X-Transmax-Signature: ed25519=...

{
  "event_id": "evt_01J7Y2K8X9",
  "event_type": "job.review_required",
  "occurred_at": "2026-05-12T09:14:22Z",
  "tenant_id": "org_42",
  "job_id": "job_abcdef",
  "surface": "rest",
  "config_snapshot_hash": "sha256:...",
  "audit_sequence_index": 482917,
  "review": {
    "policy": "human-required",
    "reviewer_role_required": "Reviewer",
    "deep_link": "https://review.transmax.io/r/eyJhbGciOi...",
    "expires_at": "2026-05-13T09:14:22Z"
  },
  "summary": {
    "segments_total": 412,
    "segments_with_critical_defects": 2,
    "segments_with_major_defects": 11,
    "edqm_terms_locked": 47,
    "qrd_sections_complete": true
  }
}
```

## 15. Appendix B — Example MCP Tool Definition

```json
{
  "name": "submit_translation_job",
  "version": "v2.0.0",
  "description": "Submit a regulated-content translation job to transmax.",
  "input_schema": {
    "type": "object",
    "required": ["org_id", "regulatory_profile", "source_language", "target_languages", "document"],
    "properties": {
      "org_id": { "type": "string" },
      "regulatory_profile": { "type": "string", "enum": ["ema-qrd-smpc-v3", "ema-qrd-pil-v3", "fda-spl-v2", "mhra-pil-v1"] },
      "source_language": { "type": "string" },
      "target_languages": { "type": "array", "items": { "type": "string" } },
      "document": { "$ref": "#/$defs/Document" },
      "glossary_ids": { "type": "array", "items": { "type": "string" } },
      "term_lock_strategy": { "type": "string", "enum": ["edqm-strict", "edqm-permissive", "custom"] },
      "review_policy": { "type": "string", "enum": ["human-required", "human-optional", "auto"] },
      "cost_ceiling_eur": { "type": "number" },
      "callbacks": { "$ref": "#/$defs/Callbacks" },
      "metadata": { "type": "object", "additionalProperties": true }
    }
  }
}
```

---

*End of specification.*
