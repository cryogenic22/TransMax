# TMX-SEAM-WIRE — wire the contract result block into the live v1 result path, HONESTLY

**State**: `[Verify]`
**Owner**: Audit & Validation
**Sprint**: —
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — additive fields on `JobResult`; no schema migration, no existing field changes.
**Pre-mortem**: if this fails in production, the failure mode is a `disposition`/`provenance`/`audit`
field that LOOKS sourced but is actually a guess or a stale default — a regulator reads it as
provenance and it isn't. Guarded against by: every field traces to one query result and is `None`
when that query is empty; the red tests specifically assert no plausible-looking constants leak
through, and `mqm` is pinned `None` so a future loop can't silently wire the legacy scorer into it.
**Blast radius**: `app/schemas/api_v1.py` (`JobResult` gains 4 optional fields; `TranslationDisposition`
/`MqmSummary`/`ProvenanceRecord`/`AuditRef` moved earlier in the file, unchanged in shape),
`app/api/v1/translations.py` (`get_job_result` + 4 new private helpers), 2 test files. No other route,
no quality gate, no graph, no MQM engine.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — extends the existing `/result` route + existing `JobResult` schema; no new
  route, no new table. 4 small helper functions, each with a single real caller (the route), each
  reusing an existing query pattern already proven in `app/api/v1/audit.py::verify_v2_audit_chain`
  (chain-head lookup) and `_config_snapshot.py` (config-snapshot shape). Ships with 8 new tests that
  fail without the change.
- [x] **G2 Reproduce-the-failure** — N/A framing note: this ticket isn't a bug-fix, it's "wire an
  unwired schema honestly" — the red-test-first discipline still applies (see stage 5): all 7 assertion
  groups in (a)/(b)/(c) fail with `KeyError` against pre-fix `translations.py` because the fields don't
  exist on the response at all.
- [x] **G3 Completion** — the live route now returns real `disposition`/`provenance`/`audit`, verified
  against the independent `/verify_v2` endpoint in the same test run; `mqm` stays `None`.

---

## 1. Task

TMX-SEAM-CONTRACT (`d5ae686`) added `TranslationDisposition` / `MqmSummary` / `ProvenanceRecord` /
`AuditRef` / `SegmentResult` / `JobResultResponse` to `app/schemas/api_v1.py` but deliberately left them
unwired — schema only. This loop wires `disposition`, `provenance`, and `audit` onto the LIVE
`GET /api/v1/translations/{job_id}/result` response (`JobResult`), additively, from data that genuinely
exists today. `mqm` stays `None` — the MQM engine is shadow-only (TMX-MQM-5 series); the live verdict is
still the legacy `quality_gate.py::evaluate_verdict` scorer. Addenda in play: **A1** (audit pointer must
be a real chain lookup), **A3** (the whole point — no field may be a plausible-looking default), **A4**
(read across `database.py` / `models.py` / `audit_v2.py` without deepening the divergence — no new
tables, no new FKs), **A6** (provenance = qualified-supplier telemetry, sourced from the artefact the
job actually ran with, not a fresh live re-resolution), **A8** (prompt version + content hash from the
pinned artefact, not "current").

## 2. Spec — acceptance criteria

- [x] AC-1: a completed job's `/result` response carries `contract_version == "1.1.0"`, a `disposition`
  matching the REAL persisted `QualityScorecard.status` (not `Document.status`), and
  `audit.chain_head_hash` that MATCHES the independent `GET /{job_id}/verify_v2` endpoint's own
  `chain_head_hash` for the same job.
- [x] AC-2: `provenance` fields with no backing artefact (`model_version`, `language_tier`, and — when
  there's no `CONFIG_SNAPSHOT_CAPTURED` v2 event — `model`/`prompt_version`/`prompt_content_hash` too)
  are `None`, never a plausible-looking constant (`"default"`, `"v1"`, `"gpt-4o"`, `"unknown"`); `model`
  is either a real resolved model id (sourced from the job's own config-snapshot event) or `None`.
- [x] AC-3: `mqm` is `None` on every `/result` response, unconditionally — even when a full
  `QualityScorecard` exists.
- [x] AC-4: pre-existing `JobResult` fields (`job_id`, `status`, `original_filename`, `translated_text`,
  `quality_summary`, `audit_id`, `completed_at`, `contract_version`) are byte-identical in shape and
  value to what an existing caller saw before this loop.

Out of scope: the quality gate, the LangGraph pipeline, the MQM engine, `SegmentResult` /
`JobResultResponse` (still unwired — a future per-segment/v2 result route), any change to
`AuditRecord`/`JobConfigSnapshot` (the v1 legacy audit tables) — provenance is sourced from the v2 chain
only.

## 3. Design

**disposition.** The only real, persisted verdict is `QualityScorecard.status`, written by
`graph.py`'s `quality_gate` node from `quality_gate.py::evaluate_verdict`'s return value — the string
values (`PASS`/`REVIEW_REQUIRED`/`BLOCKED`) are byte-identical to `TranslationDisposition`'s members, so
`_derive_disposition` just parses the enum and returns `None` (with a `logger.warning`, never a guess)
if there's no scorecard or an unrecognised string. Rejected: deriving from `Document.status`
(`translated`/`in_review`/`approved`) — that's workflow state, a different concept, and the pre-existing
`ValidationSummary.decision` field already conflates the two (pre-existing bug, explicitly out of scope
per the ticket — "Do NOT change the quality gate").

**provenance.** Rejected: calling `resolve_model()` / `PromptRegistry.load()` live at request time —
that would report what the system is CONFIGURED to do right now, not what THIS job actually ran with;
for a job from before a settings/prompt change, that's the unearned-claim defect this program keeps
fixing, restated with a live call instead of a stored default. Chosen: read the job's own
`CONFIG_SNAPSHOT_CAPTURED` v2 audit event — its payload IS `_config_snapshot.build_config_snapshot`'s
output, frozen into the chain at job start (A6/A8). This is also the literal "chain entry" the reviewer
brief names as a canonical honest source. `match_type` comes from `Segment.translation_source`, folded
to a single value only when every segment in the job agrees (an ambiguous job-level match type is
`None`, not a guess). `model_version` and `language_tier` have no corresponding artefact anywhere in
this codebase yet — they stay `None` unconditionally, which is itself asserted by a red test so a future
loop can't quietly default them.

**audit.** `chain_head_hash` = hex of the highest-`sequence_index` `AuditEventV2.event_hash` for the
job — literally the same query `app/api/v1/audit.py::verify_v2_audit_chain` uses for its own head hash,
so the two independently agree (proven by AC-1's test, which calls both endpoints and diffs the value).
`verify_url` points at that existing route. No v2 events for the job -> `audit=None` (not a placeholder
object with two `None` sub-fields — the ticket says "return None" for the whole ref).

**mqm.** Left at the schema default (`None`); the route never touches it. A dedicated red test
(`test_mqm_is_always_none_even_with_a_full_scorecard`) pins this so a future loop wiring the legacy
scorer's counts into an `MqmSummary` (which would be trivial to do by accident — the numbers are right
there on the same `QualityScorecard`) fails loud.

**Schema placement.** `TranslationDisposition`/`MqmSummary`/`ProvenanceRecord`/`AuditRef` were declared
AFTER `JobResult` in `api_v1.py` (TMX-SEAM-CONTRACT deliberately parked them there as unwired). Wiring
them onto `JobResult` needs them defined first (no `from __future__ import annotations` in this file, so
forward references don't resolve at class-body eval time) — moved the 4 shared classes to just above
`JobResult`; `SegmentResult`/`JobResultResponse` (which compose them) stay where they were and are
byte-for-byte unchanged, confirmed by the pre-existing `test_seam_contract.py` suite staying green
untouched.

**Alternative considered and rejected:** compose the route's response from `SegmentResult`/
`JobResultResponse` directly instead of adding fields to `JobResult`. Rejected because `SegmentResult`
pins `mqm: MqmSummary` as REQUIRED (not `Optional`) — `test_seam_contract.py` constructs it that way and
that test is pinned, unchanged, by this ticket. Satisfying "mqm must be None" would have meant either
changing that pinned contract shape (out of scope, and TMX-SEAM-CONTRACT's docstring says a FUTURE loop
composes those into a route) or fabricating a placeholder `MqmSummary` — the opposite of the point.
Extending `JobResult` directly with `Optional[...]` fields sourced from the same shared component models
gets the honest job-level result block without touching the per-segment contract shape.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/schemas/api_v1.py` | 159-212 | Moved `TranslationDisposition`/`MqmSummary`/`ProvenanceRecord`/`AuditRef` to before `JobResult` (unchanged shape) |
| `app/schemas/api_v1.py` | 230-260 | `JobResult` gains `disposition`, `provenance`, `audit`, `mqm` — all `Optional[...] = None` |
| `app/schemas/api_v1.py` | ~389-396 | Old unwired-block comment replaced with a pointer to the new location |
| `app/api/v1/translations.py` | imports | + `AuditEventV2`, `QualityScorecard`, `AuditRef`, `ProvenanceRecord`, `TranslationDisposition`, `Optional` |
| `app/api/v1/translations.py` | `_derive_disposition` | new — `QualityScorecard.status` -> `TranslationDisposition` or `None` |
| `app/api/v1/translations.py` | `_derive_match_type` | new — uniform `Segment.translation_source` or `None` |
| `app/api/v1/translations.py` | `_build_provenance` | new — reads the job's `CONFIG_SNAPSHOT_CAPTURED` v2 event |
| `app/api/v1/translations.py` | `_build_audit_ref` | new — reads the job's v2 chain head; `None` if no chain |
| `app/api/v1/translations.py` | `get_job_result` | wires the 3 helpers into the `JobResult(...)` return; hoisted `scorecard` out of the try/except (forced back to `None` on any lookup failure so disposition can't read a half-fetched object) |
| `tests/test_seam_wire.py` | new file | 8 tests, ACs (a)-(d) |
| `tests/test_tmx_v1_durable_ir.py` | mock fixture | extended `query_side_effect`'s `else` branch to also stub `.filter().order_by().first()` (the new `AuditEventV2` query shape) — the pre-existing test broke against a bare `MagicMock` leaking into a `str` field until this was added |

## 5. Eval / Test

Red run (`git stash` of the 2 source files, test files kept) — 7 of 8 new tests fail, the backwards-compat
test (d) passes both before and after (proving it's a real non-regression check, not a trivial one):

```
$ python -m pytest tests/test_seam_wire.py tests/test_tmx_v1_durable_ir.py -q
...
E       KeyError: 'disposition'
...
E       KeyError: 'audit'
...
E       KeyError: 'provenance'
...
E       KeyError: 'mqm'
=========================== short test summary info ===========================
FAILED tests/test_seam_wire.py::test_result_carries_contract_version_and_real_disposition
FAILED tests/test_seam_wire.py::test_disposition_blocked_when_scorecard_says_blocked
FAILED tests/test_seam_wire.py::test_no_scorecard_yields_none_disposition_not_a_guess
FAILED tests/test_seam_wire.py::test_provenance_with_no_config_snapshot_event_is_all_none
FAILED tests/test_seam_wire.py::test_provenance_model_and_prompt_fields_sourced_from_real_config_snapshot
FAILED tests/test_seam_wire.py::test_provenance_model_is_a_real_string_or_none_never_a_mock_object
FAILED tests/test_seam_wire.py::test_mqm_is_always_none_even_with_a_full_scorecard
7 failed, 1 passed in 8.41s
```

Green run (implementation restored):

```
$ python -m pytest tests/test_seam_wire.py tests/test_tmx_v1_durable_ir.py tests/test_seam_contract.py -q
......................                                                   [100%]
22 passed in 9.35s

$ python -m pytest tests/ -k "translat or audit or seam" -q
...
222 passed, 3 skipped, 1287 deselected, 2 warnings in 82.01s

$ python -m pytest tests/ -q
...
1507 passed, 5 skipped, 4 warnings in 255.91s (0:04:15)

$ python scripts/ratchet.py check
✓ Ratchet OK — all 17 metrics at or better than baseline.

$ python -m ruff check app/api/v1/translations.py app/schemas/api_v1.py tests/test_seam_wire.py tests/test_tmx_v1_durable_ir.py
All checks passed!
```

## 6. Red team

Ran `/review` equivalent manually against the diff:

- **Unearned claim check (the whole point):** every one of `disposition`/`provenance.*`/`audit.*` is
  either read straight off a query result or `None`. No `except: pass` swallows an error into a default
  value — the one `try/except` around the scorecard lookup explicitly forces `scorecard = None` in the
  except branch so `_derive_disposition` also honestly reports "couldn't determine" rather than reading
  a stale/partial object. `mqm` is never touched by the route at all (stays at the schema default).
- **A4 (dual-model-layer divergence):** no new table, no new FK. `_build_provenance`/`_build_audit_ref`
  read `AuditEventV2` (the v2 chain, already the canonical audit source) filtered by `job_id` — the
  identical join-key pattern the pre-existing `/verify_v2` route already uses successfully across the
  `Document.id` (database.py) / `AuditEventV2.job_id` (audit_v2.py, declared FK to a different table)
  boundary. Not deepened, reused.
- **Backwards compatibility:** confirmed by AC-4's test AND by the full 1507-test suite staying green —
  in particular `test_seam_contract.py` (pins `SegmentResult`/`JobResultResponse` byte-for-byte) and
  `test_tmx_v1_durable_ir.py` (pins the text-reconstruction route wiring) both still pass unmodified in
  assertions (only the mock fixture's stub surface was widened, not any assertion).
- **What could break in production:** if a job's `CONFIG_SNAPSHOT_CAPTURED` v2 write silently failed
  (the documented Phase-1 `_audit_v2_emit.py` behaviour — v2 write failures log a WARNING and don't
  raise), `provenance` correctly degrades to all-`None` rather than throwing 500 or lying — exercised by
  `test_provenance_with_no_config_snapshot_event_is_all_none`.
- **Edge case not covered (documented, not fixed — out of scope):** `ValidationSummary.decision` still
  reads `Document.status` instead of the real verdict (pre-existing bug, not introduced or worsened by
  this loop — flagged in stage 3 design notes above; a candidate for a follow-up ticket, not silently
  fixed here since "Do NOT change the quality gate" is explicit ticket scope).

## 7. Fix

No findings from the red team pass — clean. (The `test_tmx_v1_durable_ir.py` mock gap surfaced during
implementation, not red-team review, and was fixed in stage 4/5 before the green run above.)

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] CI green: pending (not pushed — on branch `loop/seam-wire`, merge pending)
- [ ] `.context/active_tasks.md` updated — orchestrator-owned, not touched by this loop
- [ ] Ratchet baseline updated — not needed, `ratchet check` passed against the existing baseline

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T14:00Z | — | `[Spec]` | Created |
| 2026-07-22T15:30Z | `[Spec]` | `[Verify]` | Implementation + red/green tests done; on branch `loop/seam-wire`, commit pending |
