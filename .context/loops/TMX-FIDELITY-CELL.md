# TMX-FIDELITY-CELL — DOCX export drops single-paragraph table-cell text

**State**: `[Done]`
**Owner**: Document Pipeline
**Sprint**: 2
**Started**: 2026-06-13
**Closed**: 2026-06-13
**Reversibility**: `two-way` — one-line predicate change + regression test; revert by restoring proxy-identity check.
**Pre-mortem**: if this is wrong in production, every translated DOCX with tables ships with empty cells while the table grid survives — silent regulatory data loss the FidelityGate does not catch (A3 worst-case).
**Blast radius**: `app/services/document_export.py` (`_replace_cell_text`), one test file. Affects every DOCX round-trip export that contains a single-paragraph table cell — i.e. essentially all pharma SmPC/CSR tables.

**Loop-driven-dev gates:**
- [x] **G1 Anti-bloat** — not net-new code; fixes an existing path. Ships with a test that fails without the change.
- [x] **G2 Reproduce-the-failure** — `test_table_cell_text_is_translated_on_export` is RED on the proxy-identity code, GREEN after the element-identity fix.
- [x] **G3 Completion** — source code changed (not tests-only); a real translated DOCX/PDF now carries populated French table cells (verified visually).

---

## 1. Task

Surfaced by a live end-to-end test (EN→FR SmPC, real `gpt-4o`, fidelity export → Word→PDF): the translated table came back with grid + shading intact but **every cell empty**. `DocumentExportService._replace_cell_text` cleared the paragraph it had just translated. A3 (no silent degradation in regulated artefacts) + A5 (stable structure end-to-end) at play.

## 2. Spec — acceptance criteria

- [x] AC-1: after `export_docx`, a single-paragraph table cell contains the translated text (not empty, not the source).
- [x] AC-2: a regression test asserts cell *content* post-export (the prior suite only asserted body-paragraph content and cell *ingestion*).
- [x] AC-3: no regression across DOCX + fidelity suites.

Out of scope: the multi-paragraph cell branch (already iterates the original `paras` list, not `cell.paragraphs`, so it was unaffected); the FidelityGate content-awareness gap (see follow-up).

## 3. Design

Root cause: `cell.paragraphs` returns a freshly-built `Paragraph` proxy on every access. The "clear OTHER paragraphs" loop compared proxy identity (`p is not paras[0]`), which is always `True`, so it wiped the run it had just written. Fix: compare the underlying XML element (`p._p is not paras[0]._p`). One-line, surgical; matches how python-docx identity must be tested everywhere else.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/document_export.py` | ~401-411 | proxy-identity → element-identity (`._p`) in `_replace_cell_text` single-paragraph branch + explanatory comment |
| `tests/test_docx_roundtrip.py` | +28 | `test_table_cell_text_is_translated_on_export` regression (red without fix) |

## 5. Eval / Test

```
pytest tests/test_docx_roundtrip.py -k translated_on_export   # green with fix
# temporarily revert fix -> RED (tests/test_docx_roundtrip.py:149 AssertionError)
pytest tests/test_docx_roundtrip.py tests/test_fidelity_gate.py tests/test_docx_revisions.py \
       tests/test_recon_headings.py tests/evals/fidelity/test_docx_fidelity.py
```

```
1 passed (regression) ; 1 failed when fix reverted ; 34 passed (full DOCX+fidelity sweep)
```

## 6. Red team

- The FidelityGate did NOT catch this — it checks structural *presence* (table exists) not cell *content*. That gap is real but separate; filed **TMX-FIDELITY-GATE-CONTENT** (assert non-empty translated content for matched source blocks).
- Merged cells: handled earlier in `_export_table` via `seen_tcs` dedup; unaffected (still single-paragraph path).
- Empty/whitespace cells: `_match_translation` returns None → cell untouched; correct.
- The same proxy-vs-element identity trap exists nowhere else in this file (grepped) — multi-paragraph branch iterates the captured `paras` list.

## 7. Fix

No further findings — the one-line change is the fix; regression locks it.

## 8. Deploy

- [x] Commit: `1f9176b` (local; push Kapil-gated)
- [ ] CI green: pending push (Kapil-gated)
- [x] `.context/active_tasks.md`: to be referenced in next backlog sync
- [ ] Ratchet: N/A (no new module)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-13 | — | `[Done]` | Found via live EN→FR fidelity test; root-caused to proxy-identity check; fixed + regression. Awaiting commit SHA + push. |
