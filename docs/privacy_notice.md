# TransMax Privacy Notice

**Last updated**: 2026-05-01
**Status**: Stub — to be reviewed by external counsel before any pilot signs (TMX-4001)

---

## What this notice is

A description of how TransMax processes data. It is the customer-facing companion to the Data Processing Addendum (DPA) we sign with each customer. The DPA is the contractual instrument; this notice is the plain-language explanation.

This notice will be replaced by a counsel-reviewed version under `compliance/privacy_notice_v1.md` before the first pilot is signed (per the v3.0 release plan).

---

## What we process and why

| Data class | Examples | Legal basis (GDPR) | Why |
|---|---|---|---|
| **Customer source documents** | SmPC, PIL, CSR, ICF, protocols submitted for translation | Contract performance (Art. 6.1.b) | The product needs the source text to produce the translated text. |
| **Customer translations** | The output of the translation pipeline | Contract performance | We persist these so reviewers can sign off and so audit trails reconstruct the work. |
| **Audit events** | Per-job, per-segment audit chain entries with hashes, timestamps, actor identities | Legitimate interest (Art. 6.1.f) + regulatory obligation | Required by 21 CFR Part 11 and EU GDPR Art. 30 records of processing. |
| **Reviewer accounts** | Email, name, role, organisation, last-login timestamp | Contract performance | Identity for authentication and audit trail. |
| **Telemetry** | Per-tenant aggregate counts (jobs/day, defects/day, LLM cost) | Legitimate interest | Operational health + customer billing. No content. |
| **Logs** | Application logs with PII redacted at the boundary | Legitimate interest | Operations + incident response. PII-in-logs is treated as a P0 incident (see `docs/incident_response.md`). |

We do **not** process:

- Patient identifiers, in raw form, in any LLM prompt — PII is redacted via Presidio (post v3.0 TMX-3805) before any LLM call. Until v3.0 lands the new PII service, the regex-based service in `app/services/pii_service.py` is acknowledged to be best-effort and customers are advised in their DPA of the residual risk.
- Customer source content for *training* of any LLM — our LLM providers (OpenAI, Anthropic, DeepL) are contracted under no-training agreements; the relevant clauses are part of each provider's qualified-supplier file (TMX-4003).

---

## Where data lives

- **Primary storage**: PostgreSQL with pgvector, in **EU-Central-1 (Frankfurt)** for v3.0. Encrypted at rest with AWS-managed keys; customer-managed keys (CMK) deferred to v3.2.
- **Object storage**: AWS S3 (eu-central-1) for uploads + audit-bundle archival, with Object Lock compliance retention for audit anchors.
- **Caching**: Redis (eu-central-1) for transient session and queue state. No PII in cache.
- **Logs**: Grafana Cloud (Frankfurt) with redaction at the logger boundary.
- **LLM providers**: OpenAI / Anthropic / DeepL — see each provider's data-processing terms in their qualified-supplier file. Hosted-only in v3.0; BYOK is a v3.2 option.

US-East and APAC regions are deferred to Phase 2 / Phase 3.

---

## Sub-processors

The current sub-processor list:

| Sub-processor | Service | Data class | Region |
|---|---|---|---|
| AWS | Compute, storage, KMS | All | eu-central-1 |
| OpenAI | LLM (translation, reflexion, refinement) | Source text + translated text (de-identified post-v3.0) | EU data residency commitment |
| Anthropic | LLM (back-translation, regulatory checks) | Source text + translated text (de-identified post-v3.0) | EU data residency commitment |
| DeepL | MT (low-risk fallback) | Source text + translated text | EU |
| FreeTSA | RFC 3161 trusted-timestamping for audit anchors | Hash of audit events (no content) | EU |
| Grafana Cloud | Telemetry + logs | Aggregated telemetry; redacted logs | EU |
| Auth0 (TMX-3013) | Identity provider | Email, name, role | EU |

The list is signed and dated per release. Customers are notified ≥ 30 days before any sub-processor change.

---

## Data subject rights (GDPR Art. 15-22)

For data subjects (typically reviewers and PHI subjects in source content):

- **Right to access**: a customer's own users can request their account data via support; broader requests route through the customer's DPO.
- **Right to rectification**: customers can edit their account data directly in the workspace.
- **Right to erasure**: TransMax processes erasure requests via redaction-by-tombstone — the customer record is replaced with a hash and a tombstone marker, preserving the audit chain. Source content can be erased entirely on request, subject to the regulatory retention obligations the customer is bound by. v3.0 ships this primitive (TMX-3015 + TMX-3106).
- **Right to portability**: customers can export their tenant's data as a signed bundle via the validation-bundle endpoint.
- **Right to object / restrict processing**: contact privacy@transmax.io.

Response time: **30 days** maximum, per GDPR.

---

## Retention

| Data class | Default retention | Override |
|---|---|---|
| Source documents | 7 years (regulatory floor for pharma submissions) | Per-tenant configurable down to 1 year |
| Translations | 7 years | Same |
| Audit chain entries | **Indefinite** (immutable; redacted-by-tombstone on request) | Cannot be shortened |
| Audit anchor objects (S3 Object Lock) | 10 years | Set by Object Lock retention; cannot be shortened |
| Reviewer accounts | Until offboarding + 90 days | Per-tenant policy |
| Logs | 30 days hot, 365 days cold archive | Configurable |
| Telemetry | 13 months | Standard |

---

## Data security

- TLS 1.2+ in transit
- AES-256 at rest
- MFA enforced for production access (TMX-3013)
- Per-tenant row-level isolation (TMX-3012, TMX-3015)
- Audit-chain integrity verified by an external attestation programme (TMX-3107 daily anchors; v3.3 third-party annual attestation)
- Pen-test annually + on every major release (Track 8, Phase 2+)

---

## Contact

- Privacy questions: **privacy@transmax.io**
- Data subject requests: **dsar@transmax.io**
- DPO (when appointed): listed in the per-customer DPA
- Address: TBD — added when entity registered

---

## Changes to this notice

We notify customers via email at least **30 days** before any material change. Material changes include:
- Adding a new sub-processor
- Changing the legal basis for processing
- Changing the default retention
- Changing the regions where data is processed

This notice is versioned in git; the canonical history is in `docs/privacy_notice.md`'s commit log.
