# ADR-0006: Pluggable document-export backends + Tier-1 PDF→PDF overlay

**Date:** 2026-06-13
**Status:** proposed
**Relates to:** ADR-0005 (pluggable parsers); supersedes its "PDF→PDF out of scope by default" stance for the *fixed-layout* class of documents.

## Context

ADR-0005 standardised the *deliverable* on **PDF → structured DOCX** and explicitly
deferred a PDF→PDF overlay POC "only if a pilot demands it." A pilot now demands it:
in practice teams hand us a **PDF to translate** (a CSR, a SmPC, a PIL, a journal
manuscript), and they expect the translated artefact to look like the source —
**colours, tables, footnotes, side boxes, figures, masthead** preserved.

The export side today is asymmetric with the parser side:
- DOCX export is strong (in-place XML run replacement + fail-loud `FidelityError`).
- The *only* PDF the backend emits is a compliance **certificate**
  (`app/services/reporting_service.py`, reportlab). There is **no translated-PDF
  path at all** — and the fidelity claim "same as the source" is what a reviewer
  scrutinises hardest (A1/A3).

Measured reality of "full-fidelity PDF→PDF" (see the POC run on a 13-page NEJM
manuscript, `uploads/fidelity_fr_demo/`): PDF is fixed-layout with no reflow, and
translation expands text (FR ≈ +15-20%, DE more). So a faithful result is not one
algorithm but a **tiered** choice driven by document class and whether the source
is available.

## Decision

Introduce a **pluggable export-backend architecture** in `app/services/export/`,
symmetric with `app/services/parsing/` (registry + `get_exporter(name=None)` keyed
on `settings.export_backend` — config, not branching; A7). Three tiers, each a
backend implementing one `DocumentExporter` protocol:

1. **`docx` (Tier-3, exists)** — round-trip the authored source. Pixel-perfect
   because Word/the layout engine does layout. **Preferred whenever the editable
   source exists** — which for regulated CSRs it usually does (authored in
   Word/Veeva/Lorenz/TLF generators). Product behaviour: *request the source
   first*; PDF-only is the fallback, not the default.
2. **`pdf_overlay` (Tier-1, NEW)** — `PyMuPDF` (`fitz`): extract text spans with
   bbox + font + size + colour, translate per layout block, **redact** the source
   span and **re-insert** the translation into the same box with shrink-to-fit.
   Everything non-text (images, vector graphics, table rules, colours, side boxes,
   footnote rules, masthead) is **never touched**, so it is preserved exactly.
   Best for **fixed-layout** docs (labels, PILs, SmPCs, forms).
3. **`pdf_render` (Tier-2, later)** — Docling IR (ADR-0005) → re-typeset to a new
   PDF. *Structural* fidelity (headings/tables/reading order), NOT pixel. Best for
   **long narrative CSRs** where overlay's per-box text-expansion breaks down.

Default `export_backend` stays `docx`; `pdf_overlay` ships **flag-gated**, behind
the existing fail-loud pattern (A3: missing `fitz` → `ExporterUnavailable`, never
a silent downgrade).

## Consequences

- **Better**: a real "translated PDF that looks like the source" capability;
  PDF-only intake stops being a dead end; the tier is a config flip per document
  class / tenant. Symmetry with the parser registry keeps one mental model.
- **Worse / cost / honest limits** (surfaced by the NEJM POC):
  - **Text expansion**: FR is longer; overlay must shrink-to-fit or risk clipping.
    Hard cap on how small before it's unreadable → some boxes need reflow (Tier-2).
  - **Font matching**: source fonts are often **subsetted embedded** (only the
    glyphs used in the source). Re-using them for the target language frequently
    **lacks accented glyphs** (é/è/à/ç). Pragmatic answer: a Unicode-complete
    fallback face (serif/sans matched to the block) — a visible-but-acceptable
    deviation that must be disclosed, not hidden (A3).
  - **Justification / hyphenation / 2-column flow**: overlay re-wraps within a box;
    full journal justification is not reproduced perfectly.
  - **AGPL**: PyMuPDF is AGPL-3.0 — **licence review required** before shipping in
    a commercial product (legal gate, like TMX-PARSE-CLOUD-GOVERNANCE).
  - **Provenance**: every overlaid PDF must carry the same audit/segment-ID spine
    as DOCX (A5) — the overlay must map each translated box back to a `segment_id`.

## Alternatives considered

- **Only Tier-3 (always demand the source):** cleanest fidelity + audit story, but
  unrealistic as the *only* option — real intake is PDF-only often enough that a
  dead end loses pilots. Kept as the *preferred* path, not the only one.
- **Only Tier-2 (always re-render via Docling):** scales to CSRs but loses exact
  colours/positioning — fails the user's explicit "maintain colours/side boxes"
  goal for fixed-layout docs. Complementary, not a replacement for overlay.
- **HTML/CSS print pipeline (weasyprint/wkhtmltopdf):** another re-render (Tier-2
  flavour); heavier dep, same non-pixel-fidelity ceiling. Deferred.
- **Edit the PDF content stream directly (no redaction):** brittle across
  producers; redaction+insert via `fitz` is the maintained, supported path.

## Affected teams / surfaces

- Document Pipeline pod: `app/services/export/*` (new), `DocumentExportService`
  (folds under the registry as the `docx` backend).
- Platform: `requirements-export.txt` (PyMuPDF, opt-in like `requirements-parsing.txt`),
  `app/core/config.py` (`export_backend`), **legal: AGPL review**.
- Quality & Regulatory: FidelityGate for the overlay path (every source box mapped
  to a target box; no dropped/empty boxes — the content-aware gate that
  TMX-FIDELITY-CELL showed we still lack).
- Auth/Pipeline: segment-ID provenance on overlaid boxes (A5).
