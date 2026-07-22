# TMX-SEAM-CONFORMANCE — the seam conformance suite (CROSS-REPO-PROTOCOL Rule 4)

**State**: `[Verify]`
**Owner**: Platform (seam work, TransMax side)
**Sprint**: n/a (loop-driven)
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — new test module only, no source/schema/contract changes.
**Pre-mortem**: if this fails in production, the failure mode is a false sense of seam safety — a
regressed invariant (e.g. a future edit that lets a TM-bound segment skip the deterministic gates, or
reintroduces a fabricated "MT"/"transmax_ai" provenance default) ships undetected because this suite
either (a) doesn't exercise the real code path, or (b) reports green by skipping the assertion that
would have caught it. Mitigated by the meta-honesty suite (`TestSeamSuiteHonesty`), which fails the
build if a COVERED invariant's test is skip-marked or if the SKIPPED/PENDING sets drift from what is
actually registered — the two ways this suite could silently go vacuous are both mechanically checked.
**Blast radius**: `tests/seam/__init__.py` (new), `tests/seam/test_conformance.py` (new, 459 lines). No
source files touched — this is a test-only addition on top of the TMX-SEAM-CONTRACT commit already on
this branch. No route, schema, or service module changed.

**Seam**: contract v1.1.0 — this loop tests engine-side behaviour only (no live reSCApe pair in this
worktree); per CROSS-REPO-PROTOCOL Rule 4, the canonical suite eventually runs against a live pair in
both CIs, but that pair does not exist here. See §3 Design for how each invariant is honestly scoped.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat (between stage 2 and 3)** — see §3 Design.
- [ ] **G2 Reproduce-the-failure** — N/A in the classic sense (this is a new test suite, not a bug
      fix), but the orchestrator's RED-TEST-FIRST instruction was still honoured: §5 captures the suite
      failing to collect (file/dir not found) before it existed, then green after implementation. A
      second, stronger red/green cycle (§5) demonstrates the suite's own honesty mechanism actually
      catches a vacuous skip, not just that the file parses.
- [x] **G3 Completion (between stage 7 and 8)** — see §7.

---

## 1. Task

CROSS-REPO-PROTOCOL Rule 4 defines nine standing invariants (C-1..C-9) TransMax and reSCApe must both
hold across the seam, enforced by one conformance suite run by both CIs against a live pair — mocking
the counterpart is prohibited. This worktree has no reSCApe counterpart to run against (it is the
TransMax-side worktree, mid-way through the seam work — TMX-SEAM-CONTRACT shipped the contract schema
as the prior commit on this branch, TMX-SEAM-CLIENT which builds the HTTP client that WOULD BE the live
pair is still `[BLOCKED]`). This loop builds the TransMax-side half of the suite honestly: each
invariant that has real, in-process engine-side behaviour to test is exercised for real (never mocking
reSCApe — only ever a canned in-process LLM provider stand-in, which is TransMax's own dependency, not
the counterpart); each invariant that genuinely cannot be tested without a live pair or without an
unbuilt engine capability is committed as a real (unreachable but documented) test body under
`pytest.mark.skip`, with a reason naming the blocking, board-tracked ticket.

Addenda in play: A3 (no silent fallbacks — this is the whole point of C-1/C-2/C-4), A1 (C-8's audit
chain pointer), A5 (C-7's stable request_id).

## 2. Spec — acceptance criteria

- [x] AC-1: `tests/seam/test_conformance.py` exists, is collected by pytest, and every one of the nine
      invariants C-1..C-9 has at least one test function bound to it (covered or skip-marked — none
      silently absent).
- [x] AC-2: C-2, C-4, C-5, C-7, C-9 each have at least one **non-skipped** test whose assertions
      exercise real engine-side behaviour (never a mock of reSCApe).
- [x] AC-3: C-1, C-3, C-6, C-8 are each `pytest.mark.skip`-marked with a `reason` that names an
      existing, board-tracked blocking ticket ID (`TMX-...`) — not a bare "not implemented".
- [x] AC-4: a meta-test (`TestSeamSuiteHonesty`) fails the build if (a) a COVERED invariant's test is
      skip-marked, (b) the declared `PENDING_INVARIANTS` count diverges from a declared constant, or
      (c) a skip-marked test's reason lacks a named ticket. Demonstrated in §5 by actually breaking the
      suite and observing the meta-test catch it (not asserted from prose — reproduced).
- [x] AC-5: the suite runs green (`pytest tests/seam/ -q`) and does not regress any pre-existing test
      file that shares the code paths it exercises (`tests/sdk/test_pipeline_failclosed.py`,
      `tests/sdk/test_pipeline_tm_bypass.py`, `tests/test_api_contract.py`, `tests/test_webhook_fire.py`,
      `tests/test_seam_contract.py`).

Out of scope for this ticket (explicit, per ticket instruction): C-1, C-3, C-6, C-8 do not get real
assertions this loop — they need a live reSCApe pair or an engine capability (TMX-LANGDETECT-HOLD) that
doesn't exist yet. No contract schema changes (`app/schemas/api_v1.py` untouched — verified by diff).
No reSCApe-side worksheet or commit.

## 3. Design

**Where the tests live**: `tests/seam/`, a new directory — this is the first cross-repo-protocol test
module and there is no existing "seam" test location to extend into (checked: no `tests/seam*` or
`tests/*conformance*` existed before this loop). Mirrors the existing `tests/sdk/` package convention
(same `__init__.py`-as-package pattern, confirmed by reading `tests/sdk/__init__.py`). G1: this is new
capability (a standing conformance gate CROSS-REPO-PROTOCOL Rule 4 requires and no existing test module
provides), not a duplicate — the closest existing coverage (`tests/sdk/test_pipeline_failclosed.py`,
`tests/sdk/test_pipeline_tm_bypass.py`) tests the SDK pipeline's own correctness in isolation, not the
seam invariants as a named, audited, honesty-gated set. Reusing those files' assertions inline (rather
than importing/re-running them) keeps this suite self-contained and traceable to the C-N invariant IDs
directly, which is the whole point of a conformance suite distinct from unit tests.

**Per-invariant scoping** (the substantive design decision this loop makes):

| Invariant | Status | Why |
|---|---|---|
| C-1 | SKIP | needs a live reSCApe pair (no mocking allowed); blocked on `TMX-SEAM-CLIENT` |
| C-2 | COVERED | `transmax_sdk.pipeline.pipeline.DefaultTranslationPipeline` already raises typed `ProviderUnavailableError`/`InvalidModelResponseError` (TMX-SDK-FAILCLOSED, shipped) — real, in-process, no live pair needed |
| C-3 | SKIP | needs `TMX-LANGDETECT-HOLD` (READY, not yet built) — nothing to assert against |
| C-4 | COVERED | two angles: (a) the contract's `ProvenanceRecord` fields all default `None` — checked directly; (b) the pipeline's real "no earned translation" path labels `UNTRANSLATED`, never `MT` |
| C-5 | COVERED | `DefaultTranslationPipeline._run_quality_gates` iterates ALL segments (including TM-bound ones) — verified by storing a TM entry with a dropped number and confirming the `NUMERIC_MISMATCH` gate still fires on the `TM_EXACT` segment |
| C-6 | SKIP | needs a live pair with resolvable `signature_records`; no wiring ticket filed yet for the TransMax-side lockability gate |
| C-7 | COVERED | `app/api/v1/translations.py`'s `Document.client_request_id` lookup already enforces this — exercised through a real tmp-SQLite DB (`fresh_engine_for_db`) and a real `TestClient`, not a mocked query |
| C-8 | SKIP | needs a live pair to independently re-verify `chain_head_hash` across the seam (Rule 4 forbids mocking the counterpart); the result block (`AuditRef`) is also not wired to any live route yet |
| C-9 | PENDING (a subset of COVERED) | no language-tier engine exists (`TMX-LANG-TIERS` READY, unbuilt); the only honest assertion available is that `ProvenanceRecord.language_tier` exists, is `Optional`, and defaults `None` |

**Honesty mechanism** (the ticket's CRITICAL requirement): a `covers(invariant_id)` decorator registers
every real test into `INVARIANT_COVERAGE`; a `skip_covers(invariant_id, reason=...)` decorator applies
`pytest.mark.skip` AND registers into `SKIP_COVERAGE`. `TestSeamSuiteHonesty` then mechanically checks:
(1) the two ID sets partition all nine invariants with no overlap; (2) every `COVERED_INVARIANTS` id has
≥1 registered test that is NOT skip-marked (introspects `fn.pytestmark`, not a self-report); (3)
`len(PENDING_INVARIANTS) == DECLARED_PENDING_COUNT` (a literal constant, `1`); (4) every skip-marked
test's `reason` kwarg contains the literal substring `"TMX-"`; (5) the registries exactly equal the
declared sets, so a future edit that adds/removes a test without updating the header table fails loudly
instead of silently passing. This is what makes "silently skip everything" fail the build rather than
pass it — proven in §5 by deliberately skip-marking a COVERED test and observing the meta-test catch it.

**Alternatives considered:**
- *Self-reporting via a plain dict `{"C-2": "covered"}` with no introspection of the actual pytest
  marker* — rejected: this is exactly the vacuous-green shape the ticket warns against (a human/agent
  could mark something "covered" in the dict while the test itself is skip-marked, and nothing would
  catch the mismatch). The chosen design introspects `pytestmark` directly off the registered function
  object, so the claim and the marker cannot drift apart.
- *One `pytest.mark.skip(reason=...)` string per test, parsed by a meta-test with plain string
  matching against a fixed invariant->reason substring map* — rejected: brittle (breaks on any wording
  edit) and doesn't generalize; the substring check for `"TMX-"` is a weaker, more durable invariant
  ("names *a* ticket") that still catches the actual failure mode (a bare "not implemented" reason).
- *Running the C-1..C-9 assertions against a live reSCApe pair via `httpx` with a documented
  `SEAM_LIVE_PAIR_URL` env var, defaulting to skip when unset* — considered as a way to make C-1/C-6/C-8
  "real but conditionally skipped" rather than unconditionally skip-marked. Rejected for this loop: no
  reSCApe HTTP client exists yet on either side (`TMX-SEAM-CLIENT` is still `[BLOCKED]`), so there is
  literally no URL scheme, auth, or payload shape to code against — writing that test now would be
  guessing at an interface, which is worse than an honest skip. Revisit once `TMX-SEAM-CLIENT` ships.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `tests/seam/__init__.py` | new, 0 lines | package marker, mirrors `tests/sdk/__init__.py` |
| `tests/seam/test_conformance.py` | new, 459 lines | invariant registry (`covers`/`skip_covers`), 9 invariant test groups, `TestSeamSuiteHonesty` meta-suite |

No other files changed. `git diff --stat` against the prior commit on this branch confirms only these
two new files.

## 5. Eval / Test

**Red run (pre-implementation)** — the suite did not exist yet:

```
$ python -m pytest tests/seam/test_conformance.py -q
ERROR: file or directory not found: tests/seam/test_conformance.py


no tests ran in 0.15s
```

**Green run (post-implementation):**

```
$ python -m pytest tests/seam/test_conformance.py -v
...
tests/seam/test_conformance.py::TestC2FailClosedOnProviderAndModelResponse::test_no_provider_configured_raises_typed_provider_unavailable PASSED [  6%]
tests/seam/test_conformance.py::TestC2FailClosedOnProviderAndModelResponse::test_unparseable_model_response_raises_typed_invalid_model_response PASSED [ 12%]
tests/seam/test_conformance.py::TestC4NoUnearnedProvenance::test_fresh_provenance_record_defaults_to_none_never_a_plausible_string PASSED [ 18%]
tests/seam/test_conformance.py::TestC4NoUnearnedProvenance::test_untranslated_segment_is_labelled_untranslated_never_mt PASSED [ 25%]
tests/seam/test_conformance.py::TestC5TmBindingDoesNotSkipGates::test_tm_exact_segment_still_runs_the_numeric_gate PASSED [ 31%]
tests/seam/test_conformance.py::TestC7RequestIdIdempotency::test_duplicate_request_id_yields_one_job_not_two PASSED [ 37%]
tests/seam/test_conformance.py::TestC9LanguageTierPending::test_language_tier_field_exists_and_defaults_none_pending_engine PASSED [ 43%]
tests/seam/test_conformance.py::test_engine_unreachable_yields_typed_error_never_glossary_substitution SKIPPED [ 50%]
tests/seam/test_conformance.py::test_low_confidence_source_language_detection_yields_typed_hold SKIPPED [ 56%]
tests/seam/test_conformance.py::test_submission_bound_segment_without_signature_ref_cannot_be_lockable SKIPPED [ 62%]
tests/seam/test_conformance.py::test_every_result_carries_a_verifiable_chain_head_hash SKIPPED [ 68%]
tests/seam/test_conformance.py::TestSeamSuiteHonesty::test_all_nine_invariants_are_accounted_for_exactly_once PASSED [ 75%]
tests/seam/test_conformance.py::TestSeamSuiteHonesty::test_every_covered_invariant_has_at_least_one_nonskipped_test PASSED [ 81%]
tests/seam/test_conformance.py::TestSeamSuiteHonesty::test_pending_count_matches_the_declared_constant PASSED [ 87%]
tests/seam/test_conformance.py::TestSeamSuiteHonesty::test_every_skipped_invariant_carries_a_named_blocking_ticket PASSED [ 93%]
tests/seam/test_conformance.py::TestSeamSuiteHonesty::test_registered_invariants_match_the_declared_sets_exactly PASSED [100%]

======================= 12 passed, 4 skipped in 12.82s ========================
```

**Honesty-mechanism self-check (AC-4, reproduced not asserted):** wrote a scratch copy of the module
with `test_no_provider_configured_raises_typed_provider_unavailable` (a C-2-covering test) additionally
decorated `@pytest.mark.skip(reason="temp sanity check")`, ran it, observed the meta-test fail exactly
as designed, then deleted the scratch file (never committed):

```
$ python -m pytest tests/seam/_sanity_broken.py -q
...
E               AssertionError: TestC2FailClosedOnProviderAndModelResponse.test_no_provider_configured_raises_typed_provider_unavailable covers C-2 but is skip-marked - a skip-marked test cannot back a COVERED invariant (this is exactly the vacuous-green failure mode this meta-test exists to prevent).
E               assert not True
=========================== short test summary info ===========================
FAILED tests/seam/_sanity_broken.py::TestSeamSuiteHonesty::test_every_covered_invariant_has_at_least_one_nonskipped_test
1 failed, 10 passed, 5 skipped in 5.90s
```

**Backwards-compatibility / nearest-related suites:**

```
$ python -m pytest tests/seam/ tests/sdk/test_pipeline_failclosed.py tests/sdk/test_pipeline_tm_bypass.py \
    tests/test_api_contract.py tests/test_webhook_fire.py tests/test_seam_contract.py -q
.......ssss.......................................................       [100%]
62 passed, 4 skipped, 1 warning in 10.87s
```

`ruff check tests/seam/test_conformance.py tests/seam/__init__.py`: `All checks passed!`

`grep -n ': Any\b\|-> Any\b' tests/seam/test_conformance.py`: no matches. `grep -n 'type:\s*ignore'
tests/seam/test_conformance.py`: 4 matches, all `# type: ignore[import-not-found]` — the ratchet's own
regex (`scripts/ratchet.py:184`) explicitly exempts this exact form; it is used only inside the four
`pytest.mark.skip`-marked test bodies to satisfy mypy on an import of a module that genuinely does not
exist yet (`rescape_bridge_client`, `app.services.language_detection`,
`app.services.disposition_gate`) — the tests document intent for code that isn't built.

**Full repo test suite** — returned within the loop's time budget (backgrounded, ~4m15s):

```
$ python -m pytest tests/ -q --timeout=600
........................................................................ [  4%]
...
1482 passed, 6 skipped, 4 warnings in 254.74s (0:04:14)
```

Zero failures across the whole suite (1482 passed vs. 1375 at the last recorded baseline
TMX-CI-POSTGRES-FAILURES close — the delta includes this loop's 12 new passing tests plus everything
shipped since). 6 skipped = the 4 new C-1/C-3/C-6/C-8 skips from this loop + 2 pre-existing
(`test_golden_path_e2e` needs a live server; one other pre-existing skip unrelated to this diff).

`mypy` on the new file specifically: attempted (`python -m mypy tests/seam/test_conformance.py
--ignore-missing-imports`), did not return within a 60s bound — consistent with the sibling
TMX-SEAM-CONTRACT loop's documented finding on this same tree (cold-cache whole-repo dependency graph,
~15 min). Closure relies on: (a) `ruff check` clean, (b) grep-verified zero bare `Any`/`type: ignore` in
the new file (only the ratchet-exempt `[import-not-found]` form, 4 uses, all justified above), (c) the
full 1482-test run passing with zero failures, which would have surfaced any runtime type mismatch this
file's assertions could trigger. Flagging honestly rather than claiming an unobserved mypy green.

## 6. Red team

- Ran the Tier-2 checklist mentally + via `ruff`: no bare `except`, no `print()`, no mutable default
  arguments, no `Any` anywhere in the new file (grep-verified), `# type: ignore[import-not-found]` only
  in the ratchet-exempt form and only where genuinely needed (unbuilt-module imports inside
  never-executed skip-marked bodies).
- **Risk considered**: could the `covers`/`skip_covers` registries leak state across test *files* if
  pytest re-imports the module (e.g. under `-p xdist`)? Each worker process gets its own fresh module
  import, so the registries are per-process, matching how the module-level constants (`ALL_INVARIANTS`
  etc.) are already used elsewhere in this codebase's test suite. Not an issue for a single-process
  `pytest tests/seam/` run, which is how this loop verified it; flagging as a boundary condition rather
  than claiming it's proven safe under `-n auto`.
- **Risk considered**: does `TestC7RequestIdIdempotency` actually prove DB-level idempotency, or could
  it be passing because both POSTs hit an in-memory cache that has nothing to do with the real dedup
  logic? Checked by reading `app/api/v1/translations.py:44-50` directly — the lookup is a real
  `db.query(Document).filter(Document.client_request_id == ...)` against the `fresh_engine_for_db`
  tmp-SQLite database, not a mock (`mock_db.query.return_value...` pattern used by the PRE-EXISTING
  `tests/test_api_contract.py::test_idempotency_tmx011`, which mocks the DB entirely). This suite's C-7
  test is strictly stronger evidence than the pre-existing one: it proves the SECOND POST never even
  reaches `background_tasks.add_task` (asserted via the `calls` counter), which the mocked test cannot
  distinguish from "the mock happened to return the right thing."
- **Risk considered**: for C-5, could `NUMERIC_MISMATCH` have fired from a check OTHER than the
  deterministic gate actually running on the TM-bound segment — e.g. some pipeline stage that inspects
  `state.translations` post-hoc regardless of gate execution? Checked by reading
  `_run_quality_gates` (`transmax_sdk/pipeline/pipeline.py:361-374`): it is the ONLY writer of
  `state.defects`, and it iterates `state.segments` unconditionally (not filtered to
  non-TM-matched segments) — the assertion is against the actual code path, not an indirect signal.
- **Risk considered**: for C-4's "never MT" assertion — is `"UNTRANSLATED"` itself a magic string that
  could silently change without this test catching drift? The test asserts the POSITIVE
  (`== "UNTRANSLATED"`) AND the NEGATIVE (`!= "MT"`) so a rename to a third label would fail loud on the
  positive assertion rather than silently pass on the negative one alone.
- **Discovered but explicitly NOT fixed this loop (scope discipline, flagged honestly)**:
  `transmax_sdk/types.py:114` — `SegmentResult.translation_source: str = "MT"` — the dataclass field's
  OWN default is `"MT"`, which is exactly the unearned-provenance shape C-4 exists to forbid. Traced
  every construction site (`grep -rn "SegmentResult(" transmax_sdk/ app/` outside tests): there is
  exactly one, `pipeline.py:397`, and it ALWAYS passes `translation_source=state.translation_sources.get(
  seg.segment_id, "UNTRANSLATED")` explicitly — so the dangerous dataclass default is currently dead
  code, never reached through the real pipeline. It IS reachable by any future/external caller that
  constructs `SegmentResult(...)` directly (e.g. a hand-rolled test fixture, or a new call site) without
  setting `translation_source`. This loop's ticket SCOPE is `tests/seam/` only — no source changes — so
  it is not fixed here. Recording it explicitly rather than silently noticing and moving on: this is a
  one-line, low-risk, in-scope-for-a-future-loop fix (`str = "MT"` -> `str = "UNTRANSLATED"` on that one
  dataclass field) and belongs to whichever loop next touches `transmax_sdk/types.py`, or a dedicated
  small ticket if none is already planned.
- **Failure mode if this suite itself is wrong in production**: since it is test-only, the direct blast
  radius is zero (no source changed), but the INDIRECT risk is the pre-mortem above — a suite that
  claims to guard an invariant but doesn't. Mitigated as described in §3/§5's honesty-mechanism
  self-check.

## 7. Fix

No findings required a source-code fix — this loop is test-only, and the one discovered hazard
(`transmax_sdk/types.py:114`) is explicitly out of scope per SCOPE and documented above for follow-up
rather than fixed silently or fixed outside scope.

**G3 completion check**: falsifiable ACs are the completion bar (AC-1..AC-5), all green per §5's
captured output, including a REPRODUCED (not asserted) demonstration that the honesty mechanism (AC-4)
actually catches a vacuous-skip regression. Source added (test-only, by design — this ticket is
building a test suite, not fixing a bug): 2 new files, 459 test-module lines, 0 source files touched.

## 8. Deploy

- [x] Commit: `e30922fd74b6d0208edac92e0dfd689a194cb6a9` on branch `loop/seam-contract` (second commit on
      this branch, on top of `d5ae686` / TMX-SEAM-CONTRACT; local; not pushed)
- [ ] CI green: not run (local loop only; no push this loop — worksheet stays `[Verify]`, exactly one
      NEW commit, no push, per instructions; merge pending)
- [ ] `.context/active_tasks.md` updated — orchestrator-owned, not edited by this loop
- [ ] Ratchet baseline updated — N/A, no `Any`/bare `type: ignore` introduced (grep-verified in §5)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T13:46Z | — | `[Spec]` | Created; read ADR-0009, CROSS-REPO-PROTOCOL, prior commit's `app/schemas/api_v1.py` |
| 2026-07-22T14:10Z | `[Spec]` | `[Verify]` | Red run captured (file didn't exist); `tests/seam/test_conformance.py` implemented (9 invariants + honesty meta-suite); green (12 passed, 4 skipped); honesty mechanism reproduced-broken to confirm it actually catches vacuous skips; backwards-compat suites green (62 passed, 4 skipped); ruff clean; grep-verified no `Any`/bare `type: ignore`; self red-team done, one out-of-scope hazard documented (not fixed, per SCOPE); on branch `loop/seam-contract`, commit pending |
