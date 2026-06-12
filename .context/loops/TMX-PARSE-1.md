# TMX-PARSE-1 — Pluggable document-parser backends behind a canonical IR (Docling + Azure/Google connectors)

**State**: `[Done]`
**Owner**: Document Pipeline
**Sprint**: 2 · **Started**: 2026-06-12
**Reversibility**: `two-way` — new `app/services/parsing/` package, additive; default backend keeps current pypdf behaviour; live upload route NOT re-wired this loop. ADR-0005.
**Pre-mortem**: if this fails in production, a parser backend silently returns a worse/empty extraction and a reviewer translates a structurally-degraded document believing it faithful — so backends MUST fail loud, never silently downgrade (A3).
**Blast radius**: new `app/services/parsing/*`; `app/core/config.py` (+2 settings); `requirements.txt` (tokenizers pin). No change to the live ingestion path in this loop.

**Gates**: G1 — net-new package is justified (real, measured fidelity gap; registry has >1 backend; ships with tests). G2 — N/A (greenfield capability, not a bug repro) — but the A/B eval reproduces the pypdf fidelity loss as the motivating evidence. G3 — backends produce the canonical IR; connectors fail loud; default behaviour unchanged.

## 1. Task
PDF ingestion is lossy (pypdf flat text; `unstructured` not even loading). Build a pluggable parser-backend layer with a canonical IR so PDF structure recovery is a config-selected backend swap. Docling is the default target; Azure Document Intelligence + Google Document AI ship as fail-loud connectors. Per ADR-0005.

## 2. Spec — acceptance criteria
- [ ] AC-1: a canonical `ParsedDocument`/`ParsedBlock` IR with a canonical `ElementType` enum + `to_legacy_blocks()` emitting the existing `{"text","type","meta"}` shape (backward-compatible drop-in for `app/api/documents.py`).
- [ ] AC-2: a registry + `get_parser(name=None)` factory selecting by `settings.parser_backend`; an unknown name raises a clear error (A3, no silent default-to-worse).
- [ ] AC-3: `pypdf` backend produces a `ParsedDocument` (always available; the fallback).
- [ ] AC-4: `docling` backend maps Docling labels → canonical `ElementType` (section_header→SECTION_HEADER, list_item→LIST_ITEM, table→TABLE, picture→FIGURE, footnote→FOOTNOTE, caption→CAPTION, page_header/footer); import-guarded → `ParserUnavailable` if Docling can't load.
- [ ] AC-5: `azure` + `google` backends raise `ParserUnavailable` (NOT silent fallback) when their SDK/credentials are absent.
- [ ] AC-6: default `parser_backend="pypdf"` → the live pipeline is byte-for-byte unchanged this loop.
- [ ] AC-7: an opt-in A/B eval script captures the pypdf-vs-docling structural delta on a sample PDF.

Out of scope (explicit follow-ups): wiring the registry into the upload route behind a flag (TMX-PARSE-2); extending the FidelityGate to the PDF→DOCX path (TMX-PARSE-3); XLSX/PPTX backends (TMX-PARSE-XLSX/PPTX); DocLang serialization (TMX-PARSE-DOCLANG); real Azure/Google credential wiring (TMX-PARSE-AZURE/GOOGLE).

## 3. Design
See ADR-0005. Canonical IR is the single source of truth; backends normalise into it; downstream reads only the IR. `config not branching` — registry keyed by name. Connectors fail loud (A3). Docling pinned via `tokenizers<0.22`.

## 4. Code
| File | Change |
|---|---|
| `app/services/parsing/base.py` | IR (`ParsedBlock`/`ParsedDocument`/`ElementType`) + `DocumentParser` protocol + `ParserUnavailable` |
| `app/services/parsing/registry.py` | backend registry + `get_parser()` |
| `app/services/parsing/pypdf_backend.py` | wrap existing pypdf extraction |
| `app/services/parsing/docling_backend.py` | Docling → IR (import-guarded) |
| `app/services/parsing/azure_backend.py` | Azure DI connector (fail-loud) |
| `app/services/parsing/google_backend.py` | Google Document AI connector (fail-loud) |
| `app/core/config.py` | `parser_backend`, `parser_ocr_enabled` |
| `scripts/parse_ab.py` | opt-in pypdf-vs-docling A/B on a sample PDF |
| `tests/test_parsing_backends.py` | AC-1..AC-6 |
| `requirements.txt` | `tokenizers<0.22` pin note |

## 5. Eval / Test
- `pytest tests/test_parsing_backends.py` → 12 passed (IR + legacy adapter; registry lists 4 + unknown→loud; default=pypdf; pypdf faked-reader IR; docling label-map + import-guard→ParserUnavailable; azure/google fail-loud without SDK).
- Full backend suite **1172 passed** / 2 skipped / 0 failed (was 1160 + 12). Ratchet 17/17. Import smoke confirms `get_parser()` loads WITHOUT importing torch/docling (lazy factories).
- **A/B on the real bermejo PDF** (`scripts/parse_ab.py`, captured at `docs/audit-extracts/parse-ab-bermejo-2026-06-12.md`): pypdf → 1 element type, 0 tables, 0 figures; **docling → 7 types, 4 tables, 30 figures**, 42s (OCR off), no mojibake.

## 6. Red team
- **A3 fail-loud verified**: azure/google → `ParserUnavailable` when SDK absent; docling → `ParserUnavailable` on import/init failure; unknown name → `ParserError`. No silent downgrade path exists.
- **Default unchanged**: live upload route untouched; `parser_backend="pypdf"`; new package dormant until TMX-PARSE-2. Fully reversible.
- **Lazy imports**: registry factories are lazy → importing the package never pulls torch/docling (confirmed). Critical so the app start-up isn't taxed.
- **Docling API drift**: every Docling access is defensive (try/except getattr) so a version bump degrades, not crashes.
- **Connectors not live-verified**: Azure/Google mapping is written to documented SDK shapes but NOT run against real APIs (no creds) — only the interface + fail-loud are proven. Honest scope; live tests are TMX-PARSE-AZURE/GOOGLE.
- **NEW governance finding (pharma)**: enabling `azure`/`google` SENDS the document to a third-party cloud — PHI/PII leaves the trust boundary. That is an A6 qualified-supplier + data-residency decision (DPA, EU region, tenant opt-in), NOT a default. Spawned **TMX-PARSE-CLOUD-GOVERNANCE**.

## 7. Fix
- Docling `TableItem.export_to_dataframe()` deprecation → now passes `ddoc` (with a `TypeError` fallback for older Docling). Re-ran A/B clean.
- No other findings.

## 8. Deploy
- [ ] Commit: <SHA>
- [x] active_tasks updated

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-12 | — | `[WIP]` | ADR-0005 written; code in progress |
| 2026-06-12 | `[WIP]` | `[Done]` | 7 modules + tests + A/B evidence; suite 1172 green; ratchet 17/17 |
