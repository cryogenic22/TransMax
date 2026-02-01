## PRD: TransMax

**Product:** Controlled AI Translation Service for Regulated Pharma Content
**Version:** 1.1
**Date:** 17 January 2026

---

## 1) Purpose

Build a translation service that produces **high-accuracy, meaning-preserving translations** for regulated pharma content, with **terminology enforcement, structured quality checks, and audit-grade traceability**.

TransMax outputs:

* A translation draft
* A structured quality report (typed issues, severity)
* A routing decision: **PASS / REVIEW_REQUIRED / BLOCKED**
* A structured audit record tied to versions of model, prompts, glossaries, and policy

---

## 2) Goals and success metrics

### Goals

1. Preserve meaning, especially safety language, across supported languages.
2. Enforce mandatory terminology with versioned glossaries.
3. Catch high-risk errors deterministically (numbers, units, negation, modality, frequency).
4. Provide structured traceability per request.
5. Support Arabic (RTL) and Japanese (non-whitespace tokenisation) without hacks.

### Success metrics (pilot)

* **0 critical errors** on the golden set for selected doc types and language pairs.
* **≥ 98% mandatory terminology compliance** on golden set.
* **≥ 90% reviewer satisfaction**: “reduces review effort”.
* **P95 latency**:

  * ≤ 8 seconds for ≤ 1,000 words (sync)
  * async option for large payloads

---

## 3) In-scope (v1.1)

### Document types (pilot)

* SmPC / PIL / labelling fragments: warnings, posology, contraindications
* Patient-facing instructions (tone controlled)

### Languages (v1.1)

* English → Spanish (pilot baseline)
* **English → Arabic** (new)
* **English → Japanese** (new)

### Key features

* Deterministic segmentation into translation units with stable IDs
* **Language packs** (Arabic and Japanese included)
* Glossary enforcement and optional Translation Memory (TM)
* Draft translation + bounded refinement loop
* Deterministic quality gates (script-aware)
* Composite scoring + routing decision
* Structured audit record with hashes
* REST API
* **Postgres + pgvector** as the primary data store layer

---

## 4) Out of scope (v1.1)

* Auto-approval for high-risk documents without defined review policy
* Full reviewer UI, Word add-in, Veeva plugin
* Perfect DOCX/PDF layout preservation (text-first pipeline only)
* Training/fine-tuning on client data
* Persisting raw input/output by default (hashes + structured logs by default)

---

## 5) Core design principle

**Deterministic checks + controlled LLM drafting.**
LLMs draft and refine. Deterministic gates decide whether output is acceptable and what must be fixed or escalated.

---

## 6) Personas and journeys (unchanged)

* Regulatory writer, localisation manager, QA/compliance, linguist/reviewer
  Primary journey remains API-led.

---

## 7) Functional requirements

### FR1: Input normalisation and segmentation

* Segment input into stable units (`segment_id`) and preserve order.
* Must support lists/headings as separate segments.
* Must produce a segmentation manifest.

**Acceptance criteria**

* Same input + same versions → identical segmentation and IDs.
* Segment count preserved across the pipeline (1:1 in v1.1).

---

### FR2: Language Packs (NEW)

Introduce a language pack per target language. Each pack defines:

* Sentence segmentation rules
* Normalisation rules for checks (not for output)
* Tokenisation strategy for gates and glossary matching
* Script direction metadata (LTR/RTL)
* Default review policy per risk level
* Allowed digit policy (Arabic-Indic vs Western) and decimal separator policy

**Arabic pack requirements**

* Script direction: RTL
* Normalise for checks: Alef variants, tatweel removal, whitespace normalisation, digit normalisation (configurable)
* Gates must treat mixed-script content safely (drug names often remain Latin)

**Japanese pack requirements**

* Script direction: LTR
* Tokenisation must not rely on whitespace
* Glossary entries must support preferred form + allowed variants (kanji/kana/katakana where applicable)

**Acceptance criteria**

* Adding a new language requires adding a language pack configuration and tests, not changing core orchestration logic.
* Audit record includes `language_pack_id` and `language_pack_version`.

---

### FR3: Glossary and style constraint retrieval

* Retrieve mandatory terms, forbidden terms, preferred phrases.
* Glossaries are versioned: `glossary_id`, `glossary_version`.
* Glossary matching uses the language pack tokenisation/normalisation.

**Acceptance criteria**

* Mandatory term check works for Japanese without whitespace dependence.
* Arabic mandatory term check works across normalised variants.

---

### FR4: Translation generation

* Produce initial translation incorporating constraints.
* Output is segment-aligned with `segment_id`.

**Acceptance criteria**

* No missing segments.
* Output uses target script direction metadata where relevant (for downstream rendering).

---

### FR5: Deterministic quality gates (script-aware)

System produces typed violations with severity. At minimum:

**Critical (BLOCKED)**

* Number mismatch (value change)
* Unit mismatch (mg/mcg/mL etc)
* Negation flip (do not / contraindicated)
* Frequency mismatch (daily/weekly etc)

**Major (REVIEW_REQUIRED)**

* Missing mandatory term
* Forbidden term present
* Modality drift (must/should/may)
* Population drift (adult/paediatric/elderly)

**Arabic-specific gates (NEW)**

* Digit form policy violation (if configured not to change)
* Decimal separator inconsistency
* Unit adjacency check (keep number and unit bound)

**Japanese-specific gates (NEW)**

* Mandatory term/phrase presence check using tokenizer rules
* Prohibited variant detection where glossary disallows it

**Acceptance criteria**

* Every violation includes: `type`, `severity`, `segment_id`, `evidence`, `message`.
* Any critical violation forces `BLOCKED` regardless of score.

---

### FR6: Bounded refinement loop

* Up to N iterations (default 2).
* Refinement actions are targeted to specific violations only.

**Acceptance criteria**

* Loop terminates deterministically.
* Audit record logs each iteration and actions taken as structured events.

---

### FR7: Decisioning and scoring

Return:

* `decision`: PASS | REVIEW_REQUIRED | BLOCKED
* component scores: terminology, safety, format, overall (0–1)
* quality report with violations

**Acceptance criteria**

* Critical → BLOCKED always.
* Review policy configurable via `risk_level`.

**Default policy (v1.1)**

* High risk labelling safety content:

  * Arabic: default **REVIEW_REQUIRED** even if no major issues, until validation proves otherwise
  * Japanese: default **REVIEW_REQUIRED** for patient-facing safety sections
* Medium risk: PASS allowed if no major/critical and overall above threshold
* Low risk: PASS allowed, still block on critical

---

### FR8: Audit trail (structured, not free-text reasoning)

Per request, store:

* request metadata
* input/output hashes
* model + prompt versions
* glossary/TM versions
* checks run, violations, actions taken
* decision + scores
* timestamps

**Acceptance criteria**

* Audit JSON validates against schema.
* `audit_trail_id` returned in API response.

---

### FR9: API endpoints

1. `POST /api/v1/translate`
2. `GET /api/v1/audit/{audit_trail_id}`
3. `GET /api/v1/health`

**Acceptance criteria**

* Auth required for all non-health endpoints.
* Size limits and rate limits enforced.

---

## 8) Data and storage: Postgres + pgvector (UPDATED)

### Primary database

**Postgres** for metadata, versioning, policy, audit indexes, and operational state.
**pgvector** for similarity retrieval.

### Data entities (minimum)

* `glossary` (id, version, domain, language pair, owner, status)
* `glossary_terms` (term_id, source_text, target_text, allowed_variants, forbidden_variants, metadata)
* `translation_memory` (tm_id, version, segment_hash, source, target, embeddings, metadata)
* `audit_records` (audit_id, timestamp, hashes, versions, decision, scores, pointers)
* `language_packs` (pack_id, version, rules, tokenizer config, normalisation config)

### Storage policy

* Default: store hashes + structured audit data in Postgres.
* Optional: store raw inputs/outputs in Postgres only if explicitly enabled per tenant and encrypted.

**Acceptance criteria**

* Tenant isolation enforced at the DB level (row-level security or separate schemas per tenant).
* All embeddings stored in pgvector with predictable indexing strategy.

---

## 9) Non-functional requirements (updated highlights)

### Security

* OAuth2/JWT or mTLS
* Rate limiting and request size limits
* Input sanitisation (prompt injection defences)
* Encryption at rest for Postgres and backups

### Internationalisation readiness

* Arabic: BiDi-safe handling in any debug or future review screens
* Store both:

  * `text_raw` (exact output)
  * `text_normalised` (checks only, not presented as final)

### Observability

* Metrics by language pack: violation types, decision rates, latency, token usage

### Versioning and change control

* Version everything that can change behaviour:

  * model, prompt, policy, glossary, language pack
* Any change requires a version bump recorded in the audit trail

---

## 10) Validation plan (expanded for Arabic and Japanese)

### Golden sets (per language)

* Safety-critical segments: dosage, contraindications, warnings
* Adversarial cases: negation, decimals, frequency, unit conversions (should fail), mixed script
* Patient vs HCP tone samples

### Acceptance

* **0 critical errors** on golden set per language pack before lowering default review requirement.
* Separate thresholds per language pack if needed.

---

## 11) Rollout plan (v1.1)

1. Pilot English → Spanish on one doc type (baseline).
2. Add Arabic pack and validate on a controlled subset (labelling fragments).
3. Add Japanese pack and validate on controlled subset (patient-facing and HCP fragments separately).
4. After golden-set performance stabilises, adjust review policy from default REVIEW_REQUIRED where justified.

---

## 12) Open questions (kept minimal but real)

* Which sections are allowed to PASS without mandatory human review for Arabic and Japanese, if any, in the pilot?
* Do you want Arabic digits to remain Western, switch to Arabic-Indic, or configurable per market?

---

