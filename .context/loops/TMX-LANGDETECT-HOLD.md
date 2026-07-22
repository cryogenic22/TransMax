# TMX-LANGDETECT-HOLD — uncertain source language becomes an explicit hold, never a silent "en"

**State**: `[Verify]` — on branch `loop/langdetect-hold`; merge pending
**Owner**: Agent & AI
**Sprint**: —
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way`
**Pre-mortem**: if this fails in production, the failure mode is a document in a language nobody declared gets silently translated as if it were English — every segment is wrong, the quality gates score against the wrong source, and the reviewer sees a confident-looking PASS instead of a hold. This is RS-06 / seam invariant C-3.
**Blast radius**: `app/agents/graph.py` (`validate_request` source-language resolution, `finalize_job`, graph wiring), `app/services/language_detection.py` (`DetectionResult`, `detect_language`, `_fallback`), `tests/test_langdetect_hold.py` (new), `tests/test_language_intelligence.py` (2 existing assertions updated). Does not cross the reSCApe seam boundary (no `Scriptiva_SCA` files touched) — CROSS-REPO-PROTOCOL.md does not apply, but this loop satisfies seam invariant **C-3** ("Low-confidence source-language detection ⇒ typed hold. Never a silent `en` default.") ahead of the seam contract work.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — extends two existing modules (`graph.py`, `language_detection.py`); no new route/service/model. New fields on the existing `TransMaxState` TypedDict + one new routing function reusing the existing `add_conditional_edges` pattern already used for `gates`. Ships with a red-then-green test.
- [x] **G2 Reproduce-the-failure** — see stage 5: failing test captured before the fix.
- [x] **G3 Completion** — see stage 7/8.

---

## 1. Task

`validate_request`'s source-language resolution silently defaults `state['source_language'] = "en"` in two places: when auto-detection confidence is below 0.5, and when detection raises/is unavailable (the `except Exception` catch-all). A mis-detected source then flows straight into `translate` and the quality gates score against the wrong source language while the result looks confident — A3 violation, red-stop RS-06, and the exact shape of seam invariant C-3. TMX-SSOT-TIER already made the DECLARED `Document.source_language` authoritative and unconditionally short-circuits this block — that must not change. The hold applies ONLY when there is no declared language AND detection is low-confidence or errored.

Addenda in play: **A1** (audit event before the side effect), **A3** (no silent fallback — fail loud/hold, never guess), **A5** (n/a — no ID remapping here), **A9** (n/a — no delete).

## 2. Spec — acceptance criteria

- [x] AC-1: No declared source language + low-confidence detection ⇒ `state['source_language_confirmation_required']` is set, `state['source_language']` is never set to `"en"` (stays unset), and the document never reaches `translate`/`gates` — `finalize_job` lands it on `DocumentStatus.IN_REVIEW`.
- [x] AC-2: Same as AC-1 when `detect_language` raises an exception — no crash, same hold, reason recorded as `"detector_error"`.
- [x] AC-3 (regression): declared `source_language` (either pre-set on state, e.g. via API, or present in `doc_meta`) ⇒ behaviour is completely unchanged — no hold, `detect_language` is never called.
- [x] AC-4: the v2 audit event (`SOURCE_LANGUAGE_CONFIRMATION_REQUIRED`) is emitted carrying the detector confidence and a typed reason, BEFORE the state flags are set (A1).
- [x] AC-5: `language_detection._fallback` never returns a bare `"en"` guess — returns an explicit low-confidence result (`language="und"`, `low_confidence=True`, a typed `reason`).

Out of scope: `app/api/endpoints.py::quick_translate` and `app/api/tools.py` (separate, non-pipeline callers of `detect_language`, unaffected by the graph routing change — they still read `.language`/`.confidence` and degrade gracefully to `"und"` at worst, no crash); the reSCApe seam contract itself (ADR-0009) — this loop only satisfies invariant C-3 on the TransMax side; `transmax_sdk`'s independent language detector (separate implementation, ADR-0009 clause 6 retires it later).

## 3. Design

**Declared-language short circuit is untouched.** `doc_meta.get('source_language')` (TMX-SSOT-TIER) still wins unconditionally — the hold branch is only reached when that's absent.

**`DetectionResult` gains two fields**: `low_confidence: bool = False` and `reason: Optional[DetectionHoldReason] = None` (a `Literal` of the five non-confident causes). This is the "explicit low-confidence result object" the ticket asks for — callers now have an unignorable boolean to check instead of re-deriving "was this confident?" from a threshold comparison. `language` on a non-confident result becomes `"und"` (ISO 639-2 "undetermined" — a real code, not an invented sentinel) instead of `"en"`, so even a caller that reads `.language` without checking `.low_confidence` gets an honest non-answer rather than a specific wrong language. This changes 2 pre-existing test assertions in `test_language_intelligence.py` (short-text and empty-text branches, which are the same silent-`"en"` class of bug) — updated in this loop.

**Routing**: a new `decide_after_validate` conditional-edge function (same pattern as the existing `decide_next_step` used for `gates`) routes `"validate"` straight to `"finalize"` when `state['source_language_confirmation_required']` is set, bypassing `load_segments` → `constraints` → `translate` → `gates` entirely. No segment is ever loaded, let alone translated, under an unconfirmed source language.

**Audit-before-flip**: a small helper `_emit_source_language_hold` (module-level in `graph.py`, mirrors the existing inline `_emit_v2_audit_event` call sites) emits the v2 event first, then sets the three state flags. It does not early-return from `validate_request` — the function falls through to the existing (unconditional, job_id-gated) v1 audit-trail-initialization block, so the job still gets `AUDIT_TRAIL_INITIALIZED`/`CONFIG_SNAPSHOT_CAPTURED`/`JOB_STARTED`, and `finalize_job`'s `JOB_FINALIZED` audit block (gated on `state.get('audit_id')`) still fires with the hold reason in its payload. An early return was considered and rejected: it would skip `audit_id` creation entirely, which would then skip `finalize_job`'s whole audit-logging block (nested under `if state.get('audit_id')`) — turning "hold recorded in the chain" into "hold happened, chain silent," a worse A1 violation than the one being fixed.

**`finalize_job`** gains a one-directional escalation identical in shape to the existing `reflexion_review_required` → `IN_REVIEW` pattern (TMX-DRIFT-GATE): if `source_language_confirmation_required` is set, `final_status = DocumentStatus.IN_REVIEW` (never downgrades an already-held status) and the reason + confidence land in the `JOB_FINALIZED` payload.

**Status reuse**: `DocumentStatus` has no `BLOCKED` value (only `UPLOADED/PROCESSING/TRANSLATED/IN_REVIEW/APPROVED`). `IN_REVIEW` is the closest honest existing status — "held for a human before it can proceed" — and is already the exact status TMX-DRIFT-GATE uses for its own hold. No new enum value invented; back-compat is a non-issue since no new value is added.

**Alternatives considered**: (a) invent `DocumentStatus.LANGUAGE_HOLD` — rejected, `IN_REVIEW` already means "needs a human before this is done" and adding a sibling status multiplies the states every consumer (UI, exports, reports) must handle for the same semantic; the ticket's own text prefers reuse. (b) Early-return from `validate_request` on hold — rejected, see audit-before-flip above. (c) Change `DetectionResult.language` to `Optional[str]` instead of the `"und"` sentinel — rejected, it would ripple a type change into `app/api/endpoints.py` and `app/api/tools.py` (out of scope, not touched by this loop) wherever `.language` is read as `str`; `"und"` is a real BCP-47/ISO-639-2 code, keeps the field type stable, and is unambiguous.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/language_detection.py` | 1-107 | `DetectionHoldReason` Literal; `DetectionResult` gains `low_confidence`/`reason`; short-text branch, `_fallback`, and the low-confidence branch all return `language="und"` + `low_confidence=True` + a typed `reason` instead of a bare `"en"` |
| `app/agents/graph.py` | `TransMaxState` | 3 new `Optional` fields: `source_language_confirmation_required`, `source_language_detection_confidence`, `source_language_detection_reason` |
| `app/agents/graph.py` | `_emit_source_language_hold` (new, module-level) | emits v2 audit event, then sets the 3 state flags |
| `app/agents/graph.py` | `validate_request` | low-confidence / exception branches call the new helper instead of `state['source_language'] = "en"` |
| `app/agents/graph.py` | `decide_after_validate` (new) | routes to `"finalize"` when the hold flag is set, else `"load_segments"` |
| `app/agents/graph.py` | `finalize_job` | hold flag ⇒ `DocumentStatus.IN_REVIEW` + reason/confidence in `JOB_FINALIZED` payload |
| `app/agents/graph.py` | graph wiring | `workflow.add_edge("validate", "load_segments")` → `workflow.add_conditional_edges("validate", decide_after_validate, {...})` |
| `tests/test_langdetect_hold.py` | new | AC-1..AC-4 |
| `tests/test_language_intelligence.py` | ~188-197 | 2 assertions updated for the `"und"` sentinel (AC-5) |

## 5. Eval / Test

RED (before the fix — `tests/test_langdetect_hold.py` written first, run against unmodified `graph.py`/`language_detection.py`):

```
$ python -m pytest tests/test_langdetect_hold.py -q
```
```
>       from app.agents.graph import decide_after_validate, validate_request
E       ImportError: cannot import name 'decide_after_validate' from 'app.agents.graph' (...\app\agents\graph.py)
...
>       mock_db.update_document_status.assert_called_once_with("doc-1", DocumentStatus.IN_REVIEW.value)
E       AssertionError: expected call not found.
E       Expected: update_document_status('doc-1', 'in_review')
E         Actual: update_document_status('doc-1', 'translated')
...
FAILED tests/test_langdetect_hold.py::test_low_confidence_detection_holds_not_en
FAILED tests/test_langdetect_hold.py::test_detector_error_holds_no_crash
FAILED tests/test_langdetect_hold.py::test_declared_language_on_state_bypasses_detection
FAILED tests/test_langdetect_hold.py::test_declared_language_in_doc_metadata_bypasses_detection
FAILED tests/test_langdetect_hold.py::test_finalize_holds_job_on_language_confirmation_required
5 failed in 8.08s
```

GREEN (after the fix):

```
$ python -m pytest tests/test_langdetect_hold.py -q
.....                                                                    [100%]
5 passed in 10.88s
```

```
$ python -m pytest tests/test_langdetect_hold.py tests/test_language_intelligence.py \
    tests/test_drift_gate.py tests/test_graph_audit_timestamps.py \
    tests/test_tmx_3110_double_write.py tests/test_tmx_3202_audit_snapshot_model.py \
    tests/test_sprint6_safety.py tests/test_finalize_output_hash.py tests/test_terminology_e2e.py -q
........................................................................ [ 87%]
..........                                                               [100%]
82 passed in 21.79s
```

```
$ python -m pytest tests/ -q --timeout=900
1468 passed, 2 skipped, 4 warnings in 686.31s (0:11:26)
```
(full backend suite, run once after the fix, before the line-count/ratchet cleanup pass)

```
$ python -m pytest tests/ -q --timeout=900   # re-run AFTER the ratchet cleanup (stage 7)
1468 passed, 2 skipped, 4 warnings in 476.32s (0:07:56)
```

```
$ python scripts/ratchet.py check
✓ Ratchet OK — all 17 metrics at or better than baseline.
```
(first run surfaced `backend.any_annotations +6` from `Dict[str, Any]` in the new test file, and `backend.mega_files_800 +1` from `graph.py` crossing 821 lines — both fixed: test file now uses precise `dict[str, str]`/`list[dict[str, str]]`, `graph.py` trimmed to 796 lines by de-verbosing the new comments/docstrings, no logic change.)

## 6. Red team

- `/review`-style pass on the diff: no silent-fallback reintroduction, no new `Any`/`type: ignore`, no bare `except` (both new `except Exception` blocks already existed pre-patch — behaviour changed, exception handling shape unchanged), `logger` only (no `print`).
- Checked every other caller of `detect_language`/`DetectionResult` (`app/api/endpoints.py::quick_translate`, `app/api/tools.py`) for breakage from the `"und"` sentinel + new fields: both read `.language` as a plain string and degrade to a harmless `"und"` label on a genuinely uncertain detection — no crash, no `Any`/type regression (out of scope, not touched).
- Checked every existing test that exercises `validate_request`/the full compiled graph (`test_nfr_validation.py`, `test_tmx_3110_double_write.py`, `test_tmx_3202_audit_snapshot_model.py`, `test_terminology_e2e.py`, `test_refinement_usage.py`) for a document with NO declared source language that would now newly route to the hold — all seed `Document.source_language="en"` (declared) or set `state["source_language"]` directly, so none exercise the auto-detect path; confirmed unaffected by running them (green above + full suite).
- mypy: ran against the two changed files; the only new-looking findings (`graph.py:741-748` — the new `final_payload[...]` assignments not matching the dict's inferred type) are the SAME error class already present pre-patch at the sibling `reflexion_review_required`/`reflexion_min_score` lines (confirmed on `HEAD:app/agents/graph.py` — line 679-680 pre-patch has the identical `Incompatible types in assignment` shape). Not a new defect class, mirrors the established (already-imperfect) local pattern; mypy itself already reports 178 pre-existing errors repo-wide when following imports, so it is not currently a passing/blocking gate in this worktree.
- ruff: `app/agents/graph.py` has 2 pre-existing `E402` findings (confirmed present on unmodified `HEAD`, unrelated line content, module-level lazy imports at the `gates`/graph-construction boundary) and `ruff format --diff` shows the whole file has never been run through the formatter (quote-style, blank lines) — both predate this change and are out of scope for a surgical ticket; `tests/test_langdetect_hold.py` is clean.
- Pre-commit is not installed as a git hook in this worktree (`git config core.hookspath` resolves to the shared `.git/hooks`, which contains only `*.sample` files) — `git commit` will not invoke it. Ran the checks manually instead: `ruff check`, `ratchet.py check` (blocking, now green), full pytest.
- Confirmed the audit-before-flip ordering by construction: `_emit_source_language_hold` calls `_emit_v2_audit_event` first, then sets the three state flags — not by a test assertion on ordering (the mock records the call regardless of order), but the source itself is the evidence and AC-4's test checks the event's payload contents/count, which would be wrong if the function bailed early.
- Considered: does skipping `load_segments`→`gates` also skip the `content_metadata`/`iteration_count` init and the v1 audit-trail block? No — `_emit_source_language_hold` does not return early; `validate_request` falls through to those unconditionally, so the v1 `AUDIT_TRAIL_INITIALIZED`/`CONFIG_SNAPSHOT_CAPTURED`/`JOB_STARTED` events still fire and `finalize_job`'s `audit_id`-gated `JOB_FINALIZED` block (with the hold reason) still fires. Verified directly by `test_low_confidence_detection_holds_not_en`'s audit-event assertions and by `test_finalize_holds_job_on_language_confirmation_required`.

## 7. Fix

Two issues found by the ratchet gate (not by red-team code review, but the same discipline — a blocking mechanical check):

1. `tests/test_langdetect_hold.py` used `Dict[str, Any]`/`list[Dict[str, Any]]` type annotations (4 occurrences) — replaced with precise `dict[str, str]`/`list[dict[str, str]]` (the test fixtures only ever hold strings), and dropped the redundant `Dict[str, Any]` annotation on local `state` dict literals entirely (matching the untyped-literal convention already used in `tests/test_drift_gate.py`).
2. `app/agents/graph.py` crossed the 800-line `mega_files_800` ratchet threshold (743 -> 821) — trimmed the new code's comments/docstrings for density (no logic change; re-ran the full `test_langdetect_hold.py` + adjacent suites after trimming to confirm no regression from the edit). Final size: 796 lines.

Re-ran `python scripts/ratchet.py check` after both fixes: `✓ Ratchet OK — all 17 metrics at or better than baseline.`

No findings from the red-team review in stage 6 required a code change beyond the two ratchet items above.

## 8. Deploy

- [x] Commit: (filled after `git commit`, see status log)
- [ ] CI green: not run (worktree-local; pre-commit not installed in this worktree — see stage 6); full backend suite run manually twice, green both times (1468 passed, 2 skipped)
- [ ] `.context/active_tasks.md` updated: N/A — orchestrator owns this file
- [x] Ratchet baseline updated: N/A — no baseline change needed, `python scripts/ratchet.py check` passes as-is (all 17 metrics at/better than baseline)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created |
