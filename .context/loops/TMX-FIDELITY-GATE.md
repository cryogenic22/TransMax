# TMX-FIDELITY-GATE — Fail-loud structural gate in DOCX export

**State**: `[Verify]`  ·  **Owner**: Document Pipeline  ·  **Sprint**: 2  ·  Batch-3 loop 4/10 (2026-06-04)
**Reversibility**: `two-way` (opt-out via `enforce_fidelity=False`). **Blast radius**: `app/services/fidelity.py` (+`structural_loss`), `app/services/document_export.py` (gate in `export_docx`).

## 1. Task
Turn FIDELITY-EVAL's comparator into a runtime guard: the DOCX round-trip export now compares the output's structural skeleton (tables/figures/headings) to the original and raises `FidelityError` if any were dropped — so a buggy export can't silently ship a degraded document. Addenda A3 (fail loud, never ship structural loss).

## 2. Spec
- [x] AC-1: `structural_loss(src, out)` reports skeleton dims (tables/images/headings) where output < source; ignores bold/italic (text-redistribution shifts those legitimately).
- [x] AC-2: `export_docx` (round-trip path) raises `FidelityError` if the skeleton shrank; `enforce_fidelity=False` opts out.
- [x] AC-3: a faithful round-trip (text replaced, structure intact) does NOT raise (no false positive) — verified on a rich fixture + the identity eval.

Out of scope: gating the PDF flat-fallback path (no original DOCX skeleton to compare — RECON loops will give PDF a structure to preserve, then this gate extends to it).

## 3. Design
Snapshot `structure_fingerprint(doc)` right after opening the original (skeleton baseline), run the in-place text replacement, fingerprint again, and `structural_loss` the two. Only the skeleton (tables/images/headings) is gate-failing — those can't change from text replacement, so a loss is unambiguously an export defect; bold/italic run counts can shift when text redistributes across runs, so they're excluded. Raise on loss.

## 4. Code
| File | Change |
|---|---|
| `app/services/fidelity.py` | +`structural_loss(src, out)` (skeleton-only) + `_SKELETON_DIMS` |
| `app/services/document_export.py` | `export_docx` snapshots skeleton, gates after mutation, raises `FidelityError`; `enforce_fidelity` param |
| `tests/test_fidelity_gate.py` | new — 3 tests (loss flagged, preserved → none, faithful round-trip passes) |

## 5. Test
`pytest test_fidelity_gate + evals/fidelity` → 7 passed (faithful round-trips pass the gate — no false positive). Ratchet 17/17. Full suite — stage 8.

## 6. Red team
- Skeleton-only gating avoids false positives from bold/italic run shifts (verified: faithful round-trip + identity eval both pass).
- Opt-out param for edge cases; default-on so the protection is real.
- PDF flat path not gated yet (no DOCX skeleton baseline) — honest scope; RECON loops extend it.
- The gate raises mid-export; callers (export endpoints / job) surface it as a fail-loud error rather than a silent degraded download (A3).

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17 · 7 tests
- [ ] Commit / push (after full suite)

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-04T~05:30Z | — | `[Verify]` | structural_loss + export gate; 3 tests; faithful round-trip passes; ratchet 17/17; awaiting full suite |