Yep. Here’s a concrete architecture + “how it actually works” design, plus a prompt set with a few-shot style that won’t drift into poetry when you need it to be boring and safe.

I’m going to describe it in a way that lets you:

* run it as a **pure API** for system-to-system calls
* later drop a **Translation UI** on top without changing fundamentals
* keep it audit-friendly, versioned, and controlled

---

# 1) Architecture overview

### The big idea

TransMax is **two engines working together**:

1. **Generation engine (LLM)**
   Draft translation + targeted fixes.

2. **Control engine (deterministic + policy)**
   Terminology checks, safety checks (numbers/units/negation/modality/frequency), routing, audit.

LLM produces text. The control engine decides if it’s usable.

---

# 2) Components

### A. API Gateway (FastAPI)

* Auth (OAuth2/JWT or mTLS)
* Rate limits, request size limits
* Routes requests into “sync” or “async job”
* Returns `audit_trail_id` and `job_id` (if async)

### B. Orchestrator (LangGraph state machine)

This is the “agentic workflow”, but it’s not vibes-based. It’s a bounded, versioned state machine.

States (high-level):

1. Validate + normalise request
2. Segment
3. Compile constraints (glossary, style, TM)
4. Draft translate
5. Deterministic quality gates
6. If needed: targeted fix loop (max N iterations)
7. Final decision + audit write

### C. Constraint Service

* Fetches glossary + versions
* Pulls TM matches via pgvector
* Produces a **Constraint Pack** used by prompts and by deterministic gates

### D. Quality Gate Service (deterministic)

* Runs critical/major/minor checks
* Produces a Quality Report (your JSON)
* Decides PASS/REVIEW/BLOCK using policy rules

### E. Audit Service

* Creates the audit record JSON
* Stores hashes and structured events
* Optional immutable log signature

### F. Storage (Postgres + pgvector)

* Glossaries + versions
* Translation memory segments + embeddings
* Jobs and job events
* Audit records and indexes
* Optional raw text blobs (off by default)

---

# 3) Data model (Postgres + pgvector)

### Core tables (minimal, but future-proof)

* `tenants(tenant_id, config_json, created_at)`
* `language_packs(pack_id, version, config_json, created_at)`
* `policies(policy_id, version, rules_json, created_at)`
* `glossaries(glossary_id, version, meta_json, created_at)`
* `glossary_terms(glossary_id, version, term_id, source, target, allowed_variants_json, forbidden_variants_json, meta_json)`
* `tm_segments(tm_id, version, segment_hash, source, target, embedding vector(1536), meta_json)`
* `translate_jobs(job_id, tenant_id, status, request_json, created_at, updated_at)`
* `job_events(job_id, event_type, event_json, created_at)`
* `audit_records(audit_id, tenant_id, created_at, decision, scores_json, record_json, record_hash)`
* `translations(translation_id, job_id, segment_id, source_hash, target_hash, final_target_text_ref, meta_json)`
  (this helps the UI later: segment-level review, overrides, approvals)

---

# 4) LangGraph state machine (detailed)

### State object (what flows through the graph)

* request metadata
* segmentation manifest (segment ids + hashes)
* constraint pack (glossary terms, forbidden terms, preferred phrases, TM hits)
* draft translation (segment-aligned)
* quality report (typed violations)
* iteration events (actions taken)
* final decision and scores
* audit record

### Graph flow (practical)

1. **ValidateRequest**

   * confirm `audience`, `domain`, `risk_level`, `glossary_id`, `target_language`
   * load `language_pack`, `policy`
2. **SegmentText**

   * deterministic sentence/list segmentation
   * Arabic: handles punctuation + parentheses sensibly
   * Japanese: sentence split by 。！？ plus bracket handling
3. **CompileConstraints**

   * fetch glossary version + build “must use” and “must not use” lists
   * query TM via pgvector for top-k per segment
4. **TranslateDraft**

   * call LLM with strict format: JSON, per-segment output
5. **RunQualityGates**

   * deterministic checks (numbers/units/negation/frequency/modality/terms)
6. **RefineTargeted (loop, max 2 by default)**

   * only for segments that failed
   * apply “fix instructions” per violation type
   * translate again for those segments only
   * re-run gates
7. **Decide + AuditWrite**

   * compute composite scores
   * enforce policy (eg Arabic/Japanese high-risk defaults to REVIEW_REQUIRED in v1.1)
   * write audit record

---

# 5) API design that supports both systems and a future UI

## 5.1 Translation endpoints

### 1) Create a translation job (recommended default)

`POST /api/v1/translations`

Request:

```json
{
  "content": "Patient must take 10 mg daily.",
  "source_language": "en",
  "target_language": "ar",
  "domain": "labeling",
  "audience": "patient",
  "risk_level": "high",
  "requirements": {
    "tone": "plain_language",
    "glossary_id": "global_pharma_v2",
    "tm_id": "client_tm_2026",
    "arabic_digits_policy": "preserve_western"
  },
  "options": {
    "mode": "async",
    "max_iterations": 2,
    "store_raw_text": false
  }
}
```

Response:

```json
{
  "job_id": "job-8d7f...",
  "status": "QUEUED",
  "audit_trail_id": "6d6d7b0a-...",
  "links": {
    "status": "/api/v1/translations/job-8d7f...",
    "result": "/api/v1/translations/job-8d7f.../result",
    "audit": "/api/v1/audit/6d6d7b0a-..."
  }
}
```

### 2) Poll job status

`GET /api/v1/translations/{job_id}`

### 3) Get result (segment-aligned)

`GET /api/v1/translations/{job_id}/result`

Response includes:

* per-segment outputs
* violations per segment
* decision and scores
* audit id

### 4) Webhook callback (optional)

If the caller supplies `callback_url`, you can `POST` completion events.

---

## 5.2 UI-supporting endpoints (future-ready)

These let a UI manage review without reworking the platform.

### 5) Fetch segment-level view for review

`GET /api/v1/translations/{job_id}/segments`

Returns:

* `segment_id`
* source text (if stored/allowed) or source hash + fetch token
* target suggestion
* violations
* TM suggestions (optional)

### 6) Apply human edits (stored as overrides)

`PATCH /api/v1/translations/{job_id}/segments/{segment_id}`

Request:

```json
{
  "action": "override_translation",
  "new_target_text": "يجب على المريض تناول 10 mg يومياً.",
  "reviewer": { "id": "user-123", "role": "linguist" },
  "reason_code": "style_preference",
  "comment": "Standard patient phrasing."
}
```

### 7) Approve / reject at job level

`POST /api/v1/translations/{job_id}/review-actions`

Actions:

* `approve_all`
* `approve_segment`
* `request_retranslate_segment`
* `escalate_to_medical_review`
* `finalise_translation`

Each action writes a **review event** into audit/job events.

---

## 5.3 Glossary and TM management endpoints

### Glossary

* `POST /api/v1/glossaries` (create new version)
* `GET /api/v1/glossaries/{glossary_id}/versions`
* `GET /api/v1/glossaries/{glossary_id}/{version}`
* `POST /api/v1/glossaries/{glossary_id}/{version}/terms:bulk_upsert`

### TM

* `POST /api/v1/tm/{tm_id}/{version}/segments:bulk_upsert`
* `GET /api/v1/tm/{tm_id}/{version}/search?query=...`

These are what makes the UI feel “real” later.

---

# 6) Prompt and instruction set (agentic steps)

The trick: **don’t ask the model to “think”**. Ask it to **produce structured outputs** and **follow constraints**.

Below are prompt templates per step. These are written like you’d store them as versioned prompt files.

## 6.1 Constraint Pack format (fed into prompts)

Your orchestrator builds this object:

```json
{
  "language_pack": { "id": "ar_pack", "version": "1.0.0", "script_direction": "rtl" },
  "glossary": {
    "id": "global_pharma_v2",
    "version": "2.4.0",
    "mandatory_terms": [
      { "source": "daily", "target": "يومياً", "allowed_variants": ["كل يوم"], "term_id": "t-001" },
      { "source": "take", "target": "تناول", "allowed_variants": ["يأخذ"], "term_id": "t-002" }
    ],
    "forbidden_terms": [
      { "target": "جرعة", "reason": "Use 'كمية' in patient leaflet", "term_id": "f-014" }
    ]
  },
  "style": {
    "audience": "patient",
    "tone_rules": [
      "Use plain language.",
      "Avoid complex subordinate clauses."
    ]
  },
  "tm_matches": [
    {
      "segment_id": "seg-001",
      "matches": [
        { "source": "Patient must take 10 mg daily.", "target": "يجب على المريض تناول 10 mg يومياً.", "score": 0.91 }
      ]
    }
  ]
}
```

---

## 6.2 Draft Translation Agent (Translator)

### System instruction (Translator)

* Output must be valid JSON.
* No commentary, no explanation.
* Must keep numbers/units unchanged unless policy says otherwise.
* Must produce per-segment outputs.

```text
You are TransMax Translator.
Translate each segment into the target language using the Constraint Pack.
Follow mandatory glossary terms. Do not use forbidden terms.
Preserve meaning exactly. Preserve numbers, units, frequency, negation, and modality.
Return ONLY valid JSON in the specified schema. Do not include any extra keys or text.
```

### User prompt template (Translator)

```text
Target language: {{target_language}}
Audience: {{audience}}
Domain: {{domain}}
Risk level: {{risk_level}}

Constraint Pack:
{{constraint_pack_json}}

Segments:
{{segments_json}}

Return JSON:
{
  "segments": [
    { "segment_id": "...", "target_text": "...", "used_mandatory_term_ids": ["..."], "used_tm": true|false }
  ]
}
```

### Few-shot example (Arabic)

**Input segments**

```json
[
  { "segment_id": "seg-001", "source_text": "Patient must take 10 mg daily." }
]
```

**Expected output**

```json
{
  "segments": [
    {
      "segment_id": "seg-001",
      "target_text": "يجب على المريض تناول 10 mg يومياً.",
      "used_mandatory_term_ids": ["t-001", "t-002"],
      "used_tm": true
    }
  ]
}
```

### Few-shot example (Japanese)

**Input**

```json
[
  { "segment_id": "seg-001", "source_text": "Do not take this medicine with alcohol." }
]
```

**Expected output**

```json
{
  "segments": [
    {
      "segment_id": "seg-001",
      "target_text": "この薬はアルコールと一緒に服用しないでください。",
      "used_mandatory_term_ids": [],
      "used_tm": false
    }
  ]
}
```

---

## 6.3 Semantic Reviewer Agent (optional but useful later)

This is *not* the deterministic gate. It’s an extra “spotter” for meaning drift, but it must output structured flags, not essays.

### System instruction (Semantic reviewer)

```text
You are TransMax Semantic Reviewer.
Compare source and target for meaning preservation.
Do not rewrite anything. Only flag issues.
Return ONLY JSON. No explanation.
```

### User prompt template

```text
Language pair: {{source_language}} -> {{target_language}}
Check for: negation flips, modality drift, population drift, missing safety qualifiers, additions.

Segments:
[
  { "segment_id": "...", "source_text": "...", "target_text": "..." }
]

Return:
{
  "flags": [
    { "segment_id": "...", "flag_type": "...", "severity": "major|critical", "note": "..." }
  ]
}
```

**Example flag output**

```json
{
  "flags": [
    {
      "segment_id": "seg-007",
      "flag_type": "possible_negation_flip",
      "severity": "critical",
      "note": "Target appears to remove prohibition."
    }
  ]
}
```

---

## 6.4 Targeted Fix Agent (Editor/Fixer)

This is where most agentic systems go off the rails. The rule is simple:

* Only edit the flagged segments.
* Only fix the listed violations.
* Keep everything else unchanged.

### System instruction (Fixer)

```text
You are TransMax Targeted Fixer.
You will receive segments and a list of violations to correct.
Only modify text to address the violations. Do not introduce new wording changes.
Preserve numbers, units, frequency, negation, modality.
Return ONLY JSON. No extra text.
```

### User prompt template (Fixer)

```text
Target language: {{target_language}}
Constraint Pack:
{{constraint_pack_json}}

Fix only these segments:
[
  {
    "segment_id": "seg-001",
    "source_text": "...",
    "current_target_text": "...",
    "violations": [
      { "type": "unit_mismatch", "evidence": { "expected": "mg", "observed": "mcg" } }
    ]
  }
]

Return:
{
  "fixed_segments": [
    { "segment_id": "...", "target_text": "...", "applied_actions": ["..."] }
  ]
}
```

**Few-shot: fix unit mismatch (Arabic)**

```json
{
  "fixed_segments": [
    {
      "segment_id": "seg-001",
      "target_text": "يجب على المريض تناول 10 mg يومياً.",
      "applied_actions": ["fix_unit_format"]
    }
  ]
}
```

**Few-shot: apply preferred phrase (Japanese)**
If glossary requires 「服用しないでください」 rather than 「飲まないでください」:

```json
{
  "fixed_segments": [
    {
      "segment_id": "seg-001",
      "target_text": "この薬はアルコールと一緒に服用しないでください。",
      "applied_actions": ["apply_preferred_phrase"]
    }
  ]
}
```

---

# 7) Deterministic gates (what they actually do)

These are code, not prompts. A quick but practical view:

### Gates you absolutely want in v1.1

* **Numbers**: parse numeric tokens from source/target, compare sets and positions
* **Units**: whitelist of units and patterns, compare adjacency to numbers
* **Frequency**: map phrases (daily/once daily/BID etc) to canonical forms; compare
* **Negation**: detect “no/not/do not/contraindicated” and their equivalents (Arabic/Japanese patterns included in language pack)
* **Terminology**: mandatory term presence via language pack matching (tokeniser for Japanese, normaliser for Arabic)
* **Forbidden terms**: disallow list match
* **Format**: list item counts, headings presence

These produce the typed violations that drive the fixer.

---

# 8) Future Translation UI: what sits on top

Because your API is job + segments + review actions, the UI becomes straightforward:

### UI screens (simple and powerful)

1. **Queue**: jobs by status (QUEUED/RUNNING/REVIEW_REQUIRED/BLOCKED/PASS)
2. **Review view**:

   * left: source segments
   * right: target segments
   * violations panel per segment
   * TM suggestions and glossary hints
   * approve / override / request retranslate
3. **Audit view**:

   * show versions used (model/prompt/glossary/policy/language pack)
   * show checks run and violations summary
   * show who approved what (review events)

### Why this matters

It keeps the “translation process” controlled without turning your API into a one-off tool that nobody trusts.

---

# 9) A practical note on Arabic + Japanese policies (v1.1)

Even if gates pass, I’d keep:

* **Arabic high-risk labelling** → default `REVIEW_REQUIRED` initially
* **Japanese patient PIL high-risk** → default `REVIEW_REQUIRED` initially

Not because the model can’t do it. Because you want the validation pack to earn your right to allow PASS.

---

If you want the next level of detail, tell me:

* which model family you’re standardising on first (OpenAI vs Gemini vs mixed)
* whether you want TM matching to be **segment-only** or allow **phrase-level** suggestions

And I’ll give you:

* a concrete LangGraph pseudo-implementation (nodes, edges, state)
* a “prompt versioning” strategy (what triggers a version bump)
* and a clean set of violation rules for Arabic/Japanese that are realistic, not academic.
