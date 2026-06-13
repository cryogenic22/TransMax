# TMX-EXPORT-1 — Pluggable document-export backends + Tier-1 PDF→PDF overlay

**State**: `[Spec]` (ADR-0006 accepted in principle; POC validated; productionization not yet built)
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

- [ ] AC-1: `get_exporter(name=None)` registry keyed on `settings.export_backend` (config-not-branching, A7), symmetric with `get_parser`.
- [ ] AC-2: one `DocumentExporter` protocol; backends `docx` (fold existing), `pdf_overlay` (new, fitz), `pdf_render` (Tier-2, later).
- [ ] AC-3: the overlay operates on the **canonical IR** (ADR-0005) + geometry, never on `if source == "<journal>"`.
- [ ] AC-4: a per-block **translatability classifier** (content vs chrome/branding/identifier/DNT-glossary) so mastheads/running-heads/trademarks are preserved, not translated.
- [ ] AC-5: per-block **strategy negotiation** — in-place → reflow-in-box → escalate-to-render — with a recorded reason; never silently clip (A3).
- [ ] AC-6: **font-resolution** layer — reuse embedded face if it covers the target charset, else nearest Unicode-complete family; substitution recorded in provenance.
- [ ] AC-7: content-aware **FidelityGate** — every source block maps to a non-empty target box; overflow/clip/DNT-skip flagged in a fidelity report.
- [ ] AC-8: A5 — each overlaid box carries its `segment_id`.

Out of scope (this ticket): Tier-2 `pdf_render`; scanned-PDF OCR routing (delegates to ADR-0005 parsers); RTL/CJK box shaping; the AGPL licence decision (legal, blocking pilot ship).

## 3. Design

See **ADR-0006**. Core principle answering "modular/flexible/intelligent, not hard-coded": **funnel every format through the canonical IR; make all per-source intelligence a *classification + policy* decision on IR blocks, never a source-type branch.** Backends declare capabilities (needs text-layer+bbox); the registry routes scanned/encrypted/rotated inputs to the right parser first. Graceful degradation (escalate a block/page to re-render) replaces hard failure.

## 4. Code

POC seed: `uploads/fidelity_fr_demo/pdf_overlay_poc.py` (NOT committed; gitignored). Productionization → `app/services/export/{registry,base,docx_backend,pdf_overlay_backend}.py`.

## 5. Eval / Test

POC run (real `gpt-4o`, FR): NEJM p1 (title/structured-abstract/side-box) + p2 (2-col body, red section heading) — masthead/colours/columns/footnotes/side-box preserved; title + abstract accurate medical French. Artifacts: `manuscript_fr_overlay.pdf`, `fr_p1_hi.png`, `fr_p2_hi.png`.

## 6. Red team — edge cases the single POC run already surfaced

| Edge case | Observed | Design answer (not a hard-code) |
|---|---|---|
| Branding/masthead translated | "The New England Journal of Medicine" → "Le New England Journal…" | AC-4 translatability classifier + DNT glossary; PAGE_HEADER/wordmark → preserve |
| Drop-cap initial | first-letter drop cap mis-aligns when first word changes | classify FIRST_LETTER/drop-cap; re-seat to translated first letter |
| Font fallback | NEJM Quadraat → Times fallback | AC-6 font-resolution; embedded-subset lacks accents → Unicode family, recorded |
| Text expansion | FR longer; shrink-to-fit used | AC-5 negotiation: shrink → reflow → escalate; cap min readable size |
| Scanned/no-text PDF | n/a here (born-digital) | route to OCR parser (ADR-0005) before export; detect, don't assume |

## 7. Fix

Pending productionization.

## 8. Deploy

- [ ] Commit (ADR-0006 + this worksheet): <SHA>
- [ ] Backend build: follow-up loop
- [ ] Legal: AGPL review for PyMuPDF before any pilot ship

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-13 | — | `[Spec]` | ADR-0006 + POC validated on NEJM manuscript (p1+p2, EN→FR). Productionization scoped; edge-case backlog captured. |
