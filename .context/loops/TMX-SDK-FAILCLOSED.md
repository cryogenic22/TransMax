# TMX-SDK-FAILCLOSED — SDK pipeline fails closed on missing provider / bad model response

**State**: `[Spec]`
**Owner**: Agent & AI
**Sprint**: ADR-0008 convergence — Hazard 1 (A3)
**Started**: 2026-07-21
**Closed**: —
**Reversibility**: `two-way` — replaces two silent fallbacks with typed raises + an explicit opt-in passthrough flag. No schema, no persisted-artifact shape change, no public method signature removed. It DOES change SDK runtime behaviour for any caller that today relies on the silent `[lang] source`/`{}` fallback — but that reliance is itself the hazard; revertable by restoring the fallbacks.
**Pre-mortem**: if this fails in production, the failure mode is a *false fail-closed* — a legitimate SDK translation job raises `PROVIDER_UNAVAILABLE`/`INVALID_MODEL_RESPONSE` when it should have succeeded, blocking a valid job. Mitigated by: (a) the raise only fires on a genuinely-absent provider or a genuinely-unparseable response; (b) an explicit `allow_passthrough` opt-in keeps the headless-testing path working; (c) a valid-but-empty model response (0 segments) is handled distinctly from a parse failure.
**Blast radius**: `transmax_sdk/pipeline/pipeline.py` (+ a typed-error home in the SDK). The SDK/MCP surface — NOT the live FastAPI REST path today (that path is `app/`, unaffected). Tests under `tests/` that exercise the SDK pipeline. No frontend, no DB, no migration.

**Loop-driven-dev gates**:
- [ ] **G1 Anti-bloat** — five-test rubric filled at end of stage 2 / start of stage 3 (below).
- [ ] **G2 Reproduce-the-failure** — this is a latent-hazard ticket (A3), user-visible when the SDK ships. Spirit honoured: a red test asserts the CURRENT fabrication/`{}` behaviour, then the fix flips it to a typed raise.
- [ ] **G3 Completion** — the fabricated `[lang] source` labelled "MT" and the silent `{}` are GONE from the default path (proven by tests that the raise fires), not merely documented.

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

_(pending scoping — awaiting existing-error-types / passthrough-config / test-inventory facts)_

## 4. Code

_(pending)_

## 5. Eval / Test

_(pending)_

## 6. Red team

_(pending)_

## 7. Fix

_(pending)_

## 8. Deploy

- [ ] Commit: <SHA>
- [ ] Pushed to `origin/feat/vision-delivery-2`
- [ ] `.context/active_tasks.md` updated (TMX-SDK-FAILCLOSED → Done)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-21 | — | `[Spec]` | Created under the ADR-0008 spine-first order (Hazard 1). Surface mapped to `pipeline.py:_translate` (fabrication) + `_parse_translations` ({} swallow). Scoping agent dispatched for error-types + passthrough-config + test inventory. |
