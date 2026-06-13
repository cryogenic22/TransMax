# TMX-EXPORT-1 — Pluggable document-export backends + Tier-1 PDF→PDF overlay

**State**: `[Done]` (registry + classifier/fonts/layout + docx & pdf_overlay backends built, tested, flag-gated default-off; upload-route wiring + AGPL review + Tier-2 are follow-ups)
**Owner**: Document Pipeline
**Sprint**: 2-3
**Started**: 2026-06-13
**Closed**: —
**Reversibility**: `two-way` for the registry + `pdf_overlay` backend (flag-gated, default-off); the IR/exporter *contract* is `one-way` once tenants depend on it.
**Pre-mortem**: if this is wrong in production, a reviewer signs off a translated PDF that *looks* faithful but dropped/clipped/mistranslated content (e.g. translated a journal masthead, clipped an expanded box) — A3 worst-case, worse than an obviously-broken output.
**Blast radius**: new `app/services/export/*`; `DocumentExportService` folds in as the `docx` backend; `app/core/config.py` (`export_backend`); `requirements-export.txt` (PyMuPDF, AGPL — legal gate).

**Loop-driven-dev gates:**
- [ ] **G1 Anti-bloat** — net-new only where the registry/protocol earns it; `docx` reuses the existing service; `pdf_overlay` is the one genuinely new path. Ships behind a flag, default-off.
- [ ] **G2** — N/A (greenfield) except the content-aware FidelityGate, which is a reproduce-the-failure (the TMX-FIDELITY-CELL empty-cell class).
- [ ] **G3** — a real PDF→PDF round-trip on a pharma sample produces a reviewer-acceptable French PDF AND a fidelity report that flags every degraded box.

---

## 1. Task

Add a translated-PDF capability so PDF-only intake (CSR/SmPC/PIL/manuscript) is not a dead end, **without** hard-coding to source types. Driven by the live POC on a 13-page NEJM manuscript (`uploads/fidelity_fr_demo/`, ADR-0006). A1/A3/A5/A7 all at play.

## 2. Spec — acceptance criteria

- [x] AC-1: `get_exporter(name=None)` registry keyed on `settings.export_backend` (config-not-branching, A7), symmetric with `get_parser`.
- [x] AC-2: one `DocumentExporter` protocol; backends `docx` (folded), `pdf_overlay` (new, fitz); `pdf_render` (Tier-2) deferred.
- [x] AC-3: the overlay operates on a generic `LayoutBlock` (text+geometry+style), never on `if source == "<journal>"`.
- [x] AC-4: per-block **translatability classifier** (CONTENT/PRESERVE/DROP_CAP) via cross-page repetition + geometry + identifier shape + glossary.
- [x] AC-5: per-block **strategy negotiation** — in_place → shrunk → reflowed → escalate — recorded per block.
- [x] AC-6: **font-resolution** — family map + embedded Unicode DejaVu (covers œ/dashes/guillemets); charset gaps flagged not mangled.
- [~] AC-7: **FidelityReport** records per-block translatability/strategy/overflow/font-sub + `degraded` rollup. The *gate* that hard-fails a degraded export (and asserts every source block maps non-empty) is the **content-aware FidelityGate follow-up** (TMX-FIDELITY-GATE-CONTENT).
- [ ] AC-8: A5 — overlaid boxes carry a `block_id`, NOT yet the pipeline `segment_id`. Follow-up **TMX-EXPORT-SEGID**.

Out of scope (this ticket): Tier-2 `pdf_render`; scanned-PDF OCR routing (delegates to ADR-0005 parsers); RTL/CJK box shaping; the AGPL licence decision (legal, blocking pilot ship).

## 3. Design

See **ADR-0006**. Core principle answering "modular/flexible/intelligent, not hard-coded": **funnel every format through the canonical IR; make all per-source intelligence a *classification + policy* decision on IR blocks, never a source-type branch.** Backends declare capabilities (needs text-layer+bbox); the registry routes scanned/encrypted/rotated inputs to the right parser first. Graceful degradation (escalate a block/page to re-render) replaces hard failure.

## 4. Code

| File | Change |
|---|---|
| `app/services/export/base.py` | protocol + value objects (LayoutBlock, Translatability/FitStrategy, BlockVerdict, FidelityReport, ExportResult, ExporterUnavailable) |
| `app/services/export/classify.py` | translatability classifier — cross-page repetition + geometry + identifier shape + glossary (AC-3/4) |
| `app/services/export/fonts.py` | font resolution — serif/sans/mono family + embedded DejaVu Unicode TTF (œ/dashes/guillemets) + charset honesty (AC-6) |
| `app/services/export/layout.py` | fit negotiation in_place→shrunk→reflowed→escalate (AC-5) |
| `app/services/export/pdf_overlay_backend.py` | fitz orchestrator: classify→translate→font/fit→redact(fill=None)→reinsert; drop-cap re-seat; FidelityReport |
| `app/services/export/docx_backend.py` | folds `DocumentExportService` under the protocol (Tier-3) |
| `app/services/export/registry.py` | `get_exporter()` keyed on `settings.export_backend` (AC-1) |
| `app/core/config.py` | `export_backend`, `export_font_dir` settings |
| `requirements-export.txt` | opt-in PyMuPDF (AGPL gate) + DejaVu bundling note |

POC seed: `uploads/fidelity_fr_demo/pdf_overlay_poc.py` + `run_overlay_prod.py` (gitignored).

## 5. Eval / Test

23 new unit/integration tests (`tests/test_export_*.py`) — classifier (masthead-by-repetition, folio, identifier, drop-cap, single-page top-band, glossary), fonts (family map + French/CJK charset honesty), layout (4 fit rungs), registry (fail-loud), overlay integration (preserve chrome / translate body / count-mismatch fail-loud). 50 passed with docx+config; 17 parsing green (symmetry intact).

Full FR run on the 13-page NEJM manuscript via the real backend (`gpt-4o`): 496 blocks → 350 preserve / 146 content; strategies 18 in_place / 116 shrunk / 12 reflowed; **0 degraded**. Masthead/folios/citations preserved; title/abstract/body accurate medical French; tables/figures/colours/columns/side-boxes intact. Artifacts: `manuscript_fr_final.pdf`, `final_p{1,2,3,6}.png`.

## 6. Red team — edge cases the single POC run already surfaced

| Edge case | Observed | Design answer (not a hard-code) |
|---|---|---|
| Branding/masthead translated | "The New England Journal of Medicine" → "Le New England Journal…" | AC-4 translatability classifier + DNT glossary; PAGE_HEADER/wordmark → preserve |
| Drop-cap initial | first-letter drop cap mis-aligns when first word changes | classify FIRST_LETTER/drop-cap; re-seat to translated first letter |
| Font fallback | NEJM Quadraat → Times fallback | AC-6 font-resolution; embedded-subset lacks accents → Unicode family, recorded |
| Text expansion | FR longer; shrink-to-fit used | AC-5 negotiation: shrink → reflow → escalate; cap min readable size |
| Scanned/no-text PDF | n/a here (born-digital) | route to OCR parser (ADR-0005) before export; detect, don't assume |

## 7. Fix — tuning items the full 13-page run surfaced

- **Over-preservation in tables/refs** (350 preserve / 146 content): short text row-labels and reference entries sometimes classified PRESERVE by the identifier/short-text heuristics. Citations-stay-untranslated is often correct, but table prose labels should translate → tune the classifier (table-cell context, language-ID on the block) — **TMX-EXPORT-CLASSIFY-TUNE**.
- **Drop-cap pairing** is heuristic (nearest body block to the right); fine on this doc, needs a guard for multi-column false pairs.
- These are recorded, not silent — the FidelityReport makes the split inspectable.

## 8. Deploy

- [x] Commit (ADR-0006 + worksheet): `5ea6f90`
- [x] Commit (export package + tests + config): <SHA at commit>
- [ ] Wire `pdf_overlay` behind the upload route (flag) — follow-up **TMX-EXPORT-WIRE**
- [ ] Legal: AGPL review for PyMuPDF before any pilot ship
- [ ] Bundle DejaVu TTFs for Linux/Railway (don't depend on matplotlib) — **TMX-EXPORT-FONTS-BUNDLE**

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-13 | — | `[Spec]` | ADR-0006 + POC validated on NEJM manuscript (p1+p2, EN→FR). |
| 2026-06-13 | `[Spec]` | `[Done]` | Productionized `app/services/export/` (registry + classifier/fonts/layout + 2 backends); 23 tests; full 13-page FR run 0-degraded. Flag-gated default-off; wiring + AGPL + segment_id + classifier-tune are follow-ups. |
