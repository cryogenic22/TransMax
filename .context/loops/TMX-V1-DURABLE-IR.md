# TMX-V1-DURABLE-IR — stop the lossy v1 output rebuild (ADR-0008 hazard 2, half 1)

**State**: `[Verify]`
**Owner**: Document Pipeline
**Sprint**: —
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way`
**Pre-mortem**: if this fails in production, a reviewer reads a fabricated ". " inside a
regulated translated artefact (e.g. a title merged into body prose with an invented period,
or a question mark followed by a phantom ". ") and signs off content that misrepresents the
source's structure — silent corruption per A3, not a crash, so nothing alerts anyone.
**Blast radius**: `app/api/v1/translations.py` only (`get_job_result` / `/result` route +
one new pure helper `_reconstruct_document_text`); one new test file. Does not touch
`app/agents/graph.py`, `app/services/document_export.py`, or the durable-worker/checkpointer
half (TMX-ORCH-CHECKPOINT Loop B — one-way, explicitly out of scope here).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — the reconstruction logic is extracted as one pure function inside
  the existing route module (no new module/service/table). It has exactly 1 caller today
  (`get_job_result`), reuses the `Segment.element_type` field FEATURE-5 already added, and
  ships with a red test that failed against the current join (see stage 5).
- [x] **G2 Reproduce-the-failure** — red test written and run against a byte-for-byte stub
  of the old `". ".join(...)` behaviour before the real fix landed; all 7 assertions failed
  on genuine logic (see stage 5 verbatim output), not an import/collection error.
- [x] **G3 Completion** — `get_job_result` now calls `_reconstruct_document_text`; the same
  red test that failed pre-fix passes post-fix; the fabricated ". " a regulated reviewer
  would previously have seen no longer appears.

---

## 1. Task

`app/api/v1/translations.py::get_job_result` (the `/result` endpoint) rebuilt a job's full
translated text with `". ".join(s.translated_text or "" for s in segments)`. This discards
each segment's own terminal punctuation (a source segment ending in "?" or ":" comes back
with a fabricated ". " glued on) and flattens all DOCX structural roles recorded on
`Segment.element_type` (Header, Paragraph, TableCell, ...) into one run of prose. For
regulated content this is silent corruption of the artefact (A3) — the reviewer is shown
text the engine never produced. ADR-0008 (hazard 2) calls this out explicitly and splits it
into two tickets: this one (the two-way "reconstruct from the IR" half) and
TMX-ORCH-CHECKPOINT Loop B (the one-way durable-worker half, NOT touched here).

Addenda at play: **A3** (no silent fallbacks / no invented content in a regulated artefact —
the core of this ticket), **A5** (segment IDs/order are the source of truth; reconstruction
must use `order_index` and per-segment data, never re-derive structure from a flat join),
**A9** (no code path here deletes anything, N/A but noted for completeness).

## 2. Spec — acceptance criteria

- [x] AC-1: A document whose segments end in varied terminal punctuation ("?", ":", ".", no
      punctuation) reconstructs with each segment's own terminator intact and **no**
      fabricated ". " inserted between segments that already carry their own terminator.
- [x] AC-2: A document whose segments carry distinct `element_type` values (e.g. "Header" vs
      "Paragraph") reconstructs with the structural boundary preserved (a line break), not
      folded into flat prose with an invented period.
- [x] AC-3: A segment with no translated text (empty/`None`) is skipped rather than injecting
      a stray separator (e.g. old code could produce `"foo. . bar"`).
- [x] AC-4: The `/result` endpoint (not just the extracted helper in isolation) exercises the
      fixed code path — a route-level regression test guards against silently reverting to
      the old join.
- [x] AC-5: No new `Any` / `type: ignore`; ruff clean on the touched files.

Out of scope for this ticket: the durable-worker / checkpointer half (background-task
execution model, `BackgroundTasks` → durable queue) — that is TMX-ORCH-CHECKPOINT Loop B,
one-way, requires human approval, not attempted here. The DOCX export path
(`app/services/document_export.py`) and the LangGraph pipeline (`app/agents/graph.py`) are
untouched — this ticket is scoped to the v1 REST `/result` reconstruction only.

## 3. Design

**Approach.** Extract a pure function `_reconstruct_document_text(segments: List[Segment]) ->
str` in the same module (thin route, G1: 1 caller, no new module). It iterates segments in
`order_index` order (as already queried), and for each pair of consecutive non-empty
segments decides the separator using only data the IR already recorded:

- `element_type` differs from the previous segment's → `"\n"` (a real structural boundary
  the ingester recorded — Header/Paragraph/TableCell/etc. — is preserved as a break instead
  of merged into prose).
- otherwise → `" "` (a single space; never a period). This mirrors the separator the
  segmenter itself already consumed when it split the source (`[.!?]+\s+` / clause-boundary
  splits both eat exactly the whitespace between pieces) — a segment that already ends in
  terminal punctuation is never double-punctuated, and a segment that doesn't (e.g. a
  length-capped hard-wrap fragment, TMX-OMIT-2) is joined the same way its original
  whitespace joined it, not with an invented character.

This satisfies "fail loud or preserve the original separator — never invent one" (A3): the
function never manufactures a punctuation mark; the two choices are both whitespace, driven
by recorded structure, not guesswork.

**Alternatives considered:**
- *Store explicit separator/offset metadata on each segment at ingestion time* (true
  "durable IR" reconstruction) — more faithful in the general case, but requires a schema
  change to `Segment` (new column) and touches the segmenter/ingestion write path, which is
  broader than this ticket's blast radius and not needed to close the specific hazard named
  in ADR-0008 (fabricated ". "). Noted for a future ticket if plain-text round-tripping needs
  full fidelity beyond punctuation.
- *Keep `". ".join` but only when the previous segment lacks terminal punctuation* — rejected
  because it still can't distinguish "no punctuation, needs a period" from "no punctuation,
  was a hard-wrapped fragment" without inventing information the IR doesn't have; A3 says
  fail loud or preserve, never guess.
- *Fail loud (raise) whenever a segment lacks terminal punctuation* — rejected as
  disproportionate: absence of terminal punctuation is common and legitimate (list items,
  headings, hard-wrapped long segments) and is not itself corruption; only inventing a
  character is.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/api/v1/translations.py` | 32-70 (new) | Add `_reconstruct_document_text` pure helper |
| `app/api/v1/translations.py` | ~200 (was 166-168) | `get_job_result` calls the helper instead of `". ".join(...)` |
| `tests/test_tmx_v1_durable_ir.py` | new file | Red/green tests for AC-1..AC-4 |

## 5. Eval / Test

Red (helper missing — collection error):
```
python -m pytest tests/test_tmx_v1_durable_ir.py -q
```
```
ImportError while importing test module '...\tests\test_tmx_v1_durable_ir.py'.
tests\test_tmx_v1_durable_ir.py:29: in <module>
    from app.api.v1.translations import _reconstruct_document_text
E   ImportError: cannot import name '_reconstruct_document_text' from 'app.api.v1.translations'
1 error in 7.97s
```

Red, take 2 — verified the assertions are real (not just import-shaped) by temporarily
wiring in a stub that byte-for-byte reproduces the old `". ".join(...)` behaviour:
```
python -m pytest tests/test_tmx_v1_durable_ir.py -q -k "not result_endpoint"
```
```
AssertionError: assert '?. ' not in 'Is this correct?. Yes it is.'
AssertionError: assert ':. ' not in 'Please confirm:. Confirmed'
AssertionError: assert '?. ' not in 'Is this correct?. Yes it is.. Please confirm:. Confirmed'
AssertionError: assert 'Section Title.' not in 'Section Title. Body content here.'
AssertionError: assert '. ' not in 'First cell. second cell'
AssertionError: assert 'First.. . Second.' == 'First. Second.'
6 failed, 1 deselected in 8.16s
```
```
python -m pytest tests/test_tmx_v1_durable_ir.py -q -k result_endpoint
```
```
assert '?. ' not in "Est-ce correct ?. Oui, c'est ça."
1 failed, 6 deselected in 5.02s
```

Green (real fix landed, stub removed):
```
python -m pytest tests/test_tmx_v1_durable_ir.py -v
```
```
tests/test_tmx_v1_durable_ir.py::test_no_fabricated_period_after_question_mark PASSED
tests/test_tmx_v1_durable_ir.py::test_no_fabricated_period_after_colon PASSED
tests/test_tmx_v1_durable_ir.py::test_varied_terminators_end_to_end_no_fabrication PASSED
tests/test_tmx_v1_durable_ir.py::test_element_type_boundary_is_not_flattened_into_a_fabricated_period PASSED
tests/test_tmx_v1_durable_ir.py::test_same_element_type_segments_join_with_space_not_period PASSED
tests/test_tmx_v1_durable_ir.py::test_empty_translated_text_segments_do_not_produce_double_separators PASSED
tests/test_tmx_v1_durable_ir.py::test_result_endpoint_does_not_fabricate_period_after_question_mark PASSED
7 passed in 5.90s
```

Related v1 suite (no regressions):
```
python -m pytest tests/test_api_contract.py tests/test_tmx_3012c_request_autoinjection.py tests/test_webhook_fire.py tests/test_golden_path_e2e.py tests/test_auth_rbac.py tests/test_tmx_v1_durable_ir.py -q
```
```
.................................s......................                 [100%]
55 passed, 1 skipped, 2 warnings in 19.48s
```

`ruff check app/api/v1/translations.py tests/test_tmx_v1_durable_ir.py` → `All checks passed!`

## 6. Red team

Ran `/review`-equivalent self read of the diff plus the 22-item checklist mentally:

- **Silent failure?** No — the function never swallows an exception; it can only ever emit
  `" "` or `"\n"`, both explicit, deterministic decisions from recorded data.
- **Unearned claim?** No provenance/quality field is touched; this only affects the
  `translated_text` string shape.
- **Edge case: all segments empty.** Returns `""`. Same as before (old join of all-empty
  strings also produced `""` or a run of `". "` — now cleanly `""`). Not a regression.
- **Edge case: single segment.** No separator logic runs (`have_prev` stays `False` for the
  first iteration); returns the segment's own text unchanged. Correct.
- **Edge case: `element_type` is `None` for every segment** (the plain-text `.txt` upload
  path — no ingester sets `element_type` there). `None != None` is `False`, so every join
  uses `" "` — never `"\n"`, never fabricated punctuation. Matches AC-1.
- **What could still be wrong in production?** Two adjacent segments of the *same*
  `element_type` but different `element_meta` (e.g. two different table cells both typed
  `"TableCell"`) still join with a bare space, which could visually merge two cells' text.
  This is a known, documented limitation (see Design → alternatives) — deeper than
  `element_type` requires `element_meta`-aware comparison, which is a larger change than this
  hazard needs; flagging here rather than silently shipping it as if solved. Does not
  regress vs. before (the old code fully flattened everything into fake sentences, which is
  strictly worse).
- **Cross-repo (ADR-0009) concern?** None — this route is not part of the reSCApe contract
  surface; `app/schemas/api_v1.py` and the seam are untouched.

## 7. Fix

No findings required a code change beyond what's already implemented — the one open
limitation (same-`element_type`/different-`element_meta` adjacency) is documented as a known,
strictly-non-regressing boundary rather than silently left unstated.

## 8. Deploy

- [x] Commit: `<filled after commit>` (on branch `loop/v1-durable-ir`; merge pending)
- [ ] CI green: not run (local loop only)
- [ ] `.context/active_tasks.md` updated — orchestrator-owned, not edited here
- [ ] Ratchet baseline updated — N/A, no baseline-affecting metric change beyond new tests

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created |
| 2026-07-22T00:00Z | `[Spec]` | `[Verify]` | Red test written, fix landed, green + related suite green; on branch `loop/v1-durable-ir`, merge pending |
