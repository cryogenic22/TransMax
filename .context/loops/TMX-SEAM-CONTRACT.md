# TMX-SEAM-CONTRACT — extend the v1 job contract for the reSCApe seam (ADR-0009 clauses 3-5)

**State**: `[Verify]`
**Owner**: Audit & Validation (seam work, TransMax side)
**Sprint**: n/a (loop-driven)
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — additive-only schema extension, every new field `Optional` with a default. No route wiring, no shape change to an existing route.
**Pre-mortem**: if this fails in production, the failure mode is a downstream consumer (reSCApe's generated client, or a future TransMax route) reading a field that silently defaults to `None`/`CONTRACT_VERSION` and treating it as an earned value — i.e. the contract shape exists but nothing populates it yet, so a naive caller could mistake schema presence for wiring. Mitigated by stating scope explicitly (schema only, no live-path wiring this loop) in this worksheet and the PR body.
**Blast radius**: `app/schemas/api_v1.py` (additive models + `CONTRACT_VERSION` + `tm_match_key`), `scripts/export_contract.py` (new), `contract/openapi.json` (new, generated), `tests/test_seam_contract.py` (new). No route files touched. No reSCApe-side files touched (this loop is TransMax-side only; ADR-0009 clause 3 contract-authoring step — the reSCApe-side worksheet/client regen is a separate, later loop per CROSS-REPO-PROTOCOL Rule 1, since this loop does not change any route's wire shape that a live reSCApe caller depends on today).

**Seam**: contract v1.1.0 — TransMax-side schema-only extension. No paired reSCApe commit this loop (see Rule 1 note in Task below).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat (between stage 2 and 3)** — see §3 Design.
- [ ] **G2 Reproduce-the-failure** — N/A, greenfield schema addition, not a bug ticket.
- [x] **G3 Completion (between stage 7 and 8)** — see §7.

---

## 1. Task

reSCApe must call TransMax over a versioned contract instead of importing its internals (ADR-0009).
The contract skeleton exists in `app/schemas/api_v1.py`: `JobCreateRequest` already carries
`request_id` (idempotency), `JobProfileRequest` (governance profile), and `webhook_url`. This loop
adds the three pieces ADR-0009 clause 3 says are missing: a **source reference** block, a
**constraint** block, and an honest **result** block (disposition, MQM summary, provenance, audit
ref) — plus the `CONTRACT_VERSION` join key (clause 3, Rule 3 of CROSS-REPO-PROTOCOL), the TM match
key helper (clause 4), and an OpenAPI export so reSCApe can generate a typed client.

Addenda in play: A1 (audit ref surfaces `chain_head_hash`), A3 (result block must not imply live
wiring it doesn't have — see scope note below), A5 (stable IDs — `component_id`/`component_version_id`
carried through, never re-derived), A6 (`ProvenanceRecord` carries model/prompt-version fields for
the qualified-supplier telemetry, though nothing populates them yet this loop).

**Cross-repo note (CROSS-REPO-PROTOCOL Rule 1):** this loop is scoped to the TransMax-side schema
only, per the ticket's explicit instruction ("DO NOT wire these into the live translation path this
loop — schema + helper + export only"). No existing route's request/response wire shape changes for
any current caller (every new field is `Optional`, defaulted). Because no live route shape changes,
there is nothing yet for a reSCApe-side worksheet to pair against or regenerate a client for — the
generated `contract/openapi.json` is the artifact a future reSCApe-side loop consumes. That follow-up
loop (client regen + wiring) is out of scope here and is called out explicitly so it isn't lost.

## 2. Spec — acceptance criteria

- [x] AC-1: `JobCreateRequest` validates with ONLY the pre-existing fields — backwards compatibility,
      true before AND after this change.
- [x] AC-2: A `JobCreateRequest` carrying `source_ref` (`SourceReference`) and `constraints`
      (`ConstraintPack`) round-trips every field through `model_validate`/`model_dump`.
- [x] AC-3: Every response model in `app/schemas/api_v1.py` that is wired to a live route
      (`JobResponse`, `JobResult`, `AuditBundleResponse`, `AuditRecordResponse`,
      `AuditVerificationResponse`, `OrgAuditVerificationResponse`) plus the two new result-block
      models (`SegmentResult`, `JobResultResponse`) carries `contract_version == CONTRACT_VERSION`.
- [x] AC-4: `tm_match_key(hash_canonical, target_locale, termbase_version_id)` is deterministic
      (same inputs → same output) and changes when `termbase_version_id` changes alone (bind-
      revalidation property, ADR-0009 clause 4).
- [x] AC-5: `TranslationDisposition` has exactly three members: `PASS`, `REVIEW_REQUIRED`, `BLOCKED`.
- [x] AC-6: `python scripts/export_contract.py` produces `contract/openapi.json` that is valid JSON
      and contains the new schema names.

Out of scope for this ticket: wiring `source_ref`/`constraints`/the result block into
`app/api/v1/translations.py` or any live handler; a `v2` route; reSCApe-side changes; TM matching
logic beyond the key helper (no lookup/store); termbase CRUD.

## 3. Design

**Where the new models live:** `app/schemas/api_v1.py`, not a new module. G1 check: the ticket's own
threshold ("maybe one new small schema module if api_v1.py would bloat past ~400 lines") is touched
but not meaningfully breached — the file grows from 252 to 411 lines (docstrings account for most of
the growth; ~15 field/class lines are the actual shape). Splitting a 411-line schema file into two at
this margin would fail G1(a) (not needed — no consumer is struggling to find anything, no file-size
tooling gate exists at 400) and G1(d) (the file is already the established single source of truth for
the v1 contract — ADR-0009 clause 3 says "the contract extends TransMax's existing
`app/schemas/api_v1.py`; it is not a new invention"). Keeping one file also avoids a second schema
registry per CLAUDE.md's "single source of truth" principle. Flagging the actual count (411, not the
originally-estimated 380) here rather than silently rounding down.

**Where `tm_match_key` lives:** `app/schemas/api_v1.py`, alongside the models it keys. There is no
existing TM/translation-memory service module in this codebase (`grep` for `tm_`/`translation_memory`
under `app/` returns nothing) — creating a new `app/services/tm_*.py` module for one pure, stateless
function would itself be new-module bloat (fails G1a: extend, don't add). The function has no DB
dependency and is contract-shaped (ADR-0009 clause 4 describes it as *the key*, i.e. part of the
wire contract, not TM storage/lookup logic, which is explicitly out of scope this loop). Revisit if
a future loop adds an actual TM store — that service module would be the natural new home.

**`tm_match_key` implementation:** canonical JSON of `{"hash_canonical", "target_locale",
"termbase_version_id"}` with `sort_keys=True, separators=(",", ":")`, sha256 hex digest. Mirrors the
existing pattern in `app/core/metric_profiles/registry.py:_compute_hash` (same repo, same technique,
already reviewed) rather than inventing a new hashing convention. A hash (vs. raw concatenation) avoids
delimiter-collision ambiguity between the three components and matches how every other stable
identifier in this codebase is derived.

**`contract_version` stamping scope:** "every response model" is read as every response model
*actually wired to a route* (`response_model=` grep confirms six classes in this file) plus the two
new result-block models this loop introduces. Sub-objects that are never a route's top-level
`response_model` (`Alert`, `ValidationSummary`, `AuditLogEntryResponse`, `OrgChainSummary`,
`VerifyFinding`, and the new `SourceReference`/`ConstraintPack`/`TermbaseRef`/`MqmSummary`/
`ProvenanceRecord`/`AuditRef`) are not stamped — stamping a nested sub-object would be a second,
redundant place to check the same value and doesn't serve Rule 3's stated purpose ("stamped in every
response so a stored result can be traced to the shape that produced it" — the response is the
top-level model). Adding the field to the six existing response classes is additive-safe: Pydantic
back-fills the default on every existing caller without touching route code.

**Alternatives considered:**
- *New `app/schemas/seam.py` module* — rejected per G1(a)/(d) above; file size doesn't warrant it and
  ADR-0009 explicitly names `api_v1.py` as the contract home.
- *Raw string concatenation for `tm_match_key`* (`f"{hash}:{locale}:{ver}"`) — rejected: no existing
  precedent in this codebase uses raw concatenation for a stable key (all use JSON+sha256), and a
  colon-joined string has a (remote but real) delimiter-collision risk if a `hash_canonical` ever
  contained a colon.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/schemas/api_v1.py` | 1-3 | add `hashlib`, `json`, `Enum` imports |
| `app/schemas/api_v1.py` | 15-20 | add `CONTRACT_VERSION = "1.1.0"` constant |
| `app/schemas/api_v1.py` | 23-52 | add `SourceReference`, `TermbaseRef`, `ConstraintPack` models |
| `app/schemas/api_v1.py` | 104-109 | `JobCreateRequest` gains `source_ref: Optional[SourceReference] = None`, `constraints: Optional[ConstraintPack] = None` |
| `app/schemas/api_v1.py` | 319-380 | add `TranslationDisposition(str, Enum)`, `MqmSummary`, `ProvenanceRecord`, `AuditRef`, `SegmentResult`, `JobResultResponse` |
| `app/schemas/api_v1.py` | 177, 192, 214, 227, 282, 308 | add `contract_version: str = CONTRACT_VERSION` to `JobResponse`, `JobResult`, `AuditBundleResponse`, `AuditRecordResponse`, `AuditVerificationResponse`, `OrgAuditVerificationResponse` |
| `app/schemas/api_v1.py` | 383-410 | add `tm_match_key()` pure function |
| `scripts/export_contract.py` | new (119 lines) | dumps `app.main.app.openapi()` + merges unwired result-block schemas via `pydantic.json_schema.models_json_schema`, to `contract/openapi.json` |
| `contract/openapi.json` | new (generated) | committed artifact, 74 schemas including all 9 new contract types |
| `tests/test_seam_contract.py` | new (7 tests) | AC-1..AC-6 |

## 5. Eval / Test

**Red run (pre-implementation)** — collection error, all new symbols absent:

```
$ python -m pytest tests/test_seam_contract.py -q
=================================== ERRORS ====================================
________________ ERROR collecting tests/test_seam_contract.py _________________
ImportError while importing test module '...\tests\test_seam_contract.py'.
tests\test_seam_contract.py:9: in <module>
    from app.schemas.api_v1 import (
E   ImportError: cannot import name 'CONTRACT_VERSION' from 'app.schemas.api_v1' (...\app\schemas\api_v1.py)
=========================== short test summary info ===========================
ERROR tests/test_seam_contract.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.50s
```

**Green run (post-implementation):**

```
$ python -m pytest tests/test_seam_contract.py -q
.......                                                                  [100%]
7 passed in 6.25s
```

**Backwards-compatibility / nearest-related suites** (every test file under `tests/` that imports
`app.schemas.api_v1`, plus every test file that exercises the v1 routes directly):

```
$ python -m pytest tests/test_seam_contract.py tests/test_webhook_fire.py tests/test_ssot_tier.py \
    tests/test_qrd_wire.py tests/test_api_contracts.py -q
.............................................................            [100%]
61 passed in 20.23s

$ python -m pytest tests/test_api_contract.py tests/test_audit_endpoint.py \
    tests/test_audit_verify_endpoint.py tests/test_auth_rbac.py tests/test_golden_path_e2e.py \
    tests/test_tamper_detection.py tests/test_tmx_3012c_request_autoinjection.py -q
................................s......                                  [100%]
38 passed, 1 skipped, 2 warnings in 23.72s
```

`ruff check` on all three changed/new files: `All checks passed!`.

`python scripts/export_contract.py` run manually: `Wrote .../contract/openapi.json (74 schemas,
contract_version join key: 1.1.0)`.

## 6. Red team

- Ran the Tier-2 22-item checklist against the diff (mentally + via `ruff`): no bare `except`, no
  `print()`, no mutable default arguments (`CONTRACT_VERSION` default is an immutable `str`), no
  `Any`/`type: ignore` introduced.
- **Risk considered**: adding `contract_version` to the six existing response models could break a
  test asserting exact response-body equality. Checked by running every test file that imports
  `app.schemas.api_v1` directly (5 files) AND every test file that exercises the v1 routes via a
  FastAPI `TestClient` (7 more files, found via grep for `api/v1/translations|api/v1/audit`) — 99
  tests total across both runs, all green. No exact-equality assertion broke.
- **Risk considered**: `TranslationDisposition`/`MqmSummary`/etc. are not reachable from any
  registered route, so `app.openapi()` alone silently omits them — a reSCApe client generator run
  against the naive export would get a contract that's missing exactly the models ADR-0009 clause 3
  says reSCApe needs. Caught by AC-6's own test (initially failed after first implementation pass);
  fixed by merging `pydantic.json_schema.models_json_schema` output into `components.schemas` before
  writing (see stage 7).
- **Risk considered**: `tm_match_key` bind-revalidation — is it really deterministic AND
  order-independent of dict construction? `json.dumps(..., sort_keys=True)` guarantees key order
  doesn't affect the digest; verified in `test_tm_match_key_deterministic_and_bind_revalidates_on_termbase_change`.
  Not tested here (out of scope, no TM store exists yet): whether a single-character delimiter-only
  change to one input can collide with a different partition of the three fields — JSON encoding with
  proper string escaping makes this practically impossible for realistic hash/locale/version-id
  inputs, and this mirrors an already-reviewed pattern in the codebase rather than inventing a new
  one.
- **Failure mode if this code is wrong in production**: since nothing is wired to a live route this
  loop, the blast radius of a schema defect is limited to (a) a malformed `contract/openapi.json`
  that produces a broken generated client on reSCApe's side (caught at their build/codegen step, not
  silently at runtime), and (b) a future wiring loop discovering the field names don't match what a
  handler expects (caught by that loop's own tests, since nothing consumes these types yet). No
  regulated-path behaviour changes this loop.
- `mypy` was invoked twice on the two changed source files. The first full run (~15 min, this repo's
  whole-codebase dependency graph, cold cache) surfaced one real defect in the diff: line 112 of
  `scripts/export_contract.py` typed `info` as `object` (not `dict[str, object]`) because the
  isinstance guard checked a *separate* `schema.get("info")` call rather than the assigned variable —
  fixed by narrowing on the same variable (`raw_info` → `info`), the standard mypy idiom, mirrored for
  `components`/`schemas` too. Every OTHER error in that first run's output (`app/api/segments.py`,
  `app/agents/graph.py`, `app/agents/runner.py`, …) is pre-existing debt in files this loop never
  touched — confirmed by `git diff` showing zero changes to those files. A second scoped run (warm
  cache) was started to confirm the fix but did not return within this loop's time budget in this
  environment (two separate ~200s+ waits, still 0 bytes of output); rather than block indefinitely on
  a slow whole-repo mypy invocation for two files with no first-party changes outside them, closure
  relies on: (a) the one real error mypy found being fixed with a standard, unambiguous pattern,
  (b) `git diff` confirming zero new `Any` or `type: ignore` anywhere in the diff (direct grep, the
  ratchet's specific gate), and (c) `ruff check` clean on all three files. Flagging this honestly
  rather than claiming an unobserved second-run green.

## 7. Fix

- **AC-6 gap found and fixed**: the first pass of `export_openapi()` called only `app.openapi()`,
  which — being FastAPI's own route-schema walker — omitted `TranslationDisposition`, `MqmSummary`,
  `ProvenanceRecord`, `AuditRef`, `SegmentResult`, `JobResultResponse` (not referenced by any route).
  Added `_merge_unwired_contract_schemas()`, using `pydantic.json_schema.models_json_schema` pointed
  at the same `#/components/schemas/{model}` ref template FastAPI uses, to merge those definitions in
  before the write. Re-ran `python scripts/export_contract.py`; verified all 9 new schema names present
  in `contract/openapi.json` (manual check, then folded into
  `test_export_contract_script_produces_valid_openapi_with_new_schema_names`, both green — see stage 5).
- No other findings.

**G3 completion check**: this is greenfield schema/tooling addition, not a bug fix, so there is no
user-visible failure to reproduce. The falsifiable ACs (AC-1..AC-6) are the completion bar instead,
and all six are green per stage 5's captured output. Source was changed (not tests-only): 8 new
models/enum, 1 new constant, 6 modified response classes, 1 new pure function, 1 new script, plus the
generated `contract/openapi.json` artifact.

## 8. Deploy

- [x] Commit: `29e0b46bb91f2e2e0b7d74567287071e04139d6d` on branch `loop/seam-contract` (local; not pushed)
- [ ] CI green: not run (local loop only; no push this loop — worksheet stays `[Verify]`, per instructions: exactly one commit, no push)
- [ ] `.context/active_tasks.md` updated — orchestrator-owned, not edited by this loop
- [ ] Ratchet baseline updated — N/A, no `Any`/`type: ignore` introduced (verified by diff grep, stage 6)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T12:18Z | — | `[Spec]` | Created |
| 2026-07-22T13:50Z | `[Spec]` | `[Verify]` | Red tests written + failed pre-implementation; schema + helper + export script implemented; AC-1..AC-6 green; backwards-compat suites green (99 tests total); self red-team done, one AC-6 gap found + fixed; on branch `loop/seam-contract`, commit pending, merge pending |
