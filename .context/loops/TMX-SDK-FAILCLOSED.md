# TMX-SDK-FAILCLOSED — SDK pipeline fails closed on missing provider / bad model response

**State**: `[Verify]` — on branch `loop/sdk-failclosed`; merge pending
**Owner**: Agent & AI
**Sprint**: ADR-0008 convergence — Hazard 1 (A3)
**Started**: 2026-07-21
**Closed**: —
**Reversibility**: `two-way` — replaces two silent fallbacks with typed raises + an explicit opt-in passthrough flag. No schema, no persisted-artifact shape change, no public method signature removed. It DOES change SDK runtime behaviour for any caller that today relies on the silent `[lang] source`/`{}` fallback — but that reliance is itself the hazard; revertable by restoring the fallbacks.
**Pre-mortem**: if this fails in production, the failure mode is a *false fail-closed* — a legitimate SDK translation job raises `PROVIDER_UNAVAILABLE`/`INVALID_MODEL_RESPONSE` when it should have succeeded, blocking a valid job. Mitigated by: (a) the raise only fires on a genuinely-absent provider or a genuinely-unparseable response; (b) an explicit `allow_passthrough` opt-in keeps the headless-testing path working; (c) a valid-but-empty model response (0 segments) is handled distinctly from a parse failure.
**Blast radius**: `transmax_sdk/pipeline/pipeline.py` (+ a typed-error home in the SDK). The SDK/MCP surface — NOT the live FastAPI REST path today (that path is `app/`, unaffected). Tests under `tests/` that exercise the SDK pipeline. No frontend, no DB, no migration.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — net-new code is one minimal errors module (no existing typed base anywhere in `transmax_sdk`; AC-5 requires one), one config flag, one guard helper. Five-test rubric: functional depth YES (typed errors a caller can branch on), end-user value YES (a reviewer can no longer sign fabricated output), trust YES (provenance labels become earned), robustness YES (three silent/crash failure modes removed), stability YES (10 real-behaviour tests).
- [x] **G2 Reproduce-the-failure** — red run pre-fix: `9 failed, 1 passed` with verbatim `DID NOT RAISE` / `assert 'MT' == ...` evidence in stage 5.
- [x] **G3 Completion** — `pipeline.py` source changed (fabrication + `{}` swallow removed); the repro (headless `execute`, corrupt-JSON `execute`) now raises typed errors, proven green in stage 5.

---

## 1. Task

`transmax_sdk/pipeline/pipeline.py` has two A3 ("no silent fallback in regulated paths") violations that produce or hide regulator-facing translation artefacts:

1. **Fabrication** — `_translate` (`pipeline.py:~112-118`): when `self._llm is None`, it writes `state.translations[seg] = f"[{target_lang}] {source_text}"` and labels the source `"MT"`. That is the untranslated **source text**, dressed as a machine translation. A reviewer or downstream gate cannot tell it from a real MT output — the exact "reviewer signs mock content as real" worst case A3 exists to prevent.
2. **Swallowed parse failure** — `_parse_translations` (`pipeline.py:~311-317`): on `json.JSONDecodeError`/`KeyError` it returns `{}`. An unparseable or malformed model response therefore yields **no translation, no error** — the segment silently vanishes (the quality gate skips empty translations), so a broken model call looks like "nothing to do".

The ticket: make the SDK pipeline **fail closed** — raise typed `PROVIDER_UNAVAILABLE` / `INVALID_MODEL_RESPONSE` errors instead — while preserving the legitimate headless-testing passthrough behind an **explicit opt-in** so failing-closed-by-default never fabricates and never hides a bad response.

Addenda at play: **A3** (no silent fallback / no substitute in a regulated artefact path — the core of this loop), **A2** (quality is enforced at gates, not by silently emitting empty/fake segments), product principle **"no vacuous green"** (a swallowed `{}` is a green run that did nothing).

## 2. Spec — acceptance criteria

- [ ] AC-1: With no LLM provider configured (`self._llm is None`) AND passthrough NOT explicitly enabled, `_translate` raises a typed `ProviderUnavailableError` (stable `.code == "PROVIDER_UNAVAILABLE"`) — it never writes a fabricated `[lang] source` translation and never labels one `"MT"`.
- [ ] AC-2: An explicit opt-in (a pipeline/config flag, default **off**) preserves the headless-testing passthrough. When enabled, the passthrough output is labelled with an **honest, non-"MT" source tag** (e.g. `"PASSTHROUGH"`) so it can never be mistaken for a real machine translation downstream.
- [ ] AC-3: `_parse_translations` raises a typed `InvalidModelResponseError` (`.code == "INVALID_MODEL_RESPONSE"`) on `json.JSONDecodeError` or a missing `segment_id`/`target_text` key — it never silently returns `{}`. The error carries debug context (the underlying parse error + a truncated snippet of the offending content).
- [ ] AC-4: A **valid** model response that legitimately contains **zero** segments (parseable JSON, empty `segments` list) is NOT an error — it is distinct from a parse FAILURE. (Guards against over-firing AC-3.)
- [ ] AC-5: The typed errors extend a common SDK base error (reuse an existing base if one exists; otherwise a minimal new one) with a stable string `.code`, so callers can `except` and branch. No bare `except`, no `Any` leak.
- [ ] AC-6: Every existing SDK pipeline test still passes — updated where (and only where) it relied on the removed silent behaviour — plus new tests that (a) prove each raise fires, (b) prove the `allow_passthrough` opt-in works and is labelled non-"MT", (c) pin AC-4 (valid-empty ≠ parse-failure).

Out of scope for this ticket: wiring the SDK into the live REST path (TMX-3227/3228); the v1 `". ".join` IR-reconstruction hazard (separate loop TMX-V1-DURABLE-IR); retry/backoff/circuit-breaking on provider errors (a resilience concern, not a fail-closed correctness concern); changing `app/` behaviour (untouched).

## 3. Design

**Scoping facts** (verified in-tree): there is NO central errors module in `transmax_sdk` — the only exception classes are `CircuitBreakerOpenError` (`resilience/circuit_breaker.py`) and `RetryExhaustedError` (`resilience/retry.py`), both resilience-local with no shared base. Passthrough today fires from `pipeline.py:113-118` whenever `self._llm is None`. No code outside `pipeline.py` consumes the `translation_source` label values (grep: only `types.py` serialisation + tests).

**Approach**:
1. **New minimal `transmax_sdk/errors.py`** (G1-justified: AC-5 needs a common typed base and none exists; ticket authorises "otherwise a minimal new one"): `TransMaxSDKError(Exception)` with stable class attr `code: str`; `ProviderUnavailableError` (`code="PROVIDER_UNAVAILABLE"`); `InvalidModelResponseError` (`code="INVALID_MODEL_RESPONSE"`, carries `raw_length: int` + `raw_sha256: str` of the offending payload).
2. **Config opt-in**: `SDKConfig.allow_passthrough: bool = False`; `DefaultTranslationPipeline(allow_passthrough: bool = False)`; wired in `container._make_pipeline`. Passthrough output = the **unaltered source text** (not the `[lang] …` fabrication) labelled `PASSTHROUGH_UNTRANSLATED` — never `"MT"`.
3. **Fail closed in `_translate`**: when no provider exists at all (`self._llm is None and not self._llm_providers`) and passthrough is not enabled → raise `ProviderUnavailableError` with an actionable message naming the opt-in. A `_require_provider` guard also covers the partial-wiring holes (default provider `None` while named providers exist; a smart-route step resolving to nothing) which today crash with untyped `AttributeError: 'NoneType'`.
4. **Fail closed in `_parse_translations`**: raise `InvalidModelResponseError` on `json.JSONDecodeError | KeyError | TypeError | AttributeError` (the latter two close the sibling crash paths: non-object JSON, non-dict segment entries). A parseable response with zero segments stays a valid empty result (AC-4).
5. **`_build_result` default label**: `translation_sources.get(seg, "MT")` → `.get(seg, "UNTRANSLATED")` — same A3 defect class in the same file: an absent translation must not claim MT provenance.

**AC-3 amendment (declared, not silent)**: AC-3 as written asks the error to carry "a truncated snippet of the offending content". The orchestrator ticket supersedes this: "carry a length/hash of the raw payload, NOT the payload" — model output in a pharma pipeline can contain regulated/PII content, and a payload snippet inside an exception message leaks into logs (lesson L-002 class). Implemented: underlying parse-error type+message (never contains model content — only our lookup keys and json positions) + `raw_length` + `raw_sha256`.

**Rejected alternatives**:
- *Errors inside `types.py`* — mixes an exception hierarchy into the dataclass module; a dedicated `errors.py` is the conventional SDK import surface the ticket names.
- *Reusing `CircuitBreakerOpenError`/`RetryExhaustedError` as base* — they are resilience-specific; retrofitting a shared base onto them is out-of-scope churn.
- *Env-var opt-in* — invisible configuration violates the "explicit opt-in" spirit; a typed config field is auditable.
- *Keeping the `[lang] source` shape under passthrough* — the prefix is fabricated decoration; honest passthrough returns the source text verbatim so nothing downstream can mistake it for target-language output.
- *Exporting the errors from `transmax_sdk/__init__.py`* — `__init__.py` is outside the ticket scope list; callers import `transmax_sdk.errors` directly. Noted as a follow-up nicety.

**Ordering note (G2 mechanics)**: `errors.py` + the red-test file are created BEFORE the pipeline fix so the red run shows the behavioural failures (`DID NOT RAISE`, fabricated `MT` label, `TypeError: unexpected keyword argument 'allow_passthrough'`) instead of a bare collection ImportError. The errors module alone changes no behaviour.

## 4. Code

| File | Change |
|---|---|
| `transmax_sdk/errors.py` | **NEW** — `TransMaxSDKError` base (stable `.code`), `ProviderUnavailableError` (`PROVIDER_UNAVAILABLE`), `InvalidModelResponseError` (`INVALID_MODEL_RESPONSE`, carries `raw_length` + `raw_sha256`, never the payload). |
| `transmax_sdk/pipeline/pipeline.py:34-58` | `allow_passthrough: bool = False` constructor param. |
| `transmax_sdk/pipeline/pipeline.py:105-118` | `_require_provider` guard — typed raise instead of `AttributeError: 'NoneType'` when a step resolves to no provider. |
| `transmax_sdk/pipeline/pipeline.py:129-144` | `_translate`: fabricated `[lang] source` + `"MT"` label GONE. No provider at all → `ProviderUnavailableError` unless `allow_passthrough=True`; opt-in emits unaltered source text labelled `PASSTHROUGH_UNTRANSLATED`. |
| `transmax_sdk/pipeline/pipeline.py:160,188` | `_direct_translate`/`_pivot_translate` dereference a `_require_provider`-checked local. |
| `transmax_sdk/pipeline/pipeline.py:246-256` | Smart-route step providers wrapped in `_require_provider`. |
| `transmax_sdk/pipeline/pipeline.py:352-373` | `_parse_translations`: silent `{}` GONE — raises `InvalidModelResponseError` on `JSONDecodeError|KeyError|TypeError|AttributeError` (TypeError/AttributeError close the non-object-JSON crash paths). Valid zero-segment response stays a valid empty result (AC-4). |
| `transmax_sdk/pipeline/pipeline.py:416-419` | `_build_result` absent-translation label default `"MT"` → `"UNTRANSLATED"` (same A3 class: an empty translation must not claim MT provenance). |
| `transmax_sdk/config.py:36-40` | `SDKConfig.allow_passthrough: bool = False`. |
| `transmax_sdk/container.py:228` | `_make_pipeline` wires `allow_passthrough=config.allow_passthrough`. |
| `tests/sdk/test_pipeline_failclosed.py` | **NEW** — 10 tests pinning AC-1..AC-5 (see stage 5). |
| `tests/sdk/test_{pipeline_standalone,pipeline_tm_bypass,pipeline_any_to_any,pipeline_cost,e2e_pipeline,e2e_any_to_any,e2e_cost_tracking,mcp_tools,pipeline_smart_routing,sdk_public_api}.py` | Headless runs that relied on the silent fabrication now opt in explicitly (`allow_passthrough=True`); `test_partial_tm_hits` asserts `PASSTHROUGH_UNTRANSLATED` instead of the fabricated `"MT"`. |

Incidental hygiene in touched files (would otherwise fail the mandatory pre-commit hooks): removed 3 pre-existing unused imports (`List`, `QualityDefect` in pipeline.py; `Type` in container.py); `ruff format` applied to the touched test files (they pre-dated the format hook — verified UNFORMATTED at baseline via `git show HEAD:<f> | ruff format --check -`).

## 5. Eval / Test

**G2 red run (pre-fix), verbatim** — `python -m pytest tests/sdk/test_pipeline_failclosed.py -q` → `9 failed, 1 passed in 0.81s` (the 1 pass is the TM-covered non-regression pin, green by design):

```
E       Failed: DID NOT RAISE <class 'transmax_sdk.errors.ProviderUnavailableError'>
E       TypeError: DefaultTranslationPipeline.__init__() got an unexpected keyword argument 'allow_passthrough'
E       AssertionError: assert 'MT' == 'PASSTHROUGH_UNTRANSLATED'
E       Failed: DID NOT RAISE <class 'transmax_sdk.errors.InvalidModelResponseError'>
E           AttributeError: 'list' object has no attribute 'get'
E       AssertionError: assert 'MT' == 'UNTRANSLATED'
```

(The `errors.py` module + red tests were created before the pipeline fix so the red run shows behavioural failures, not a collection ImportError. The `AttributeError` line is the pre-existing uncaught crash on non-object JSON — now a typed error.)

**Green runs (post-fix), verbatim**:

- `python -m pytest tests/sdk/test_pipeline_failclosed.py -q` → `10 passed in 1.32s`
- `python -m pytest tests/sdk -q` (full SDK suite) → `318 passed in 2.93s` (baseline pre-change: `308 passed in 4.72s`)
- `python scripts/ratchet.py check` → `✓ Ratchet OK — all 17 metrics at or better than baseline.`
- `python -m scripts.judge_eval_gate check` → `"result": "PASS_STRUCTURE_ONLY"`

**AC coverage**: AC-1 → `test_no_provider_raises_typed_error`, `test_error_message_names_the_opt_in`, `test_sdk_facade_default_fails_closed`; AC-2 → `test_passthrough_is_honestly_labelled`, `test_sdk_facade_passthrough_via_config`; AC-3 → `test_corrupt_json_raises_typed_error`, `test_missing_target_text_key_raises_typed_error`, `test_non_object_json_raises_typed_error`; AC-4 → `test_valid_empty_response_is_not_an_error`; AC-5 → `.code` + `isinstance(..., TransMaxSDKError)` assertions; AC-6 → full-suite 318 green with only fabrication-reliant tests updated.

## 6. Red team

1. **Does any production surface break?** `transmax_mcp/server.py` builds the SDK from env API keys; with no keys it previously served fabricated "MT" — now it raises typed errors. That IS the intended RS-02 fail-closed behaviour, not a regression. `app/` does not import the SDK pipeline (verified by grep). — resolved by design.
2. **Partial model response** (valid JSON, but a requested segment absent): not a parse failure, so no raise; segment lands with empty `translated_text` and now label `UNTRANSLATED` (not `MT`), quality gate skips it, confidence 0. Honest but silent-ish — a completeness gate ("every requested segment answered") is a QUALITY concern that belongs in the gate layer (A2), out of this loop's scope. **Residual, noted.**
3. **`SegmentResult.translation_source` dataclass default is still `"MT"`** (`types.py:114`). Unexercised via the pipeline after this fix (`_build_result` always passes an explicit label) but a direct constructor elsewhere could still inherit an unearned claim. `types.py` is outside this ticket's scope list. **Residual, noted for follow-up.**
4. **Non-string `target_text`** (e.g. model returns an int): passes `_parse_translations` untyped. Deep schema validation is gate-layer work (A2); not added (G1). **Residual, noted.**
5. **Does the raw parse-error message leak payload?** Checked each caught type: `JSONDecodeError` messages carry only line/col positions; `KeyError` carries OUR lookup key; `TypeError`/`AttributeError` carry type names. Pinned by `assert payload not in str(err)`. — resolved.
6. **Pydantic silently ignoring `allow_passthrough`** (the pre-fix facade test failed exactly this way): now a real `SDKConfig` field, pinned by `test_sdk_facade_passthrough_via_config`. — resolved.
7. **Back-compat**: constructor param is additive with default `False`; no public signature removed. Callers relying on silent fabrication now get a typed, actionable error naming the opt-in — the intended breaking change of this ticket. — accepted.

## 7. Fix

Findings 1, 5, 6, 7 resolved in the main diff (design + tests above). Findings 2, 3, 4 are declared residuals outside this ticket's scope list (A2 gate-layer completeness; `types.py` default) — carried in this worksheet rather than silently expanded into scope (G1).

## 8. Deploy

- [x] Commit: see status log (single commit on `loop/sdk-failclosed`)
- [ ] Pushed — NOT pushed; merge pending by orchestrator
- [ ] `.context/active_tasks.md` — owned by orchestrator; not touched

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-21 | — | `[Spec]` | Created under the ADR-0008 spine-first order (Hazard 1). Surface mapped to `pipeline.py:_translate` (fabrication) + `_parse_translations` ({} swallow). Scoping agent dispatched for error-types + passthrough-config + test inventory. |
| 2026-07-22 | `[Spec]` | `[Verify]` | Loop agent (worktree `sdk-failclosed`, branch `loop/sdk-failclosed`): stages 3-7 complete. Red 9-failed pre-fix, full SDK suite 318 green post-fix. AC-3 amended (declared in stage 3): error carries length+sha256 of raw payload, not a snippet — orchestrator ticket supersedes, payload may contain regulated content. Single commit on branch; NOT pushed; merge pending by orchestrator. |
