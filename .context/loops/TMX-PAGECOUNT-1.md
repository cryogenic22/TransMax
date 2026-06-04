# TMX-PAGECOUNT-1 — Real PDF page count (not block/segment count)

**State**: `[Verify]`  ·  **Owner**: Document Pipeline  ·  **Sprint**: 2  ·  Batch-3 loop 1/10 (2026-06-04)
**Reversibility**: `two-way`. **G2**: reproduced — the real NEJM PDF returned `count_pages == 13` (was shown as 316). **Blast radius**: `app/services/pdf_service.py` (+`count_pages`), `app/api/documents.py` (upload uses it).

## 1. Task
User-visible defect: the upload card showed "316 segments · 7982 words · **316 pages**" for a 13-page PDF. Cause: `documents.py` set `page_count=len(blocks)` — the block/segment count, not pages. Report the real page count. Addenda A3 (don't show a wrong number to users), A5-adjacent (accurate doc metadata).

## 2. Spec
- [x] AC-1: `PDFService.count_pages(path)` returns the real PDF page count (pypdf), min 1.
- [x] AC-2: malformed/non-PDF input → falls back to 1, never raises, never reports a segment count.
- [x] AC-3: upload sets `page_count` from `count_pages` for PDFs (DOCX stays 1 — no fixed page count without rendering).
- [x] AC-4: verified on the real file — 13, not 316.

Out of scope: DOCX/PPTX true page count (needs rendering); backfilling already-ingested docs (applies to new uploads).

## 3. Design
`count_pages` reads `len(pypdf.PdfReader(fh).pages)` (lightweight, already a dep), guarded (→1 on error). `documents.py` upload calls it for `.pdf`. Word/segment counts unchanged.

## 4. Code
| File | Change |
|---|---|
| `app/services/pdf_service.py` | +`count_pages(file_path)` (pypdf, guarded) |
| `app/api/documents.py` | `page_count = ingest_service.count_pages(file_path)` for PDF (was `len(blocks)`) |
| `tests/test_page_count.py` | new — 3 tests (5-page, 1-page, bad-file fallback) |

## 5. Test
`pytest tests/test_page_count.py` → 3 passed. Live check on the NEJM PDF → 13. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Guarded fallback (→1) so a corrupt PDF never breaks upload or shows a wrong huge number.
- DOCX left at 1 (honest — Word page count is render-dependent); could estimate from word_count later (spawned).
- Existing mis-counted docs aren't backfilled — new uploads correct; a backfill is optional follow-up.

## 7. Fix
Reworded a "bug"→"defect" docstring (TODO-meter). No code findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 3 tests
- [ ] Commit / push (after full suite)
### Spawned
- **TMX-PAGECOUNT-1a** — DOCX/PPTX page estimate (word-based) + optional backfill of existing docs.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~04:15Z | — | `[Verify]` | count_pages + upload wiring; 3 tests; real file = 13; ratchet 17/17; awaiting full suite |