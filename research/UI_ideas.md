That “agents learn and update the glossary/knowledge/domain store over time” feature is **powerful**… and also **the fastest way to accidentally poison your own translation system** if you don’t put it on a leash.

So yes, I like it. But only in a controlled shape.

## What I think about the feature

### Why it’s great

* Translation teams don’t just translate. They **standardise language** across markets and years.
* The biggest pain isn’t the first translation. It’s the 200th time someone debates the same term again.
* If TransMax can surface “this is the term we always end up approving”, you reduce review cycles massively.

### Where it can go wrong

* Agents will “learn” things that are context-specific and then apply them everywhere.
* You get silent drift: translations become consistent… but consistently wrong.
* In regulated content, uncontrolled learning becomes an audit headache: “who approved this change, and when?”

### The safe design (this is the key)

Make glossary learning **two-layered**:

1. **Suggested knowledge** (agent-generated, auto-collected)
2. **Approved knowledge** (human-curated, versioned, effective-dated)

Agents can *propose*. Humans *promote*.

A simple workflow:

* Agent suggests a new term mapping or preferred phrase
* It lands in a **“Proposed” queue** with evidence (segments, doc types, markets, frequency)
* A linguist/regulatory reviewer approves it into an **“Approved Glossary vX.Y”**
* The pipeline only enforces **Approved** entries by default

That’s how you get learning without chaos.

---

# UI ideas for a “proper” enterprise translation team

If you want sophisticated teams to adopt this as a service, the UI needs to feel like a serious workstation, not a demo.

### 1) Job inbox that behaves like a real workflow

* Filters: doc type, product, market, language pair, risk level, status
* Views: “Needs review”, “Blocked”, “Waiting on medical”, “Ready to publish”
* SLA tags: what’s due, what’s stuck, what’s failing repeatedly

### 2) Review screen built for speed

**Split view**: source left, target right

* Inline highlights for violations (numbers/units/negation/glossary)
* “Fix suggestions” panel that shows what the system wants changed
* One-click actions:

  * Accept suggested fix
  * Override translation
  * Request retranslate (segment only)
  * Escalate to medical review

### 3) A proper table reviewer (this is where tools usually fall apart)

* Table preserved as a table, not flattened text
* Cell-level violations and locking visual cues
* Header context displayed when you click a cell
* “Lock cell” toggle for reviewers (prevents future edits)

### 4) Glossary workstation (not just a CRUD page)

* Search term mappings by language pair and domain
* Show:

  * Preferred term
  * Allowed variants
  * Forbidden variants
  * Scope (PIL patient vs SmPC HCP)
  * Evidence: where it was used, how often, and what reviewers chose
* Bulk import/export (CSV) for real teams

### 5) “Proposed terms” queue (agent learning, human approval)

A dedicated screen:

* Ranked suggestions (by frequency, risk, reviewer overrides)
* For each suggestion:

  * examples from real segments
  * doc types where it appeared
  * markets/languages impacted
  * who approved/declined and why
* Buttons:

  * Approve into glossary version
  * Approve for a specific scope only
  * Reject (with reason)
  * “Needs discussion”

### 6) Translation Memory view that’s actually usable

Even with segment-only TM:

* Show top TM matches for a segment
* Provide “Use TM match” vs “Keep current”
* Highlight differences between TM match and current output

### 7) Audit and versioning view (pharma teams will ask for it)

* For any job: show model/prompt/glossary/policy/language pack versions
* Show decisions and gates triggered
* Show who approved what, when
* One-click export of audit pack (JSON + summary PDF later)

### 8) Team collaboration features (the grown-up stuff)

* Assign segments to reviewers
* Comments and @mentions on segments/cells
* “Resolve thread” workflow
* Change history per segment and per glossary term

### 9) Analytics dashboard that’s genuinely useful

* Most common violation types
* Top “blocked” reasons
* Where reviewers spend time
* Glossary gaps by domain
* Trend: how often HITL is triggered and why

---

# The enhanced pipeline details (Markdown content)

Below is the MD file content you asked for. You can drop this into `ENHANCED_PIPELINE.md`.

```md
# TransMax Enhanced Pipeline (Pharma-Ready)
Version: 1.0
Owner: Ekta
Scope: API-first translation service with UI-ready workflow, glossary learning (controlled), Arabic + Japanese readiness

---

## 1) Overview
TransMax is a controlled translation system for regulated pharma content. It prioritises:
- Meaning preservation (especially safety language)
- Terminology enforcement (approved glossary + TM)
- Deterministic quality gates
- Clear routing: PASS / REVIEW_REQUIRED / BLOCKED
- Audit-grade traceability with versioning

A UI can sit on top to manage review, approvals, glossary curation, and continuous improvement.

---

## 2) Key design principles
1. The model drafts. The system decides.
2. Deterministic checks are the backbone for safety and compliance.
3. Version everything that can change behaviour:
   - model, prompt, glossary, policy, language pack
4. Store structured evidence, not free-form LLM reasoning.
5. Learning is controlled:
   - agents propose, humans approve

---

## 3) End-to-end pipeline stages

### Stage A: Ingestion and structure preservation
**Input:** PDF/DOCX or structured JSON document  
**Output:** Document blocks with stable IDs

- If input is PDF/DOCX:
  - Layout extraction produces blocks: headings, paragraphs, lists, tables
  - Each block gets:
    - `block_id`, `type`, `content`, `source_hash`
    - `layout_confidence` (0-1)
- If layout confidence is below threshold:
  - block is flagged for HITL layout verification

**Rationale:** If structure is wrong, translation can be “correct” but unusable.

---

### Stage B: Segmentation
Each block is segmented deterministically into translation units:
- Segment IDs are stable and reproducible under fixed versions.
- Tables are handled as structured cells (preferred) or split into cell tasks.

**Output:** `segmentation_manifest` for audit and UI mapping

---

### Stage C: Constraint compilation (Glossary + TM via Postgres/pgvector)
For each segment:
- Retrieve mandatory glossary terms, allowed variants, forbidden variants
- Retrieve segment-only TM matches via pgvector (top-k per segment)
- Compile into a Constraint Pack

**Output:** Constraint Pack (versioned)

---

### Stage D: Privacy controls (optional, tenant policy)
- PII detection (regex + NER)
- Replace with stable tokens, e.g. `[[PII:NAME:8f3a]]`
- Add placeholder preservation checks:
  - count and IDs must match exactly in output
- Store mappings securely if rehydration is required

---

### Stage E: Draft translation (LLM)
- Translate blocks/segments using OpenAI
- Strict JSON output format (segment-aligned)
- Constraint Pack injected:
  - mandatory terms
  - forbidden terms
  - preferred phrases by domain/audience

---

### Stage F: Deterministic quality gates
The system checks output using deterministic rules:
**Critical (BLOCKED)**
- number mismatch
- unit mismatch
- frequency mismatch
- negation flip

**Major (REVIEW_REQUIRED)**
- mandatory term missing
- forbidden term present
- modality drift
- population drift

**Language-pack specific**
- Arabic: digit policy, decimal separator, unit adjacency, RTL punctuation patterns
- Japanese: tokeniser-based term checks, disallowed variants, mandatory phrase checks

**Output:** Quality report with typed violations and exact locations:
- `{block_id, segment_id}` or `{block_id, table_id, row_id, cell_id}`

---

### Stage G: Targeted refinement loop (bounded)
If violations are fixable:
- Create a Fix Packet per failing segment/cell:
  - what must change
  - what must not change
  - required replacement terms/phrases
- Call the LLM only on failing items
- Max iterations: default 2
- Re-run quality gates after each iteration

**Goal:** Fix issues without collateral rewrites.

---

### Stage H: Decisioning and HITL routing
Decision rules use:
- gate severity outcomes
- risk policy (doc type, section type, audience, domain)
- language pack defaults (Arabic/Japanese high-risk initially REVIEW_REQUIRED)

Statuses:
- PASS
- REVIEW_REQUIRED
- BLOCKED

---

### Stage I: Audit record creation
Create structured audit record including:
- input/output hashes
- versions used (model/prompt/glossary/policy/language pack)
- checks run
- violations and actions taken
- final decision + scores
- optional signed hash for tamper evidence

---

## 4) Continuous improvement (controlled learning)
TransMax supports “learning” through a two-layer store:

### 4.1 Proposed Knowledge (agent-generated)
Agents can propose:
- new glossary mappings
- preferred phrases by doc type/audience
- allowed/forbidden variants
- new gate patterns (e.g., unit variants)

Each proposal includes:
- evidence segments where it occurred
- frequency and impact
- who overrode what in review

### 4.2 Approved Knowledge (human-curated)
Only approved entries are enforced by default.

Workflow:
1) Proposed item created
2) Human review in UI
3) Approved into a new glossary version (effective-dated)
4) Regression tests run on golden set
5) Promote to production policy

---

## 5) UI-ready API behaviour
The API supports:
- full document input (blocks, lists, tables) or single-block calls
- job-based workflow:
  - create job, poll status, fetch result
- segment/cell-level review endpoints:
  - fetch segments/cells with violations
  - apply overrides
  - approve/reject segments and jobs
- glossary management:
  - view versions, curate terms, approve proposals

---

## 6) Table handling approach
Tables are translated as structured objects:
- each cell has `cell_id`, `cell_type`, `locked` metadata
- numeric/unit/locked cells are preserved exactly
- header context is passed to the translator when translating cells
- table structure must remain identical

---

## 7) What “pharma-ready” means in practice
- No critical errors escape undetected on validated golden sets
- Traceable versions and auditable events
- Controlled HITL routing for high-risk content
- Change control for any behaviour-changing updates
- Structured logs that can be inspected without reading model “reasoning”
```

---

# Continuing with “fixing the frontend”

I don’t have your current frontend code or current UI screens in this chat, so I can’t literally “fix” what exists line-by-line.

But I *can* give your UI team a very concrete build spec that avoids the usual traps. Here’s the build plan I’d hand them.

## Frontend build spec: make it a real translation system

### Core routes

* `/jobs`
* `/jobs/:jobId/review`
* `/jobs/:jobId/audit`
* `/glossary` (versions + search)
* `/glossary/proposals` (agent-suggested queue)
* `/tm` (search and manage)
* `/settings/policies` (who can PASS what, per doc/section/language)

### Review screen layout

* Left panel: source blocks/segments (virtualised list)
* Right panel: target segments (editable)
* Side drawer:

  * Violations for current segment/cell
  * Glossary terms relevant to segment
  * TM matches (segment-only)
  * Actions: accept fix, override, retranslate, escalate

### Table review component (must-haves)

* grid rendering with fixed headers
* click cell to open context pane (row header + column header)
* show locked cells as read-only
* show cell-level violations
* preserve structure always

### RTL support (Arabic)

* BiDi-safe rendering
* correct cursor behaviour in editable fields
* mirrored layout option (source left, target right still works, but text alignment must be correct)
* fonts tested for Arabic readability

### Approval workflow

* Approve per segment/cell
* Approve whole job once all items resolved
* Every approval creates a review event saved via API

### Glossary “learning” UX

* Proposed queue shows evidence and frequency
* One-click “promote to glossary version”
* Version diff view: what changed between glossary versions
* Rollback option (because someone will approve something silly on a Friday)

---

