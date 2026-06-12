# ADR-0005: Pluggable document-parser backends behind a canonical IR

**Date:** 2026-06-12
**Status:** accepted

## Context

PDF ingestion is the weakest link in the fidelity story. The production path
(`app/services/pdf_service.py`) tries `unstructured` with `strategy="fast"` and
falls back to `pypdf` flat-text extraction. Measured on a real 17-page oncology
PDF (`bermejo-et-al-2026 … real-world-evidence`):

- **pypdf**: 747 blocks, ALL typed `"Sentence"`; **0 tables**; 2-column text
  interleaved; unicode corrupted (`Begoña` → `Bego�na`); names shattered
  (`S u s a n a de la Cruz`). `unstructured` did not even load in the env
  (`No module named 'pi_heif'`), so the "fast" path was never exercised.
- **Docling** (same PDF): 342 typed text items — 36 `section_header`,
  114 `list_item`, 20 `page_header`, 27 `page_footer`, 17 `footnote`,
  4 `caption` — **4 tables** with cell structure, **30 figures** detected,
  correct reading order, clean unicode. 171s first run on CPU (model download
  + OCR on); fast path (OCR off, born-digital) is the steady state.

The DOCX path, by contrast, already does a faithful in-place XML round-trip with
a fail-loud `FidelityError` gate (`app/services/document_export.py`,
`app/services/fidelity.py`). DOCX fidelity is good; **PDF structure recovery is
the gap**, and it is a pilot-blocking gap for a pharma reviewer who expects the
translated artifact to mirror the source (headings, tables, lists, footnotes).

We also evaluated **DocLang** (`doclang-project/doclang`) — it is a document
*representation format/DSL* (`.dclg.xml`), not a parser. It validates that a
**canonical intermediate representation between parser and engine is the right
shape**, but adopting its spec as our core model now would be premature.

## Decision

Introduce a **pluggable parser-backend architecture** in `app/services/parsing/`:

1. A **canonical IR** — `ParsedDocument` / `ParsedBlock` with a canonical
   `ElementType` enum (TITLE, SECTION_HEADER, TEXT, LIST_ITEM, TABLE, FIGURE,
   CAPTION, PAGE_HEADER, PAGE_FOOTER, FOOTNOTE, OTHER), reading order, page
   number, optional bbox/table-grid, and per-block provenance (which backend +
   confidence). The IR is the single source of truth all downstream consumers
   read; `ParsedDocument.to_legacy_blocks()` emits the existing
   `{"text","type","meta"}` shape so wiring is a backward-compatible drop-in.
2. A **registry + `get_parser(name=None)` factory** that selects the backend by
   `settings.parser_backend` (config, not branching — open for extension).
3. Four backends implementing one `DocumentParser` protocol:
   - **`pypdf`** — wraps today's extraction; always available; the fallback.
   - **`docling`** — default target; layout/table/reading-order/unicode.
     Import-guarded: a missing/broken Docling raises `ParserUnavailable`
     (fail-loud, A3) rather than silently degrading.
   - **`azure`** — Azure AI Document Intelligence connector.
   - **`google`** — Google Document AI connector.
   The Azure/Google connectors ship as real interfaces that **fail loud**
   (`ParserUnavailable`) when their SDK or credentials are absent — never a
   silent fallback to a worse parser (A3).

Default `parser_backend = "pypdf"` ships unchanged behaviour; the live upload
route is NOT re-wired in this loop (engine first, surface second — wiring is a
flagged follow-up so the running pipeline is never destabilised). Docling is
pinned via `tokenizers<0.22` (its transformers dep conflicts with 0.22.x) and
is intended to run in the controlled Docker/Railway env, not necessarily every
dev laptop.

## Consequences

- **Better**: PDF structure recovery becomes a backend swap, not a rewrite. The
  FidelityGate can finally cover the PDF→DOCX path (Docling structure becomes
  the "source skeleton" to compare). Cloud OCR/parse (Azure/Google) is a config
  flip for tenants who require it or who send scanned PDFs. One IR decouples
  parser choice from the segmenter/engine/exporter.
- **Worse / cost**: Docling is heavy (torch + layout/table models, ~hundreds of
  MB) and slow on first run / CPU — ingestion must stay async/background, and
  the model layer is a deploy-image concern. A dependency pin (`tokenizers`) is
  now load-bearing.
- **Possible later**: serialize the IR to DocLang `.dclg.xml` for interop;
  per-tenant backend selection; a "best-of" router that picks a backend by
  document class.

## Alternatives considered

- **Fix `unstructured` hi_res instead of adding Docling:** viable but heavier
  to operate, worse-maintained table models than Docling's, and still needs the
  same backend abstraction. Kept as a possible 5th backend, not the default.
- **Adopt DocLang as the core IR now:** rejected — it is a young spec; coupling
  our pipeline to an external DSL before it stabilises is risk without payoff.
  Noted as a future *serialization* of our own IR.
- **PDF → pixel-perfect PDF round-trip:** rejected as the default deliverable —
  reflowing translated text (20-30% expansion in DE/FR) back into a fixed PDF
  layout is a hard, separate problem. Standardise on **PDF → structured DOCX**
  as the fidelity deliverable; scope a PDF→PDF overlay POC only if a pilot
  demands it.
- **One parser hard-coded with `if`-branches per format:** rejected — violates
  config-not-branching and would refork the divergence the codebase is actively
  paying down (A4 / TMX-3017 spirit).

## Affected teams / surfaces

- Document Pipeline pod: `app/services/parsing/*` (new), `app/services/pdf_service.py`
  (future flagged delegation), `app/api/documents.py` ingestion (future wiring).
- Platform: `requirements.txt` (`tokenizers<0.22` pin; Docling deploy image),
  `app/core/config.py` (`parser_backend`, `parser_ocr_enabled`).
- Quality & Regulatory: the FidelityGate extension to the PDF path (follow-up).
