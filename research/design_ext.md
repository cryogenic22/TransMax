Got it: **OpenAI standard**, and **TM matching segment-only**. Sensible starting point.

Below is the straight answer on phrase-level TM, API flexibility for full docs vs components, and how to deal with tables without the whole thing turning into spaghetti.

---

## 1) Segment-only TM vs phrase-level TM

### Segment-only TM (what you’re choosing)

**Pros**

* Simple and predictable. Easy to explain to QA and linguists.
* Lower risk of Frankenstein output (stitched phrases that don’t quite fit).
* Easier audit: “this segment reused TM entry X”.

**Cons**

* You miss reuse for long segments where only one clause matches a prior translation.
* Repeated micro-phrases in PIL/SmPC (standard warnings) won’t be reused unless the entire sentence matches.

### Phrase-level TM (what you’re asking about)

Phrase-level is basically “sub-segment matches”: find matching chunks inside a sentence and reuse them.

**Benefits**

* **Higher leverage on standard pharma phrasing**. PIL/SmPC have lots of repeated fragments (e.g., “If you get any side effects, talk to your doctor…”). Phrase-level can reuse these reliably even when the sentence is slightly different.
* **Better consistency** across documents and versions, especially when writers tweak wording but keep the meaning.
* **Cost control**: fewer tokens, less re-generation, because the model is guided with more “known good” text.
* **Faster reviewer experience**: fewer style/phrase debates because standard fragments keep recurring identically.

**Downsides (why I didn’t push it for v1)**

* It raises a real question: *who “owns” the final sentence*? The model or the TM fragments.
* You need conflict resolution rules (what if two overlapping phrases match with different translations?).
* It can make Arabic/Japanese trickier if the phrase boundaries don’t align nicely.

**Verdict:** You’re right to start with segment-only. Phrase-level becomes worthwhile once:

* you have a decent TM volume, and
* you care about “standard phrase consistency” as a headline feature.

A neat middle ground for later: **segment-only TM**, but allow a small library of **approved standard phrases** (not full phrase-level TM). That gets you 80% of the benefit with 20% complexity.

---

## 2) OpenAI standardisation: what changes in design

This simplifies a lot:

### Recommended model split

* **Primary translation + fixes:** one model (OpenAI) with deterministic gating outside the model.
* Keep prompts versioned. Don’t let “prompt tweaks” happen casually.

### Important: use structured outputs

Make the model return strict JSON for segment outputs. You’ve already set this direction, which is exactly right for auditability and UI readiness.

---

## 3) Will the API support full document input vs components?

It should support both. And it can, cleanly.

### The trick: use a document “container” format with blocks

Instead of accepting only one big string or only small segments, accept a **Document JSON** that can represent either.

### Recommended request format (flexible)

`POST /api/v1/translations`

```json
{
  "document": {
    "doc_id": "optional-client-id",
    "doc_type": "pil",
    "source_language": "en",
    "blocks": [
      { "block_id": "b1", "type": "paragraph", "content": "Patient must take 10 mg daily." },
      { "block_id": "b2", "type": "table", "content": { "rows": [[ "Dose", "10 mg" ], [ "Frequency", "Daily" ]] } }
    ]
  },
  "target_language": "ar",
  "domain": "labeling",
  "audience": "patient",
  "risk_level": "high",
  "requirements": {
    "glossary_id": "global_pharma_v2",
    "tm_id": "client_tm_2026"
  },
  "options": {
    "mode": "async",
    "max_iterations": 2
  }
}
```

This lets you pass:

* a full document in one call
* or a “document” with just one block (which is basically a component)

**Why it’s future-proof**

* UI can show a document with blocks.
* Systems can call it with a single string block.
* Audit can track block-level and segment-level changes.

---

## 4) How to support complex table content (without breaking meaning)

Tables are where naive translation goes to die. The biggest risks:

* numbers/units shifting columns
* row/column meaning being changed
* headers not matching regulated phrasing
* cells being merged or dropped
* bilingual reviewers needing structure preserved

### The right approach: treat tables as structured data, not text

You don’t “translate a table”. You translate **cells** with **context**.

#### Step-by-step table handling

1. **Table parsing** (caller provides structure, or UI extracts it)

   * rows, columns
   * merged cells (rowspan/colspan)
   * header rows/columns
   * cell types: text vs numeric vs unit-bearing vs code

2. **Cell classification**

   * If cell is purely numeric or unit token: do not translate.
   * If cell contains mixed content: translate text parts, preserve numeric/unit parts.
   * If cell is a header: apply glossary + preferred phrases strongly.

3. **Context injection**
   When translating a cell, include minimal context:

   * table title (if present)
   * row header and column header
   * neighbouring header labels (optional)

4. **Structure-preserving output**
   Return the same table structure with translated cell strings inserted.

### Example: table block output

```json
{
  "block_id": "b2",
  "type": "table",
  "content": {
    "rows": [
      ["الجرعة", "10 mg"],
      ["الوتيرة", "يومياً"]
    ]
  }
}
```

### Deterministic gates for tables

Run the same critical checks, but table-aware:

* Units and numbers must stay in the same cell (or remain adjacent if mixed).
* No cell count changes.
* Header translations must respect glossary phrases.

### What about “really complex” tables?

If tables include footnotes, multi-line cells, embedded bullets:

* store each cell as a mini-block internally
* segment it, translate, then reassemble
  Still controlled. Still auditable.

---

## 5) What the API returns for full documents

Return both:

1. **Translated document** (same blocks, translated content inserted)
2. **Review artefacts** (segment-level issues, table cell issues)

Example response shape:

```json
{
  "job_id": "job-...",
  "decision": "REVIEW_REQUIRED",
  "translated_document": { "...same blocks, translated..." },
  "quality_report": { "...violations with block_id + segment_id/cell_id..." },
  "audit_trail_id": "uuid-..."
}
```

This makes UI easy:

* render the translated doc
* highlight violations inline (cell-level for tables, segment-level for paragraphs)

---

## 6) Quick “tell it like it is” guidance

* If you want tables to work well, **don’t accept DOCX/PDF as the source truth** in v1. Accept a structured JSON representation from upstream (or UI).
* Phrase-level TM is a second-phase optimisation. It’s brilliant when you have scale. It’s distracting when you’re still proving “no critical errors”.

---

If you want, I can give you two more concrete things next:

1. The **Document JSON schema** (blocks, tables, merged cells, cell ids) and how it maps to audit/violations.
2. The **table-specific prompt template** for OpenAI that translates cells while keeping numbers/units locked and returns strict JSON per cell.
