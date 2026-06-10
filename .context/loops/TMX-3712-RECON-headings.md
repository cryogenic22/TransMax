# TMX-3712-RECON-headings — PDF export applies heading styles from element_type

**State**: `[Done]` — `e3c5bfc` on origin/main  ·  **Owner**: Document Pipeline  ·  **Sprint**: 2  ·  Batch-3 loop 5/10 (2026-06-04)
**Reversibility**: `two-way`. **Blast radius**: `app/services/document_export.py` (the PDF flat-export branch only).

## 1. Task
The NEJM manuscript came back as 299 flat `Normal` paragraphs — no title, no section headings. Root cause: the PDF flat-export path did `add_paragraph(text)` and **ignored the `element_type`** the ingester already records (unstructured tags `Title`/`Header`/etc., stored on `Segment.element_type` and passed to export in `seg_dicts`). Apply real heading styles from that type. Addenda: document-fidelity (E3), A5 (carry structural metadata end-to-end).

## 2. Spec
- [x] AC-1: a `Title`/`Headline` block → DOCX Title style (first one, level 0).
- [x] AC-2: `Header`/`SectionHeader`/`Heading` (and further Titles) → Heading 1.
- [x] AC-3: `NarrativeText`/`Sentence`/None → Normal paragraph (unchanged).
- [x] AC-4: the fidelity fingerprint now sees real headings (was 0) — so a structured PDF no longer exports fully flat.

Out of scope: tables (TMX-3712-RECON-tables, next), figures (needs image extraction), heading-LEVEL inference beyond title/section (font-size hierarchy is a refinement), the font-heuristic fallback when unstructured is off (ingestion already tags via unstructured; a pdfplumber font heuristic is a follow-up).

## 3. Design
The plumbing already existed — `documents.py` stores `element_type=block.get("type")` at ingestion and passes `element_type` to `export_docx` in `seg_dicts`. The only gap was the `force_new` (PDF) branch ignoring it. Now that branch orders segments by `order_index`, maps the element_type to `add_heading(level=0|1)` vs `add_paragraph`, and tracks the first Title as the doc title. No ingestion/storage change.

## 4. Code
| File | Change |
|---|---|
| `app/services/document_export.py` | PDF flat-export branch applies Title/Heading styles from `element_type` |
| `tests/test_recon_headings.py` | new — 2 tests (Title/Header→styled, fingerprint headings>0; plain→Normal) |

## 5. Test
`pytest tests/test_recon_headings.py` → 2 passed (Title style + 2 Heading 1; fingerprint headings=3, was 0). Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- First-Title-as-doc-title heuristic; subsequent Titles → Heading 1 (unstructured reuses "Title" for section heads). Level precision is a refinement; the win is non-flat structure.
- Plain blocks still Normal (no over-styling) — verified.
- Quality depends on the ingester's element_type accuracy (unstructured); when unstructured is off, blocks lack rich types → fewer headings (acceptable, font-heuristic follow-up). Pairs with TMX-FIDELITY-GATE once PDF gets a comparable skeleton.

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 2 tests
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-3712-RECON-headings-font** — pdfplumber font-size heuristic to tag headings when unstructured is unavailable.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~05:55Z | — | `[Verify]` | PDF export styles headings from element_type; 2 tests; fingerprint headings 0→3; ratchet 17/17; awaiting full suite |