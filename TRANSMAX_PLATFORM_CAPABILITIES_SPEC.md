# Transmax — Platform Capabilities Specification

**Status:** Internal design specification, draft v0.9
**Owner:** Product Management — Pharma Translation Agent
**Audience:** Engineering leads, regulatory affairs, security, validation/QA, GTM, customer-facing solution architects
**Date:** May 2026
**Companion documents:** *Transmax — Code Review and Enterprise Upgrade Path* (Word, May 2026); *Transmax — Headless and Multi-Surface Agent Specification* (Markdown, May 2026)

---

## 1. Purpose and Scope

This specification covers the four platform capability pillars that turn transmax from a translation engine into a defensible, regulator-grade pharma platform. Each pillar is partly scaffolded in the codebase today and needs deliberate productisation.

| Pillar | Theme | Today | Target |
| --- | --- | --- | --- |
| 1 | Knowledge, rules, Black Books, domain context | Single flat `TranslationRule` table; auto-promotion at confidence 0.90; no tenant scope | Layered, signed, version-controlled rule system with provenance, conflict resolution and tenant isolation |
| 2 | Phrase memory, determinism, token-cost optimisation | TM table with pgvector; exact-match batch; no LLM-bypass cascade | Four-tier resolution path (Determinism Library → Exact TM → Fuzzy TM → LLM) with multi-layer caching |
| 3 | Confidence scoring, check-and-recheck, human escalation | Stub `confidence_service.py`; per-pair calibration prior; no calibrated meta-model | Eight-signal calibrated confidence with tiered thresholds, regenerate-and-compare loop, audited escalation routing |
| 4 | Format fidelity (incl. formulas, TLFs) | Plaintext only; naive period split; pypdf basic ingestion; export stub | XLIFF 2.1 canonical; native ingestion of DOCX, XLSX, PPTX, PDF (with OCR), HTML, XLIFF, TMX, IDML, RTF, MathML/OOML; format-fidelity QA gate |

The spec is intended to be the engineering and regulatory contract for building these capabilities. It does not duplicate the code-review findings (already in the Word doc) or the surface design (already in the Headless Agent Spec); it references both.

---

## 2. Cross-Pillar Principles

Six principles bind the four pillars together. None is negotiable.

1. **Determinism precedes machine learning.** A pre-approved exact answer always beats a regenerated LLM answer. The system tries cheaper, more deterministic resolution paths first.
2. **Every output is explainable.** Every translated segment carries a structured *provenance object*: which rules fired, which TM rows matched, which determinism-library entry was reused, which model/prompt produced novel content, which signals fed the confidence score. This is what a regulator will inspect.
3. **Tenant isolation is structural, not procedural.** Every persisted artefact (rule, TM row, cache entry, calibration model, formula library entry, TLF cell-type classifier) carries `tenant_id` and is enforced via PostgreSQL row-level security.
4. **Hard constraints fail loudly.** Glossary locks, regulator-mandated phrases, formula and number preservation, EDQM standard terms — these are validated post-translation; failures block the job, do not warn-and-continue.
5. **Human approval is the only path to trust.** No artefact (rule, library entry, calibration model update) reaches `ACTIVE` without a signed human review. Confidence thresholds may *gate* what is sent for review, but they never replace the signature.
6. **Format is content.** Bold marks warnings. Subscripts carry units. Decimal alignment carries clinical meaning. Format-fidelity defects are content defects and are scored on the same defect taxonomy.

---

## 3. Pillar 1 — Knowledge, Rules, Black Books, Domain Context

### 3.1 Current state

The codebase already has the bones:

- `app/models/models.py` — `TranslationRule` model.
- `app/services/learning_service.py` — extracts candidate rules from reviewer corrections; auto-promotes at confidence ≥ 0.90.
- `app/api/knowledge.py` — knowledge / glossary REST stubs.
- `verify_black_book.py` — verification script in repo root.
- `app/core/regulatory_profiles.py`, `profile_resolver.py`, `profile_enums.py`, `policy_definitions.py` — regulator-level profile scaffolding.
- `Glossary` and `GlossaryTerm` models and CRUD.

Three blocking problems:

1. **No tenant scope.** `TranslationRule` has no `organization_id` foreign key. Rule leakage between tenants is one bug away.
2. **Auto-promotion without signed review.** Rules at confidence ≥ 0.90 reach ACTIVE without human approval. Wrong rules propagate silently across all future jobs.
3. **Flat namespace.** All rules live in one bucket. There is no notion of regulator-level vs industry-level vs tenant-level vs brand-level vs study-level vs reviewer-level rules, and no precedence when they conflict.

### 3.2 Target architecture

A six-layer rule taxonomy with explicit precedence and provenance.

| Layer | Purpose | Examples | Precedence (lowest = base) |
| --- | --- | --- | --- |
| **L0 Regulator** | Mandatory regulator-issued phrasing and locked terms | EMA QRD section titles; EDQM Standard Terms; ICH-harmonised wordings | 0 (lowest) |
| **L1 Industry** | Pharma-wide conventions where regulators are silent | Standard adverse-event phrasings; common abbreviations (BID, TID, PRN) | 1 |
| **L2 Tenant** | Customer house style | "Use sentence case in section headings"; "spell out drug class on first occurrence" | 2 |
| **L3 Brand** | Per-product / per-compound rules | "Refer to ABC-123 as 'XYZ' in marketing material in DE-DE" | 3 |
| **L4 Study** | Per-protocol or per-submission rules | "In study AT-2026-001, refer to placebo as 'control'" | 4 |
| **L5 Reviewer** | Documented preferences of a specific reviewer | "Reviewer X prefers 'subject' over 'patient' in DE-DE" | 5 (highest) |

A higher-precedence rule overrides a lower-precedence rule when they conflict on the same source span. Conflicts within a layer are resolved by an explicit `priority` integer; ties are flagged for human resolution and logged.

### 3.3 Data model

```sql
CREATE TABLE translation_rule (
  id              UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL REFERENCES organisation(id),
  layer           TEXT NOT NULL CHECK (layer IN ('L0','L1','L2','L3','L4','L5')),
  scope_kind      TEXT NOT NULL CHECK (scope_kind IN
                   ('regulator','industry','tenant','brand','study','reviewer')),
  scope_id        TEXT,                       -- e.g. brand_id, study_id, reviewer_id
  language_pair   TEXT NOT NULL,              -- 'en-GB:de-DE'
  content_type    TEXT,                       -- 'smpc','pil','csr','tlf', null=any
  source_pattern  JSONB NOT NULL,             -- {kind: 'literal'|'regex'|'embedding', value: ...}
  target_pattern  JSONB NOT NULL,             -- structured target representation
  condition       JSONB,                      -- additional context filters
  priority        INT NOT NULL DEFAULT 0,
  rationale       TEXT,                       -- human-readable why
  status          TEXT NOT NULL CHECK (status IN
                   ('proposed','reviewed','approved','active','deprecated','archived')),
  version         INT NOT NULL,
  supersedes_id   UUID REFERENCES translation_rule(id),
  created_by      UUID NOT NULL,
  reviewed_by     UUID,
  approved_by     UUID,
  approved_at     TIMESTAMPTZ,
  effective_from  TIMESTAMPTZ NOT NULL,
  effective_to    TIMESTAMPTZ,
  signature       BYTEA,                      -- detached Ed25519 signature
  rule_hash       BYTEA NOT NULL,             -- canonical hash for JobConfigSnapshot
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON translation_rule (tenant_id, layer, language_pair, status);
ALTER TABLE translation_rule ENABLE ROW LEVEL SECURITY;
```

A *rule set* is the materialised view of all active rules applicable to a job, keyed on `(tenant_id, language_pair, content_type, brand_id, study_id, reviewer_id)`. Its hash is recorded in the JobConfigSnapshot so the exact rule set used for any historical job can be reconstructed.

### 3.4 Domain context — the knowledge graph

Rules are not enough; a translation agent needs entities. We introduce a tenant-scoped knowledge graph holding pharma-domain entities and their cross-links.

| Entity | Sources | Used for |
| --- | --- | --- |
| Drug / compound | INN, ATC, MeSH, EDQM, IDMP MPID/PCID | Locked terminology; do-not-translate; brand-vs-generic resolution |
| Indication | MedDRA preferred terms, ICD-10, SNOMED CT | Glossary lookup; content-type prior for confidence model |
| Population | Paediatric, geriatric, renal-impaired, hepatic-impaired (ICH E14) | Rule applicability |
| Adverse event | MedDRA LLT/PT/HLT/HLGT/SOC | TLF cell-content rules; lock for safety language |
| Study / protocol | Protocol number, sponsor, design (RCT, single-arm, observational) | Study-level rules |
| Regulatory profile | EMA, FDA, MHRA, PMDA, NMPA, EDQM | Regulator-mandated rules |
| Glossary term | Tenant glossary | Direct termbase lookup |
| Document type | SmPC, PIL, IFU, CSR, ICF, CTD module, label | Content-type prior |

The knowledge graph is loaded at `compile_constraints` time, sliced by document context, and emitted as both *soft* constraints (preferred phrasing) and *hard* constraints (locked terms) into the LLM prompt and the post-translation quality gate.

### 3.5 Lifecycle

```
proposed → reviewed → approved → active → deprecated → archived
```

* Candidate rules are generated by `learning_service.py` from reviewer corrections, by direct authoring in the rule console, by importing TBX glossaries, or by pulling regulator-issued updates (EDQM Standard Terms releases, EMA QRD template updates).
* Candidate rules enter `proposed` with the contributing evidence attached.
* A reviewer with the `Curator` role moves rules to `reviewed`.
* An approver with the `RuleApprover` role (a new role) moves rules to `approved` with an Ed25519 signature.
* The release pipeline materialises approved rules into `active` at the next rule-set publication; published rule sets are immutable and signed.
* Deprecation requires an approver signature; deprecated rules continue to apply to historical jobs but not to new ones.
* Archive is permanent; archived rules never fire but remain for audit.

The auto-approval at confidence ≥ 0.90 documented in `learning_service.py` is removed. The system *suggests* with confidence, but does not promote without a signature.

### 3.6 Integration with existing components

* `compile_constraints` LangGraph node consumes the materialised rule set, the knowledge-graph slice, the glossary, and the TM matches; emits a single `ConstraintPack` into the translate node.
* `translate` node uses the pack to render the LLM prompt with hard locks as inviolable constraints and soft rules as priority hints.
* `quality_gate` enforces hard locks post-translation; failures register as Critical defects; the refinement loop uses the failed locks as feedback.
* `audit_service` records the rule-set hash, the rules that fired and the rules that were overridden, per segment.

### 3.7 Pillar 1 validation

* **Unit:** rule conflict resolver returns the correct precedence in 100% of curated conflict cases.
* **Property:** for any rule R1 and a strictly higher-precedence rule R2 on the same source span, R2 wins.
* **Behavioural:** golden corpus runs with and without each rule layer enabled; expected differences asserted.
* **Tenant isolation:** every test in the multi-tenant suite asserts a tenant cannot see another tenant's rules through any surface.
* **Lifecycle:** auto-promotion is forbidden at the model layer; an integration test attempts to promote without a signature and expects 403.
* **Signature:** rule-set artefacts are verified by Ed25519 in CI; tampered artefacts fail verification.

### 3.8 Pillar 1 phased delivery

* **Phase 1 (0–90 days):** add `tenant_id` FK and RLS; remove auto-promotion; introduce L0–L5 layering and the conflict resolver; rule-set hash in JobConfigSnapshot; Ed25519 signing of approved rule sets; basic rule console (CRUD with approval workflow). Import EDQM Standard Terms as an L0 rule pack.
* **Phase 2 (3–6 months):** knowledge-graph schema; ingestion of MedDRA, MeSH, ATC, IDMP MPID; entity-aware constraint compilation; rule import from TBX; rule-impact telemetry (usage, override rate).
* **Phase 3 (6–12 months):** ML-assisted rule discovery from reviewer-edit history (offline pipeline only — humans still sign promotions); per-brand and per-study rule packs as a customer-facing artefact; partner-built regulator-pack marketplace.

---

## 4. Pillar 2 — Phrase Memory, Determinism, Token-Cost Optimisation

### 4.1 Current state

- `TranslationMemory` model with pgvector embedding column.
- `find_exact_matches_batch` in `app/services/db_service.py` for exact-match TM lookup.
- No fuzzy-match retrieval, no semantic-RAG retrieval surfaced into the prompt, no LLM-bypass cascade, no determinism library, no segment-result cache, no constraint-pack cache.

The result: every segment, even if it is a verbatim re-use of a phrase translated 200 times before, currently round-trips through an LLM. Cost is unbounded; outputs are non-deterministic; identical inputs produce drifted outputs.

### 4.2 Four-tier resolution cascade

Every segment passes through the cascade before any LLM call:

```
Tier 1 — Determinism Library (signed, byte-stable boilerplate)
       │
       │ no hit
       ▼
Tier 2 — Exact-match TM (≥99% similarity, matching context)
       │
       │ no hit
       ▼
Tier 3 — Fuzzy-match TM (85–99%, used as RAG context)
       │
       │ no hit
       ▼
Tier 4 — LLM with full Constraint Pack (rules, glossary, knowledge graph)
```

Tier 1 and Tier 2 hits **bypass the LLM entirely**. Tier 3 reduces LLM token cost (the matched fragment is the context, the prompt asks for a constrained adaptation). Tier 4 is the fallback.

### 4.3 Determinism Library

Pre-approved, signed, byte-stable translations of regulator boilerplate. Examples:

* EMA QRD section titles and standard headings ("Pharmaceutical form", "Therapeutic indications", "Posology and method of administration") in every supported target language.
* EDQM Standard Terms (dosage forms, routes of administration, units of presentation, container types).
* ICH-harmonised wordings (consent boilerplate; standard adverse-event severity labels).
* Statistical-notation phrases used in TLFs ("mean (SD)", "median [Q1, Q3]", "n (%)", "95% CI").
* Common pharmacovigilance phrases ("If you get any side effects, talk to your doctor or pharmacist.").

```sql
CREATE TABLE determinism_library_entry (
  id                UUID PRIMARY KEY,
  tenant_id         UUID,                         -- nullable for global L0 entries
  scope_layer       TEXT NOT NULL,                -- 'L0','L1','L2','L3'
  language_pair     TEXT NOT NULL,
  content_type      TEXT,                         -- 'smpc','tlf', null = any
  source_canonical  TEXT NOT NULL,
  source_normalised TEXT NOT NULL,                -- collapsed whitespace, NFC, lower
  target_canonical  TEXT NOT NULL,
  variant_pattern   JSONB,                        -- e.g. case-insensitive, punctuation-insensitive
  signed_by         UUID NOT NULL,
  signed_at         TIMESTAMPTZ NOT NULL,
  effective_from    TIMESTAMPTZ NOT NULL,
  effective_to      TIMESTAMPTZ,
  signature         BYTEA NOT NULL,
  source_hash       BYTEA NOT NULL,               -- sha256(source_normalised)
  status            TEXT NOT NULL,
  version           INT NOT NULL
);
CREATE UNIQUE INDEX ON determinism_library_entry
  (tenant_id, language_pair, content_type, source_hash, status)
  WHERE status = 'active';
```

Lookup is a constant-time hash probe on `source_hash` after normalisation. A hit returns the target byte-for-byte; the segment is annotated with the determinism-library entry id and that entry's signature is recorded in the segment's provenance.

### 4.4 TM extensions

* Add `context_hash` (preceding + following segment hash) to disambiguate context-sensitive matches.
* Add `last_used_at` and `hit_count` for governance and pruning.
* Add `fuzzy_index_version` so we can rebuild fuzzy indexes without breaking previous matches.
* Replace `find_exact_matches_batch` with a tiered retriever that returns the highest-tier match per segment (Determinism > Exact TM > Fuzzy TM > none).

### 4.5 Caches

Three caches sit on the LLM call path:

| Cache | Key | Effect |
| --- | --- | --- |
| Segment-result cache | `(tenant_id, language_pair, source_segment_hash, glossary_hash, rule_set_hash, profile_hash, prompt_version, model)` | Identical inputs and constraints → identical output, no LLM call |
| Constraint-pack cache | `(tenant_id, doc_id, profile_id, glossary_hash, rule_set_hash)` | Avoid recompiling constraints for repeat runs of the same job |
| Reasoning cache | `(segment_hash, prompt_kind, model)` | "Explain this edit", round-trip explanation, etc. |

Caches are tenant-scoped, TTL-bounded (default 30 days; configurable), and invalidated automatically on glossary, rule-set or profile change. Cache hit rates are reported per tenant per content type.

### 4.6 Token-cost governance

* **Pre-translation deduplication.** Identical segments within a job are translated once and propagated; the result is also written to TM and the segment-result cache.
* **Bucketing by language pair.** Batched LLM calls are constructed per language pair.
* **Model routing.** A small/cheap model (e.g. Claude Haiku, GPT-4.1-mini, DeepL) handles segments with high TM/Determinism support. A frontier model handles novel content. Routing is rule-based, observable and overridable per tenant.
* **Per-job cost ceiling.** Already noted in the headless spec; surfaced as a structured pause-and-escalate event when reached.
* **Per-tenant monthly budget.** Webhook fires at 80% and 100%; UI displays projected month-end spend.
* **Token telemetry.** Prompt tokens, completion tokens, cached-prompt tokens (where the LLM provider supports prompt caching), per segment per node per model.

### 4.7 Determinism guarantees

For a given `(source_segment_hash, glossary_hash, rule_set_hash, profile_hash, prompt_version, model, temperature=0)` the engine produces a byte-identical translation. This is achieved by:

* Tier 1 and Tier 2 hits are byte-stable by construction.
* Tier 4 calls fix `temperature = 0` and use providers that support deterministic decoding (OpenAI seed parameter, Anthropic deterministic mode where available); the segment-result cache absorbs the residual variance.
* The full LLM response (not just the extracted target) is stored alongside the segment; replays compare byte-for-byte.

A *Determinism KPI* is a customer-facing metric: percentage of segments resolved without an LLM call, plotted over time.

### 4.8 Pillar 2 validation

* **Determinism property:** for any segment translated twice with identical inputs, outputs are byte-identical.
* **Cost regression:** golden corpus translation cost is monitored; any release that increases cost > 10% without a feature justification fails CI.
* **Cache correctness:** changing glossary, rule set or profile hash invalidates the segment-result cache; integration tests verify no stale hits.
* **TM-context correctness:** segments with the same source but different surrounding context produce the right TM behaviour (the wrong-context match must not be returned).
* **Tenant isolation:** no cache key collision across tenants is possible; integration tests assert.
* **Determinism Library signature verification:** every Tier-1 hit verifies the entry's signature; tampered entries cause the lookup to fall through to Tier 2 with an audit event.

### 4.9 Pillar 2 phased delivery

* **Phase 1:** Determinism Library schema and lookup; Tier-1 / Tier-2 cascade; segment-result cache; pre-translation dedup; per-job cost ceiling enforcement; determinism KPI reporting. Seed L0 entries from EMA QRD and EDQM Standard Terms.
* **Phase 2:** Fuzzy TM as RAG context; constraint-pack cache; reasoning cache; model routing rules engine; per-tenant budget controls.
* **Phase 3:** Adaptive cache eviction by hit-rate × age; cross-tenant *anonymised* boilerplate library (with explicit tenant opt-in); offline pipeline that promotes high-hit-rate fuzzy matches into the Determinism Library after human signing.

---

## 5. Pillar 3 — Confidence Scoring, Check-and-Recheck, Human Escalation

### 5.1 Current state

- `app/services/confidence_service.py` — present but shallow.
- `app/core/scoring_config.py` — scoring weights; static.
- `app/core/language_calibration.py` — pair-specific difficulty multipliers (en→ja harder than en→fr).
- `app/services/quality_gate.py` — defect taxonomy and severity scoring.
- No multi-signal composition. No back-translation in production. No reviewer-feedback calibration. No tiered escalation routing.

### 5.2 Eight signal model

A high-class confidence score composes at least eight signals into a single calibrated scalar. Each signal is recorded on the segment for audit; the composite is what triggers gating.

| # | Signal | Source | Notes |
| --- | --- | --- | --- |
| 1 | LLM self-reported logprobs | OpenAI / Anthropic logprobs | Where provider supports; null otherwise |
| 2 | Round-trip semantic similarity | Back-translate target → source; compute COMET-22 + BERTScore + chrF | Uses a *different* model from the forward pass to avoid self-confirmation |
| 3 | TM match score | TM retriever | Higher score = higher confidence |
| 4 | Glossary adherence | Quality-gate glossary check | Fraction of expected terms preserved in target |
| 5 | Quality-gate severity-weighted defect rate | Quality-gate output | Critical = 1.0, Major = 0.4, Minor = 0.1; lower is better |
| 6 | Language-pair calibration prior | `language_calibration.py` | Static prior per pair |
| 7 | Content-type prior | Profile + classifier | SmPC indication line ≠ marketing footer |
| 8 | Reviewer-agreement history | Per reviewer × content-type × language-pair | "How often does this reviewer accept first-pass output of this kind without edit" |

### 5.3 Calibration

Composition is not a hand-tuned sum. The composite is a *calibrated probability* — "the probability that this segment will be accepted by a human reviewer without edit" — produced by a calibrated meta-model.

* **Ground truth:** every reviewer action emits a labelled training example: source + target + signals → `accepted_without_edit` (boolean) + edit-distance.
* **Model:** isotonic regression as a baseline; gradient-boosted trees per `(tenant, language_pair, content_type)` slice once enough data accumulates.
* **Versioning:** the calibration model is an MLflow-tracked artefact with a hash; the active version is recorded in the JobConfigSnapshot. Replays use the historical model.
* **Refresh:** nightly retraining where slice has sufficient data; otherwise weekly; otherwise quarterly.
* **Cold start:** new tenants start on a global model; per-tenant slice activates after a configurable evidence threshold (e.g. 5,000 reviewed segments).

### 5.4 Tiered thresholds

| Composite | Disposition | Required reviewer action |
| --- | --- | --- |
| ≥ 0.95 | Auto-approve | None; segment goes to `APPROVED` with provenance |
| 0.85 – 0.95 | Light review | Spot-check; reviewer sees only sampled subset (configurable %) |
| 0.70 – 0.85 | Full review | Reviewer must affirm or edit |
| < 0.70 | Dual review | Two independent reviewers must agree |

Thresholds are **per tenant × content type × language pair**. Default values are conservative; customers can tighten but not loosen below contractual minima for regulatory content (e.g. SmPC content must be at least Full review regardless of confidence).

### 5.5 Check-and-recheck loop

The agent regenerates *whenever signal disagreement exceeds a threshold* — that is, when the model is "confident" but other signals disagree. Concretely:

```
if max(signal) - min(signal) > 0.30 OR
   (logprobs >= 0.90 AND round_trip_score < 0.70):
    regenerate with alternate model
    compare new translation to original via TER + COMET
    if delta > threshold → escalate to human
    if delta within threshold → record concord, take higher-confidence variant
```

The regenerate step uses a *different* model and a *different* prompt template to avoid self-confirmation. Both translations are recorded in the segment audit trail with their signal vectors.

### 5.6 Critical-defect overrides

Some defects bypass confidence entirely and trigger immediate escalation regardless of score:

- Negation flips (source has a negator that target lacks, or vice versa).
- Number changes (any numeric value in source missing from target, or vice versa).
- Unit changes (mg → g, mL → L, %→ no %).
- Drug-name changes (entity recognised in source not present in target).
- Dose-frequency changes (BID → TID, etc.).
- Polarity changes in safety language (do/do-not, must/must-not).

These are detected by deterministic checkers running in `quality_gate`; a single hit forces the segment into the dual-review tier with a paged notification to the on-call medical reviewer.

### 5.7 Escalation routing

Escalations route to a *reviewer pool* with a skill profile — language pair, content type, regulatory domain, certification. SLAs are tier-specific: dual review of safety-critical content has a same-business-day SLA; light review of marketing footer has a next-business-week SLA.

All escalation events land on the audit ledger with the signal vector, the chosen reviewer, and the SLA target. Late-SLA escalations re-route automatically and emit a webhook event.

### 5.8 Pillar 3 validation

* **Calibration validation:** Brier score and reliability diagrams per slice; CI fails if calibration error > target.
* **Critical-defect detection:** zero misses on a curated set of 500 negation, number, unit, drug-name, dose-frequency, and polarity test cases.
* **Threshold property:** for any segment scored x, the disposition matches the configured tier exactly.
* **Check-and-recheck:** synthetic test where logprobs are forced high but round-trip is forced low; system must regenerate with the alternate model and escalate when delta exceeds threshold.
* **Reviewer-agreement decay:** if a reviewer's behaviour shifts (suddenly edits more), the calibration model must reflect this within N nights of retraining.
* **Audit:** every escalation has a full signal vector and an SLA target; missing fields fail CI.

### 5.9 Pillar 3 phased delivery

* **Phase 1:** signal capture (1, 3, 4, 5, 6, 7) end-to-end; back-translation infrastructure (signal 2) on a sample basis; reviewer-action capture (signal 8 inputs); a global calibration model; tiered thresholds; critical-defect overrides; escalation routing with manual reviewer assignment.
* **Phase 2:** per-slice calibration models; check-and-recheck loop; SLA-driven auto-routing with reviewer skill profiles; calibration KPIs as a customer-facing report.
* **Phase 3:** per-reviewer fine-tuning of calibration; explanations of why a segment was escalated (feature attribution); reviewer-load balancing across regions and time zones.

---

## 6. Pillar 4 — Format Fidelity (with Formulas and TLFs)

This pillar is the most acutely competitive. Pharma documents are highly formatted; format is content. Loss of format is loss of meaning.

### 6.1 Current state vs benchmarks

| Vendor class | Approach | Strength |
| --- | --- | --- |
| TMS (Phrase, Smartling, XTM, memoQ, Trados) | XLIFF segmentation with inline tag preservation as `<g>`, `<ph>`, `<pc>` | Strong |
| Document MT (DeepL Document, Google Document Translation, AWS Translate batch) | Native ingestion of .docx / .pdf / .pptx / .xlsx with style preservation | Strong; DeepL widely best in class |
| Pharma LSPs | Trados / memoQ pipelines plus desktop-publishing teams for PIL leaflets and IFU booklets | Very strong; format is table-stakes plus paid DTP service |
| Agentic (Smartcat, Lilt) | XLIFF-style inline tag preservation; native file ingestion; in-context preview | Strong |
| **Transmax today** | Plaintext API; period-split segmentation; pypdf basic ingestion; export stub; no inline-tag preservation; no XLIFF; no DTP | **Below virtually every benchmark** |

Closing this gap is non-optional. No regulated customer will accept a SmPC translation that lost the bold on a contraindication or the superscript on m².

### 6.2 Canonical internal format

All ingested documents are converted to **XLIFF 2.1** as the internal canonical, augmented with a transmax-specific metadata namespace (`xmlns:tm="urn:transmax:1.0"`) carrying:

* `tm:cell-type` for table cells (numeric, label, header, footnote, identifier).
* `tm:formula-kind` for formula objects (math, chemical, statistical).
* `tm:tlf-role` for TLF metadata (table number, population, source dataset).
* `tm:lock` for hard-locked spans (numbers, units, drug names, IDs, footnote markers).
* `tm:provenance` for the source-document anchor (page, paragraph, run).

Every translatable unit in the source becomes an XLIFF `<unit>` with its inline formatting captured as paired open/close placeholders (`<pc>`) or self-closing placeholders (`<ph>`). Translators (human or agent) cannot remove or reorder placeholders without an explicit override.

### 6.3 Ingestion stack

| Source format | Library / approach | Notes |
| --- | --- | --- |
| DOCX | python-docx + custom XML walker | Tracked changes preserved; comments preserved; headers/footers handled; styles map applied |
| XLSX | openpyxl | Cell-level segmentation with cell-type classification; formula cells locked |
| PPTX | python-pptx | Slide order; speaker notes; in-shape text |
| PDF (digital) | pdfplumber + pypdfium2 | Layout extraction; table detection; reading-order recovery |
| PDF (scanned) | Tesseract / AWS Textract / Azure Document Intelligence | OCR fallback with confidence metric; below threshold escalates to human |
| HTML / XML | lxml + custom selectors | Schema-aware ingestion |
| XLIFF 1.2 / 2.1 | direct round-trip | Metadata preserved |
| TMX | direct ingestion | TM seeding |
| IDML (InDesign) | IDML parser | Used for PIL leaflet layouts; preserves layers and threaded frames |
| Markdown / reStructuredText | mistune / docutils | Used for technical documents |
| RTF | striprtf + custom RTF walker | Primary TLF source format |
| MathML / OOML / LaTeX | dedicated math parser (e.g. mathml2omml, mathjax-node) | Formula-aware ingestion |

### 6.4 Export stack

Round-trip from XLIFF back to the original format is the default. Additional exports:

* **PDF/A-1b** with embedded fonts for archival (regulator-acceptable long-term format).
* **Signed PDF** with reviewer e-signature panel and audit-trail appendix.
* **XLIFF 2.1** for downstream TMS interoperability.
* **TMX** for translation-memory portability.
* **eCTD-ready** package: PDF/A bookmarked per Module 1 / 2 / 3 expectations; XML metadata aligned to ICH eCTD v4.0 once available.

### 6.5 Inline format preservation

Every inline format is captured as an opaque numbered placeholder. The post-translation QA gate enforces preservation:

| Inline format | Source representation | Validation |
| --- | --- | --- |
| Bold | `<pc>` open/close | Span count match; nested-span integrity |
| Italic | `<pc>` open/close | Span count match |
| Underline | `<pc>` open/close | Span count match |
| Strike-through | `<pc>` open/close | Span count match (rare in pharma; flagged when present) |
| Superscript | `<pc>` open/close | Span count match; symbol table preservation |
| Subscript | `<pc>` open/close | Span count match; symbol table preservation |
| Hyperlinks | `<pc>` with href attr | URL preserved byte-for-byte; link text translated |
| Footnote refs | `<ph>` with anchor id | Anchor preserved; markers (a, b, †, ‡, *) locked |
| Cross-references | `<ph>` with target id | Target id preserved; visible label translated |
| Symbols (Greek, math, IPA, etc.) | Unicode literal | NFC normalisation; allow-list enforced |
| Images / figures | `<ph>` with anchor id | Anchor preserved; alt-text translated |
| Page breaks (structural) | `<ph type="page-break"/>` | Preserved when structurally meaningful |

The QA gate produces a **format-fidelity score** per segment and per document; defects are added to the standard defect taxonomy with severity Critical (lost lock), Major (lost span) or Minor (whitespace drift).

### 6.6 Formulas

Pharma content contains formulas that must round-trip exactly.

#### 6.6.1 Formula taxonomy

| Class | Examples |
| --- | --- |
| Pharmacokinetic | Cₘₐₓ, AUC, t½, CL, V_d, k_el |
| Dosing | mg/kg, mg/m² (BSA-based), AUC-targeted (Calvert) |
| Statistical | RR, OR, HR, NNT, 95% CI, p, Cohen's d, Kaplan-Meier S(t) |
| Chemical | C₂H₅OH, NaCl, H₂O, ATP, mAb |
| Mathematical (PK/PD models) | dC/dt = -k·C; one-compartment, two-compartment, Michaelis–Menten |

#### 6.6.2 Approach

1. **Detect.** Formula objects in DOCX OOML, HTML MathML or LaTeX are detected at ingestion and lifted into a dedicated XLIFF `<unit>` with `tm:formula-kind` set.
2. **Decompose.** Each formula is parsed into a structural tree: variables, operators, numerals, subscripts, superscripts, fractions, integrals, summations, units.
3. **Lock.** Operators, numerals, units (when canonical), Greek letters, structural markers are *hard-locked* — they cannot be modified by any translation step.
4. **Translate (rarely).** Variable *labels* in surrounding prose may be translated ("body surface area" → "Körperoberfläche"); the variable *symbol* (BSA) is never translated.
5. **Re-emit.** The structural tree is re-emitted in the original format on export (OOML for Word, MathML for HTML, LaTeX for technical content).
6. **Image-of-formula fallback.** Where a formula appears as a rasterised image (scanned PDF), Mathpix Snip or equivalent OCR is used; below confidence threshold, the segment is escalated and the formula is preserved as image with an OCR'd alt-text.

#### 6.6.3 Specific rules (L0 layer in Pillar 1)

* Numbers are never translated.
* Units in canonical form are never translated (mg, mL, mcg, IU, mol/L, mmHg, mg/m², °C). Local long-form variants ("milligrammes") are forbidden in regulated content.
* Variable symbols (Cmax, AUC, t½) never translated.
* Greek letters preserved Unicode-literally (α, β, γ, δ, μ, λ, σ).
* Inequality and equality preserved exactly (≤, ≥, ±, ≠, ≈).
* Decimal separator follows target-locale convention only when explicitly authorised; default is to preserve source convention to avoid silent corruption.

### 6.7 TLFs — Tables, Listings, Figures

#### 6.7.1 What TLFs are

Standard outputs of clinical-trial data analysis, included in the Clinical Study Report and supporting submissions:

* **Tables (T)** — statistical summaries (demographics, exposure, efficacy endpoints, safety summaries).
* **Listings (L)** — subject-level line listings (one row per subject per event).
* **Figures (F)** — graphical outputs (forest plots, Kaplan–Meier curves, box plots, waterfall plots).

Source format is typically RTF generated from SAS PROC REPORT, R `gt` / `flextable`, or Python `great_tables`; sometimes embedded in CSR Word documents; sometimes delivered as PDF.

#### 6.7.2 What is hard about TLFs

* **Decimal alignment** in numeric columns is part of the meaning (3.14 vs 3.140 vs 3.1).
* **Footnote anchors** (a, b, c, †, ‡, *, **) must remain anchored to specific cells; losing the anchor loses the footnote's meaning.
* **Page-spanning tables** repeat headers on each page; the header must be translated once and propagated.
* **Statistical notation** ("n (%)", "mean (SD)", "median [Q1, Q3]", "95% CI") is conventional and should come from the Determinism Library.
* **Population / denominator notes** ("Safety Population", "Per-Protocol Set", "ITT Population") have canonical translations and must not be paraphrased.
* **TLF metadata header** (Table 14.2.1.1, Population: Safety Population, Source: ADSL.SAS, Date: 12MAR2026) is partly never-translated (table number, dataset name, date) and partly canonically translated (Population labels).
* **Cross-references** between tables and listings (Table 14.2.1.1, Listing 16.2.6.1) must be preserved exactly.
* **Some text is translated, much is not.** Treatment arm labels, parameter names, footnote text → translated. Subject IDs, lab values, date-time stamps, statistical numbers → never translated.

#### 6.7.3 Approach

1. **Cell-level segmentation.** Each table cell is its own XLIFF unit. The unit carries a `tm:cell-type` attribute classifying the cell:

   | `cell-type` | Translatable? | Validation |
   | --- | --- | --- |
   | `header` | Yes | Header propagation across page repetitions |
   | `row-label` | Yes | Glossary / Determinism lookup mandatory |
   | `column-label` | Yes | Glossary / Determinism lookup mandatory |
   | `numeric` | No | Locked; bypass LLM entirely |
   | `numeric-with-marker` | Markers translatable; numbers locked | E.g. "3.45*" — number locked, marker preserved |
   | `statistical-notation` | Yes (canonical) | Determinism Library mandatory |
   | `categorical` | Yes | Glossary lookup; e.g. "Yes / No / Missing" |
   | `subject-id` | No | Locked |
   | `date-time` | No (default) | Locked; ISO 8601 enforced; locale conversion only with explicit per-tenant rule |
   | `footnote-text` | Yes | Footnote-anchor preservation |
   | `metadata` | Mixed | Field-by-field; table number locked, population label translated |

2. **Cell-type classifier.** A deterministic rule-based classifier (column position + content regex + header label) seeded on a corpus of CDISC ADaM standard tables; agentic fallback for non-standard tables.

3. **Decimal alignment preservation.** A post-translation cell-formatting layer asserts:
   * For each numeric column, all cells share the same decimal precision.
   * Trailing zeros are preserved (3.140 ≠ 3.14 in clinical reporting).
   * Sign and parenthesis conventions for negative numbers are preserved.

4. **Footnote-anchor preservation.** Footnote markers in numeric cells are inline `<ph>` placeholders with anchor ids; the QA gate asserts every source anchor has exactly one target anchor with matching id, and every target anchor has corresponding footnote text.

5. **Header propagation.** Repeated headers are translated once per unique header signature; identical signatures across pages reuse the same target.

6. **Statistical notation library.** The Determinism Library carries canonical translations for the statistical-notation phrases listed above per language pair. Cells classified as `statistical-notation` MUST hit Tier 1; a miss is a Critical defect.

7. **Cross-reference preservation.** Table and listing identifiers ("Table 14.2.1.1", "Listing 16.2.6.1", "Figure 2") are locked; the visible label ("Table") is translated, the identifier is not.

8. **Figures.** Figures are rasterised or vector-graphic outputs. The text inside them (axis labels, legend, title, annotations) is extracted via OCR (raster) or SVG-text walking (vector) and translated as a separate XLIFF document; on export the figure is re-rendered with the translated labels. For raster-only figures with no source SVG, the translated labels are emitted as a side-by-side bilingual caption.

9. **TLF QA gate.** A specialised quality-gate sub-checker runs only on TLF documents:
   * Cell count matches between source and target tables.
   * Cell-type classifications match.
   * Numeric cells are byte-identical between source and target.
   * Decimal precision is preserved per column.
   * Footnote-anchor counts match per cell and per table.
   * Statistical-notation cells hit Determinism Library.
   * Cross-references are preserved exactly.
   * Header propagation is consistent.

#### 6.7.4 RTF specifics

RTF is the dominant TLF source format. The RTF parser must:

* Preserve TRowD / cellx column-width definitions.
* Preserve rowspan / colspan via `\clmgf` / `\clmrg`.
* Preserve borders, shading, alignment.
* Preserve fonts and font sizes (TLFs are often Courier or Arial Narrow at small sizes for fit).
* Preserve page setup (orientation, margins).

Round-trip through RTF on export must be byte-stable for non-translated cells and produce a structurally identical document.

### 6.8 Locale-aware handling

Some format elements vary by locale and must be configurable per tenant rule:

* Decimal separator (US: 1,000.5; EU: 1.000,5).
* Date format (US: 03/12/2026; EU: 12/03/2026; ISO: 2026-03-12).
* Time format (12-hour vs 24-hour).
* Quotation marks (English: "…"; German: „…"; French: « … »).
* List punctuation (German typically uses comma after enumerator).
* Number grouping (thousands grouping by 3 in most locales; by 4 in some Asian locales).

Default is preservation of source convention to avoid silent corruption; tenant rule overrides.

### 6.9 Pillar 4 validation

The format-fidelity validation programme is the densest of the four pillars.

* **Round-trip identity:** untranslated documents pass through ingestion → XLIFF → export and emerge byte-identical (where format permits) or structurally identical (where round-trip is lossy by definition, e.g. PDF → PDF). Tested on a corpus of 50+ pharma documents.
* **Inline-tag conservation:** for every translated segment, source placeholder count equals target placeholder count, ids match, ordering matches (where structurally significant).
* **Format-fidelity QA gate:** every test in the golden corpus produces a format-fidelity score; regressions > 1% fail CI.
* **Formula round-trip:** OOML / MathML / LaTeX formulas survive ingestion → translation (where applicable) → export with byte-stable structure for locked elements.
* **TLF round-trip:** RTF TLFs round-trip with byte-identical numeric content, preserved decimal precision, preserved footnote anchoring, preserved cross-references.
* **Cell-type classifier accuracy:** ≥ 99% on a curated CDISC-adjacent corpus.
* **OCR confidence gating:** scanned PDFs below configurable confidence threshold are escalated, not silently translated.
* **Locale handling:** decimal-separator, date-format and quotation-mark tests assert no silent locale corruption.
* **DTP regression:** language-expansion tests (German +30%, Japanese line-break behaviour, Arabic RTL flip) emit valid layouts without overlap.

### 6.10 Pillar 4 phased delivery

* **Phase 1 (0–90 days):** XLIFF 2.1 canonical layer; native DOCX ingestion with tracked changes; native XLSX and PPTX; basic PDF (digital) with table extraction; HTML/XML; XLIFF/TMX round-trip; placeholder-count QA; PDF/A-1b export. Sufficient to handle 80% of inputs.
* **Phase 2 (3–6 months):** RTF ingestion and export; cell-level TLF segmentation with classifier; statistical-notation Determinism entries seeded for top six language pairs; OOML / MathML formula handling; OCR fallback with confidence gating; locale-aware handling; DTP reflow with target-language line-break and font handling; IDML support for PIL leaflets.
* **Phase 3 (6–12 months):** Figures pipeline with SVG-text walking and label re-rendering; LaTeX support for protocols and SAPs; eCTD v4.0 export; partner-built ingestion plug-ins (e.g. Madcap Flare, Adobe FrameMaker).

### 6.11 Where this puts transmax vs benchmarks

| Capability | Today | Phase 1 end | Phase 2 end | Phase 3 end | Best-in-class benchmark |
| --- | --- | --- | --- | --- | --- |
| Inline tag preservation | None | Match TMS leaders | Match | Match | Phrase, XTM, memoQ |
| Native DOCX with tracked changes | Weak | Match | Match | Match | DeepL Document, Phrase |
| TLF (RTF) handling | None | None | Match LSPs | Beat LSPs (automated, no DTP) | Pharma LSPs (human DTP) |
| Formula handling (OOML, MathML, LaTeX) | None | None | Match | Beat (regulator-grade lock) | Limited; mostly LSP-manual today |
| OCR for scanned pharma PDFs | None | Basic | Match | Match | DeepL, AWS Translate |
| eCTD-ready export | None | None | Partial | Match | TransPerfect (eCTD specialist), XTM |

By end of Phase 2, transmax is at parity with the TMS and document-MT leaders on day-to-day formats and ahead of all of them on TLFs and formulas. By end of Phase 3, transmax owns the pharma-specific formats (eCTD, IDML, LaTeX) that no competitor handles end-to-end today.

---

## 7. Cross-Pillar Integration

The four pillars are not silos. They interact in specific, designed ways.

| Interaction | Pillars | Mechanism |
| --- | --- | --- |
| Rules feed determinism | 1 → 2 | L0 / L1 rule-set updates seed Determinism Library candidates for human signing |
| Determinism feeds confidence | 2 → 3 | A Tier-1 hit produces a confidence of 1.0 by construction (signed, byte-stable) |
| Confidence feeds memory | 3 → 2 | High-confidence reviewer-accepted segments are written to TM with their signal vector |
| Format feeds quality gate | 4 → 3 | Format-fidelity defects are inputs to the confidence model and the defect taxonomy |
| Knowledge graph feeds rules | 1 ↔ 1 | Drug, indication, population entities are referenced by rule conditions |
| TLF cell-type drives memory tier | 4 → 2 | Numeric cells bypass LLM; statistical-notation cells must hit Tier 1 |
| Reviewer behaviour feeds confidence | 3 ↔ 3 | Reviewer-accept-without-edit is the calibration ground truth |
| Audit ledger ties everything | all | Every artefact (rule version, library entry, calibration model version, format-validator version) hash is recorded in JobConfigSnapshot |

A single segment translation, end-to-end, exercises all four:

```
1. Ingestion (Pillar 4): plain text or formatted run extracted as XLIFF unit with format tags.
2. Compile constraints (Pillar 1): applicable rules + glossary + knowledge graph slice.
3. Resolution cascade (Pillar 2): Determinism Library → exact TM → fuzzy TM → LLM.
4. Quality gate (Pillar 4 + Pillar 1): format fidelity, glossary adherence, hard-lock validation.
5. Confidence scoring (Pillar 3): eight-signal calibrated composite.
6. Disposition (Pillar 3): auto-approve, light review, full review or dual review.
7. Reviewer action (Pillar 3 + Pillar 1): edit + reason → calibration training example + candidate rule.
8. Export (Pillar 4): XLIFF → DOCX / PDF/A-1b / RTF / etc.
9. Audit (all): provenance, signal vector, artefact hashes recorded; chain extended.
```

---

## 8. Governance and Roles

Two new roles are added to the existing six-role RBAC:

| Role | Responsibility |
| --- | --- |
| **Curator** (existing) | Reviews candidate rules and library entries; promotes to `reviewed` |
| **Rule Approver** (new) | Signs rules and Determinism Library entries to `active` |
| **Calibration Owner** (new) | Owns the confidence calibration models per slice; signs new model versions |

Both new roles require MFA and are restricted to a small named set per tenant; assignments are themselves auditable.

---

## 9. Phased Delivery — Consolidated View

| Capability | Phase 1 (0–90 days) | Phase 2 (3–6 months) | Phase 3 (6–12 months) |
| --- | --- | --- | --- |
| Pillar 1 — Rules / Black Books | Tenant scope; L0–L5 layering; conflict resolver; signed rule sets; basic rule console; EDQM Standard Terms imported as L0 | Knowledge graph; MedDRA / ATC / IDMP ingestion; entity-aware constraints; TBX import; rule-impact telemetry | ML-assisted rule discovery; per-brand and per-study rule packs; partner regulator-pack marketplace |
| Pillar 2 — Memory / Determinism | Determinism Library (seeded with EMA QRD + EDQM); Tier-1 / Tier-2 cascade; segment-result cache; pre-translation dedup; cost ceiling enforcement; determinism KPI | Fuzzy TM as RAG context; constraint-pack and reasoning caches; model routing; tenant budgets | Adaptive cache eviction; cross-tenant boilerplate library (opt-in); offline pipeline that promotes high-hit-rate fuzzy matches into Determinism Library |
| Pillar 3 — Confidence / Escalation | Eight signals captured; back-translation infra; global calibration model; tiered thresholds; critical-defect overrides; manual escalation routing | Per-slice calibration models; check-and-recheck loop; SLA-driven auto-routing with reviewer skill profiles; calibration KPIs | Per-reviewer fine-tuning; explanation-of-escalation; reviewer-load balancing |
| Pillar 4 — Format Fidelity | XLIFF 2.1 canonical; DOCX/XLSX/PPTX/HTML/XLIFF/TMX ingestion; placeholder-count QA; PDF/A-1b export | RTF; TLF cell-level segmentation + classifier; statistical-notation Determinism; OOML/MathML formulas; OCR fallback; locale-aware handling; DTP reflow; IDML | Figures pipeline (SVG-text); LaTeX support; eCTD v4.0 export; partner ingestion plug-ins |

Each phase ships a Validation Summary Report (per the Headless Agent Spec) covering all four pillars together. Customers can verify, per release, that capabilities match the published roadmap.

---

## 10. Acceptance Criteria — "Done" for the Capabilities Programme

A release is "done" against this spec when **all** of the following hold on a single tag.

1. Every `TranslationRule` has a non-null `tenant_id`; PostgreSQL row-level security enforces isolation; auto-promotion is impossible at the model layer; rule-set artefacts are Ed25519-signed.
2. Determinism Library is seeded with EMA QRD section titles, EDQM Standard Terms, ICH-harmonised wordings and statistical-notation phrases for the top six language pairs (en→de, en→fr, en→es, en→it, en→pt, en→ja).
3. Tier-1 / Tier-2 cascade live; Determinism KPI reported per tenant; segment-result cache live with measurable hit rate.
4. Eight confidence signals captured per segment; calibration model active; tiered thresholds enforced; critical-defect overrides bypass confidence.
5. Check-and-recheck loop implemented and exercised on the golden corpus.
6. XLIFF 2.1 canonical in production; DOCX (with tracked changes), XLSX, PPTX, HTML, PDF (digital), XLIFF, TMX ingestion live; PDF/A-1b export live.
7. RTF ingestion and export with TLF cell-level segmentation and classifier ≥ 99% accuracy on the curated corpus.
8. OOML / MathML formula round-trip with structural integrity assertions.
9. Format-fidelity QA gate live; defects emitted into the existing taxonomy; thresholds enforced.
10. Validation Summary Report per release covers all four pillars and is signed by Programme Lead, Regulatory Affairs Lead and Quality Lead.
11. At least three customers have ingested at least one each of: a real SmPC; a real PIL; a real CSR with TLFs; a real protocol with formulas; and have signed off the resulting translations through the platform.

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Determinism Library curation overhead high | High | Medium | Seed automatically from EDQM, EMA QRD, ICH; provide a curation console; bulk-sign workflow for trusted sources |
| Rule conflicts cause unexplained translations | Medium | High | Conflict resolver emits a structured explanation per fired rule; reviewers see which rules fired; UI surfaces ties for human resolution |
| Calibration model overfits to a few prolific reviewers | Medium | Medium | Reviewer-agreement signal weighted by sample size; minimum-evidence threshold per slice; global fallback |
| Format complexity exceeds parser capacity (rare native formats) | Medium | Medium | Plug-in ingestion architecture; partner integrations for IDML, FrameMaker, etc.; manual fallback path |
| TLF classifier mis-classifies cells | Medium | High | Conservative defaults (mis-classify as numeric → no translation, safest); reviewer override; classifier retrained quarterly |
| OCR failure on poor scans | Medium | Medium | Confidence-gated OCR; below threshold → escalate, not silently translate |
| Formula corruption on round-trip | Low | High | Hard-lock operators / numerals / units; validate structural tree byte-stability; integration tests on a formula corpus |
| Determinism breaks under LLM provider change | Medium | High | Pin model + temperature in JobConfigSnapshot; segment-result cache absorbs residual variance; re-translation never happens silently for historical jobs |
| Cross-tenant Determinism Library sharing leaks PHI | Medium | High | Cross-tenant sharing is opt-in only; PHI scrubber on all candidate entries; legal review before any public-domain seeding |

---

## 12. Open Questions

1. Do we expose the rule console to customers as a self-service product, or is rule authoring a paid professional-services engagement?
2. Determinism Library: do we publish a *core L0 pack* (EMA QRD, EDQM Standard Terms, ICH) as open data, or treat it as proprietary?
3. Confidence calibration: do we surface the calibrated probability to reviewers as a number, or only as a tier label? The honest number can be either reassuring or anxiety-provoking depending on the audience.
4. TLF: do we build native RTF round-trip, or do we ingest only and emit DOCX (which most regulators accept for CSR appendices)?
5. Formulas: is on-prem Mathpix viable for OCR of formula images, or do we accept the cloud dependency?
6. DTP reflow: build in-house (fragile, slow) or partner with a DTP automation vendor (cheaper to start, dependency)?
7. Cross-tenant boilerplate library: which customers want this, and at what discount?

---

*End of specification.*
