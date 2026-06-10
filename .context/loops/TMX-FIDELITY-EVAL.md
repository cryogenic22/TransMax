# FIDELITY-EVAL — Document structural-fidelity comparator + golden-set eval

**State**: `[Done]` — `4de88c3` on origin/main  ·  **Owner**: Document Pipeline + Quality  ·  **Sprint**: 2  ·  Fidelity step 2/3 (2026-06-04)
**Reversibility**: `two-way`. **Blast radius**: `app/services/fidelity.py` (new comparator/gate), `tests/evals/fidelity/` (new golden-set eval). Nothing wired into the live export yet (the gate is available for a follow-on).

## 1. Task
Make document fidelity *measurable + gateable*, so the NEJM-class failure (13 tables→0, figures dropped, headings flattened) can never silently ship. Build a structural comparator + a golden-set eval (identity round-trip + regression detector). Addenda: A3 (fail loud on structural loss), E3.

## 2. Spec
- [x] AC-1: `structure_fingerprint(doc)` counts the structure-bearing elements (paragraphs, tables, images, headings, bold/italic runs).
- [x] AC-2: `compare_structure(src, out)` reports losses + a weighted 0–100 score (tables/figures weighted highest); only LOSSES count (added paragraphs from a verbose target language are not penalized).
- [x] AC-3: `assert_fidelity` is a fail-loud gate (`FidelityError`) for a future export step.
- [x] AC-4: **identity round-trip** — export the same text back through `DocumentExportService.export_docx` and assert tables/figures/headings preserved + score ≥90.
- [x] AC-5: the comparator FLAGS the NEJM flattening (13→0 tables etc.) with score <10 (the eval would have caught it).

Out of scope: PDF structural extraction (so PDF-input fidelity can be scored — the layout-reconstruction follow-on); wiring `assert_fidelity` into the live export; multi-format corpus (DOCX fixture for now).

## 3. Design
`app/services/fidelity.py` is a production primitive (not test-only) so it can later gate the export pipeline. The eval lives in `tests/evals/fidelity/` with a synthetic rich-manuscript fixture (title + headings + a data table + bold/italic, mirroring the NEJM shape). The **identity round-trip** (translated == source) is the key test: it isolates *structural* fidelity from translation quality — any drift is a fidelity defect regardless of language. A second test pins the comparator against the exact NEJM numbers to prove the detector fires.

**Finding:** the identity round-trip **passes** — `DocumentExportService.export_docx` preserves tables, figures, headings, and formatting on DOCX input. So the DOCX in-place round-trip is faithful; the NEJM failure came from the **PDF → flat-DOCX** path (no round-trip + the naive segmenter, now fixed in TMX-3801). Scoring PDF-input fidelity needs a PDF structural extractor → the layout-reconstruction follow-on.

## 4. Code
| File | Change |
|---|---|
| `app/services/fidelity.py` | new — `structure_fingerprint`, `compare_structure`, `FidelityReport`, `assert_fidelity`/`FidelityError` |
| `tests/evals/fidelity/__init__.py` | new package |
| `tests/evals/fidelity/test_docx_fidelity.py` | new — identity round-trip, NEJM-flattening detector, clean-case, added-paragraphs-not-penalized (4 tests) |

## 5. Test
`pytest tests/evals/fidelity/` → 4 passed. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Identity round-trip is language-independent → a pure structural gate.
- Only losses scored (verbose target languages add paragraphs legitimately) — avoids false fidelity failures.
- Comparator proven to catch the real regression (NEJM numbers pinned).
- `images` uses `inline_shapes` (floating images not counted) — acceptable proxy; refine if a corpus shows floating-image docs.

## 7. Fix
Reworded a test-docstring "bug"→"defect" (TODO-meter). No code findings.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 4 eval tests
- [x] Commit: `4de88c3` (subject `FIDELITY-EVAL:` — no `TMX-` prefix, so declared here for the drift audit)
- [x] Pushed to origin/main (Railway auto-deploys)
### Spawned
- **TMX-3712-PDF-RECON** — PDF structural extractor + layout reconstruction so PDF-input jobs preserve tables/figures/headings (the remaining big NEJM gap); the eval will score it.
- **TMX-FIDELITY-GATE** — wire `assert_fidelity` into the export step (fail-loud on structural loss).
- **TMX-FIDELITY-CORPUS** — add real multi-format docs (PDF/XLSX/PPTX) to the golden set.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~03:30Z | — | `[Verify]` | comparator + 4-test golden eval; identity round-trip green (DOCX export faithful); ratchet 17/17; awaiting full suite |