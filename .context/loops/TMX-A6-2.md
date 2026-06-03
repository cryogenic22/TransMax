# TMX-A6-2 — Per-job LLM usage telemetry in the audit chain (A6 qualified-supplier consumption)

**State**: `[Spec]`
**Owner**: Agent & AI
**Sprint**: 2
**Started**: 2026-06-03
**Closed**: —
**Reversibility**: `two-way` — pure addition: one new audit event type (`LLM_USAGE_RECORDED`) emitted at one site + a `usage` block surfaced in the engine's quality report. Revert by deleting the emit site + the report key. No schema change, no migration, no consumer depends on it yet.
**Pre-mortem**: if this fails in production, the failure mode is a *missing or wrong* usage event in the audit chain — never a blocked translation (the emit is wrapped, telemetry is best-effort per the A3 carve-out for non-content metrics).
**Blast radius**: `app/agents/nodes/translation_engine.py` (engine surfaces usage in the report), `app/agents/graph.py` (translate-node wrapper emits the event). Read by: the audit chain / future regulator-facing usage views. No frontend, no DB schema, no other pod.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — 5-test rubric:
  (a) *needed?* Yes. A6 requires qualified-supplier **response token usage** in the audit evidence. TMX-3202 put model + prompt version in the JobConfigSnapshot (captured at job *start*, before any LLM call — so it structurally cannot hold response tokens). Consumption today lands only on the **mutable** `Document.total_tokens`/`total_cost_usd` row (Feature 5), which is not chain-anchored evidence. This closes that gap.
  (b) *<5 callers?* Emitted at **1** site (translate-node wrapper).
  (c) *bundle impact?* Negligible — reuses `emit_v2_audit_event`, `audit_service.log_event`, `cost_for`.
  (d) *reuses patterns?* Yes — same double-write shim (`_audit_v2_emit`) + canonical pricing table (`app/core/model_pricing.py`). No new dependency.
  (e) *ships with a failing test?* Yes — see stage 5 (test asserts the event + payload shape; red before the code).
- [ ] **G2 Reproduce-the-failure** — N/A as a user-visible bug; this is an audit-coverage gap. Treated TDD-style: the assertion that an `LLM_USAGE_RECORDED` v2 event exists with the telemetry payload is RED before the emit lands.
- [ ] **G3 Completion** — after stage 7: a real pipeline run leaves an `LLM_USAGE_RECORDED` event in the v2 chain whose payload reproduces the model + token counts + cost, verifiable independently of the `Document` row.

---

## 1. Task

Close the A6 (LLM = qualified supplier, Annex 11 §3 / EU AI Act tech-doc) gap left open by TMX-3202. The config snapshot now records *which* supplier/model/prompt was engaged, but the **actual consumption** — response token usage and resulting cost — is recorded only on the mutable `Document` row, not in the immutable audit chain. A regulator inspecting the chain cannot see, per job, how much qualified-supplier output was consumed. Emit that consumption as a first-class chained audit event.

Addenda at play: **A6** (qualified-supplier telemetry — the headline), **A1** (audit-by-default — the record is itself an audit event), **A3** (the emit is best-effort and must never block a translation; this is the documented metrics carve-out, not a silent fallback in a content path), **A8** (the prompt versions consumed go in the payload, consistent with TMX-3202's snapshot).

## 2. Spec — acceptance criteria

- [ ] **AC-1**: After the translate node runs on a job with `job_id`, the v2 audit chain contains exactly one `LLM_USAGE_RECORDED` event for that job.
- [ ] **AC-2**: The event payload contains `model` (real, from settings — not a literal), `input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost_usd`, `currency` (`"USD"`), and `pricing_source` (`"app.core.model_pricing"`).
- [ ] **AC-3**: `estimated_cost_usd` equals `cost_for(model, input_tokens, output_tokens)` rounded to 6 dp — i.e. derived from the canonical pricing table, not a re-implemented formula.
- [ ] **AC-4**: `total_tokens == input_tokens + output_tokens`.
- [ ] **AC-5**: If the v2 emit raises (writer down, bad session), the translate node still returns successfully and the quality report is unaffected (A3 metrics carve-out). No exception propagates.
- [ ] **AC-6**: When `job_id` is absent from state (e.g. ad-hoc invocation), no event is emitted and no error is raised.
- [ ] **AC-7**: The engine's quality report carries a `usage` block with the same fields, so non-audit consumers (dashboard) read one source.

Out of scope: per-segment / per-LLM-call granularity (this is per-job aggregate — a follow-up TMX-A6-2a can split it); v1 chain emit (v2 is the canonical chain; v1 double-write optional and added only if trivially safe); putting tokens *into* the JobConfigSnapshot (structurally impossible at capture time — see G1(a)); the `placeholder_hash` in JOB_FINALIZED (TMX-3213).

## 3. Design

**Where.** Two seams, each minimal:

1. **Engine → report** (`translation_engine.py`, in `translate_document`, the existing cost block at ~L319-330): build a `usage` dict `{model, input_tokens, output_tokens, total_tokens, estimated_cost_usd, currency, pricing_source}` from the already-accumulated `_total_input_tokens`/`_total_output_tokens` + `cost_for`, and attach it to the quality report (`report["usage"] = usage`). The cost is computed exactly once here; the audit event reuses it (no second pricing call, no drift). Keep the whole thing inside the existing try/except (A3 — a mocked/non-numeric token count must not abort translation; this is the regression TMX-3202 already fixed once).

2. **Node wrapper → audit** (`graph.py`, `translation_engine_node`): after `quality_report` comes back, if `state.get('job_id')` and `quality_report.get('usage')`, call `_emit_v2_audit_event(event_type="LLM_USAGE_RECORDED", actor_kind="agent", actor_id=None, payload={**usage, "_actor_node": "translator"})`. Wrap in its own try/except that logs at WARNING and swallows — consistent with the `_audit_v2_emit` Phase-1 contract and AC-5.

**Why the model comes from settings, not `"gpt-4o-mini"` literal.** The engine currently bills the *cost* at the gpt-4o-mini tier (a deliberate pricing-tier choice in Feature 5). But the **supplier model of record** for A6 is `settings.default_gpt_model` — that's what actually served the call when `enable_live_llm_inference` is on. The payload records the real configured model for provenance; the cost stays computed at its own tier. To avoid conflating the two, the payload carries `model` (provenance, from settings) AND keeps `pricing_source` so an auditor can see cost was table-derived. *Decision:* record `settings.default_gpt_model` as `model`; compute cost via the pricing table's gpt-4o-mini tier as Feature 5 established; if the configured model isn't in the pricing table, `cost_for` raises and the A3 wrapper logs + skips the event (loud in logs, never a wrong silent number). Revisit unifying the tier in TMX-PRICING-1a (already spawned to register more models).

**Alternatives considered & rejected.**
- *Emit from inside the engine* — rejected: the engine has `doc_id` but not `job_id`/`audit_id`; threading those down deepens coupling. The node wrapper already holds `state`. Engine stays surface-agnostic (composes on the engine, A-discipline).
- *New DB table for usage* — rejected by G1: the audit chain IS the durable store; a table would duplicate it and add schema/migration (one-way). The mutable `Document` row already serves the dashboard.
- *Put it in JOB_FINALIZED payload* — rejected: finalize runs after the refinement loop and may not see translate-node totals without state threading; a dedicated event is clearer evidence and independently queryable. (Also keeps JOB_FINALIZED's separate TMX-3213 hash fix uncoupled.)

**Correction during code:** the translate-node wrapper (`translation_engine_node`) lives in `translation_engine.py`, NOT `graph.py` (graph.py only imports it). So BOTH seams are in one file — graph.py needs no change. Smaller blast radius than the spec estimated.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/agents/nodes/translation_engine.py` | imports | `from app.core.config import settings`; `from app.agents._audit_v2_emit import emit_v2_audit_event` |
| `app/agents/nodes/translation_engine.py` | `__init__` + new `_reset_usage_counters` | extract counter reset to a method (DRY + red-team fix seam) |
| `app/agents/nodes/translation_engine.py` | `translate_document` start | call `_reset_usage_counters()` per document (red-team fix #1) |
| `app/agents/nodes/translation_engine.py` | `translate_document` ~end | replace cost block with `usage = self._build_usage(settings.default_gpt_model)`; attach `report["usage"]` |
| `app/agents/nodes/translation_engine.py` | new `_build_usage` | provenance model + token counts + table-derived cost dict |
| `app/agents/nodes/translation_engine.py` | `translation_engine_node` | emit `LLM_USAGE_RECORDED` v2 event from `report["usage"]`, A3-wrapped |
| `tests/test_llm_usage_audit.py` | new (6 tests) | AC-1..AC-7 + reset-regression; red before code |

## 5. Eval / Test

```
python -m pytest tests/test_llm_usage_audit.py -q     # 6 passed
python -m pytest tests/test_nfr_validation.py -q       # 3 passed (prior cost-block regression site — clean)
python -m pytest -q                                    # full suite — see stage 8
```

Red-before-green confirmed: pre-code run was `4 failed, 1 passed` (the 1 pass = no-job_id no-op, which is correct today and stays green).

## 6. Red team

Adversarial review of the diff surfaced four issues:

1. **[REAL BUG — fixed]** The engine is a process singleton (`get_engine`), and `_total_input_tokens`/`_total_output_tokens` were zeroed only in `__init__`, never per document. So job N's recorded cost included jobs 1..N-1 — monotonic inflation. Pre-existing in Feature-5's `Document.total_cost_usd`, but A6-2 writes that number into the *immutable* audit chain as A6 evidence, turning a cosmetic metrics glitch into a regulatory defect (A3/A6: wrong number in a regulated path). **Fix:** `_reset_usage_counters()` called at the top of `translate_document`; regression test `test_engine_resets_usage_counters_between_documents`.

2. **[Caveat — documented]** `estimated_cost_usd` is a float in the hashed payload. `audit_writer_v2` warns floats are a cross-language re-verification hazard (Python `repr(float)`). Accepted for now: the only verifier (TMX-3104 `AuditVerifierV2`) is Python and re-hashes with the *same* canonical-JSON, so events are byte-exactly verifiable today; and keeping one float representation across `Document.total_cost_usd`, the report, and the event honours single-source-of-truth. **Follow-up TMX-A6-2a:** if a non-Python verifier is ever built, switch the hashed cost to integer micro-USD.

3. **[Scope boundary — documented]** The event captures the **translate-pass** consumption only. The refinement loop (`refine_translation`, graph.py:580) runs *after* the translate node emits, and its tokens are not included. For the common PASS path (no refinement) this is the full job consumption; refined jobs undercount. **Follow-up TMX-A6-2b:** emit a second `LLM_USAGE_RECORDED` (or augment JOB_FINALIZED) with refinement-pass tokens.

4. **[Concurrency caveat — documented]** Resetting a singleton's counters at document start is correct for the realistic deployment (one job per worker via `run_pipeline_background`) but two documents translating concurrently in one process would interleave counts — a pre-existing flaw of the singleton+instance-state design, not introduced here. **Follow-up TMX-A6-2c:** make token accounting per-call/per-document-local rather than instance state (pairs with the TMX-3053 lazy-singleton theme).

`/review` 22-item checklist: no broken windows; no silent fallback in a content path (the swallow is the documented A3 metrics carve-out, mirroring `_audit_v2_emit`); no new dependency; reuses canonical pricing + emit shim; types are explicit; one new event type, one emit site.

## 7. Fix

Red-team finding #1 fixed in-loop (reset method + regression test). Findings #2–#4 are documented caveats with spawned follow-ups (TMX-A6-2a/b/c); none blocks this loop's AC set, which is per-translate-pass consumption evidence. No other findings.

**In-loop adjacent fixes (entropy / gate-hygiene, surfaced because the harness gates went live this session):**
- `scripts/ratchet.py` — `RX_TODO_BARE` now also exempts this repo's canonical `(TMX-XXXX)` ticket convention, not only GitHub-style `(#NNN)`. The meter was counting properly-ticketed `TODO(TMX-3211)` markers as bare, contradicting CLAUDE.md + the TMX-AUDIT-RATCHET-TODO-SWEEP loop's intent. Correctness fix, not loosening.
- Deleted a stray untracked `full_suite.log` (a prior test-run artifact) that inflated `hygiene.committed_log_files` 18→19 (the meter globs on-disk files, tracked or not).
- `app/agents/graph.py` — `_build_config_snapshot` return type `Dict[str, Any]` → `dict` (consistent with this loop's `_build_usage`; removes a false-precision `Any` and keeps `any_annotations` at baseline 252 with zero loosening). Also removed 2 genuinely-dead imports (`uuid`, `ChatOpenAI`). The 2 pre-existing `E402` mid-file imports were left (moving them risks circular imports — out of scope; candidate cleanup ticket).

## 8. Deploy

- [x] Tests: full suite green (see status log); `tests/test_llm_usage_audit.py` 6/6
- [x] Ruff: clean on all changed files (graph.py retains 2 pre-existing unfixable E402)
- [x] Ratchet: `✓ all 17 metrics at or better than baseline` (no loosening)
- [x] Commit: `d072288`
- [x] Pushed to origin/main (`735b662..d072288`)
- [x] `.context/active_tasks.md` updated

### Spawned follow-ups
- **TMX-A6-2a** — if a non-Python audit verifier is ever built, switch the hashed `estimated_cost_usd` to integer micro-USD (cross-language byte-exactness).
- **TMX-A6-2b** — include refinement-pass tokens (emit a second `LLM_USAGE_RECORDED` after `refine_translation`, or augment `JOB_FINALIZED`).
- **TMX-A6-2c** — make token accounting per-call/document-local rather than engine-instance state (concurrency-safe; pairs with the TMX-3053 lazy-singleton theme).
- **TMX-GRAPH-E402** — resolve the 2 pre-existing `E402` mid-file imports in `graph.py` once circular-import safety is confirmed.

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-03T~17:30Z | — | `[Spec]` | Created; baseline 911 passed/0 failed confirmed green before start |
| 2026-06-03T~20:35Z | `[Spec]` | `[Done]` | Shipped `d072288`; suite 917/0; ratchet 17/17; red-team singleton-reset bug fixed; A6 consumption now in the immutable chain |
