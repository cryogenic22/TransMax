# TMX-BUDGET-1 — Per-job token/cost budget with cooperative fail-loud halt

**State**: `[Spec]`
**Owner**: Agent & AI
**Sprint**: 2
**Started**: 2026-06-03
**Closed**: —
**Reversibility**: `two-way` — opt-in, **default-off** (limits are `None` ⇒ guard disabled ⇒ zero behaviour change for every existing job). Revert by deleting `budget_guard.py` + the engine wiring + 2 settings. No schema, no migration.
**Pre-mortem**: if this fails in production, the failure mode is a job that *should* have been capped runs to completion (guard silently no-ops) — i.e. degrades to today's behaviour. The opposite failure (a wrongly-tripped budget) blocks segments LOUDLY with reason `budget_exceeded`, never silently mistranslates (A3).
**Blast radius**: `app/core/config.py` (+2 opt-in settings), `app/services/budget_guard.py` (new), `app/agents/nodes/translation_engine.py` (cooperative check in the batch loop + audit signal on the report), `app/agents/graph.py`-adjacent node emit. No frontend, no DB schema.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: an unbounded LLM job is an uncontrolled cost + an EU-AI-Act/Annex-11 operational-control gap; a hard per-job cap is real capability, not future-proofing. (b) 1 new module, 1 guard type, ~2 call sites. (c) negligible bundle. (d) reuses `cost_for` (TMX-PRICING-1) + the A6-2 usage accumulators + existing `SegmentState.BLOCKED`. (e) ships failing tests.
- [ ] **G2 Reproduce-the-failure** — N/A (greenfield guardrail); TDD: the "subsequent batches skip once budget tripped" + "BUDGET_EXCEEDED emitted" assertions are red before the code.
- [ ] **G3 Completion** — after stage 7: with a tiny budget set, an over-budget job leaves later segments `BLOCKED (budget_exceeded)` AND a `BUDGET_EXCEEDED` audit event in the chain; with no budget set, behaviour is byte-identical to today.

## 1. Task

Add an opt-in per-job token/cost budget to the translation engine. Once the accumulated qualified-supplier consumption (the A6-2 accumulators) crosses a configured limit, the engine stops spending: in-flight batches finish, but any batch that hasn't called the LLM yet is **skipped** (its segments marked `BLOCKED` with reason `budget_exceeded`), and a `BUDGET_EXCEEDED` audit event is recorded (A1). Default-off so no existing job changes. Addenda: **A3** (fail loud — block, never silently truncate/mistranslate), **A1** (audit the breach), **A6** (consumption is the trigger), config-not-branching (limits live in settings).

## 2. Spec — acceptance criteria

- [ ] **AC-1**: `JobBudget(max_tokens=None, max_cost_usd=None).is_enabled is False`; `is_exceeded(...)` always False when disabled.
- [ ] **AC-2**: With `max_tokens=1000`, `is_exceeded(tokens=1001, cost_usd=0)` is True; `is_exceeded(1000, 0)` is False (boundary: over, not at).
- [ ] **AC-3**: With `max_cost_usd=0.01`, `is_exceeded(tokens=0, cost_usd=0.0101)` is True. Either limit independently trips.
- [ ] **AC-4**: Engine `_maybe_trip_budget()` sets `self._budget_exceeded=True` once accumulated usage exceeds the budget; idempotent.
- [ ] **AC-5**: `_process_batch` entered while `self._budget_exceeded` is True does NOT call the LLM and marks every segment in the batch `BLOCKED` (skip = spend prevention).
- [ ] **AC-6**: When tripped, the engine surfaces `report["budget"] = {"exceeded": True, "limit_tokens":…, "limit_cost_usd":…, "tokens_used":…, "cost_used_usd":…}`; the node emits one `BUDGET_EXCEEDED` v2 audit event from it.
- [ ] **AC-7**: Default-off — with both limits `None`, `_maybe_trip_budget` never trips and no `budget` key / event is produced (regression-safe).

Out of scope: mid-batch (sub-LLM-call) cancellation; refund/partial-billing logic; surfacing budget in the dashboard UI (follow-up); per-tenant budget config (uses global settings for now).

## 3. Design

**Guard (`app/services/budget_guard.py`)** — pure, no I/O: a frozen `JobBudget` dataclass with `max_tokens: int | None`, `max_cost_usd: float | None`, `is_enabled` property, and `is_exceeded(tokens, cost_usd) -> bool` (strictly greater-than each non-None limit). Pure ⇒ trivially testable, no engine needed.

**Engine wiring** — cooperative, because all batches launch under one `asyncio.gather` (semaphore-capped); there is no wave barrier. So:
- `_reset_usage_counters()` also clears `self._budget_exceeded=False` (per-doc).
- `translate_document` reads `self._job_budget = JobBudget(settings.max_tokens_per_job, settings.max_cost_usd_per_job)` at start (config-not-branching; read per-doc for testability).
- `_call_llm`, right after the A6-2 token accumulation, calls `self._maybe_trip_budget()` → builds current usage via `cost_for` and sets the flag if `is_exceeded`. Monotonic set-once ⇒ benign races.
- `_process_batch`, at entry (before the attempt loop), if `self._budget_exceeded`: mark each unit `BLOCKED` + `error_message="budget_exceeded"`, update progress, `return` (no LLM call → caps spend to at most the already-in-flight wave).
- After batches, `translate_document` attaches `report["budget"]` iff tripped.
- Node (`translation_engine_node`) emits `BUDGET_EXCEEDED` v2 event from `report["budget"]`, same A3-wrapped pattern as `LLM_USAGE_RECORDED`.

**Alternatives rejected:** (a) raise `JobBudgetExceeded` mid-call and abort the whole job — rejected: loses already-completed segments + their audit; cooperative-skip preserves partial work and is gentler. (b) pre-flight estimate-and-reject — rejected: no reliable pre-run token estimate; the real signal is actual consumption. (c) enforce at `llm.py` gateway — rejected: the gateway has no per-job accumulator; the engine owns the job-scoped counters (A6-2).

## 4. Code

| File | Change |
|---|---|
| `app/services/budget_guard.py` | new — pure `JobBudget` (max_tokens/max_cost_usd, `is_enabled`, `is_exceeded` strict-greater-than) |
| `app/core/config.py` | +2 opt-in settings `max_tokens_per_job` / `max_cost_usd_per_job` (default None) |
| `app/agents/nodes/translation_engine.py` | `_job_budget` init + per-doc read; `_reset_usage_counters` clears `_budget_exceeded`; `_current_cost_usd`; `_maybe_trip_budget` (A3-wrapped); trip-check after token accrual in `_call_llm`; batch-entry skip in `_process_batch` (BLOCK + no LLM); `report["budget"]` when tripped |
| `app/agents/nodes/translation_engine_node.py` | **new** — extracted the LangGraph node adapter (`get_engine` + `translation_engine_node`) out of the engine file (engine first, surface second); node emits `LLM_USAGE_RECORDED` (A6-2) + `BUDGET_EXCEEDED` (this loop) |
| `app/agents/graph.py` | import `translation_engine_node` from the new module |
| `tests/test_job_budget.py` | new — 7 tests (AC-1..AC-7), red-before-green |

**Refactor note:** BUDGET-1's additions pushed `translation_engine.py` to 871 lines, tripping the `mega_files_800` ratchet. Rather than trim comments to dodge the threshold, I extracted the node adapter to its own module — the metric was correctly signalling a real single-responsibility split (engine class vs LangGraph surface adapter, per CLAUDE.md "engine first, surface second"). Engine file now 785 lines; ratchet green with **zero loosening**.

## 5. Eval / Test

```
python -m pytest tests/test_job_budget.py tests/test_llm_usage_audit.py -q   # 13 passed
python scripts/ratchet.py check                                              # 17/17 OK
python -m pytest -q                                                          # full suite — see stage 8
```
Red-before-green confirmed: pre-wiring run `4 failed, 3 passed` (the 3 pure-guard tests passed; the 4 engine/node-wiring tests were red).

## 6. Red team

1. **Default-off safety** — both limits `None` ⇒ `is_enabled` False ⇒ `_maybe_trip_budget` early-returns, no `budget` key, no event. Every existing job is byte-identical. AC-7 + full suite confirm.
2. **Mocked-LLM / non-numeric tokens** — `_maybe_trip_budget` and `_current_cost_usd` are inside try/except (A3 metrics carve-out); `int(MagicMock())` would be caught, leaving the budget untripped. No repeat of the TMX-3202 nfr_03 regression.
3. **Concurrency** — `_budget_exceeded` is a monotonic set-once bool; benign races. Worst case one extra in-flight wave completes before the flag is observed — overspend is capped to that wave, documented.
4. **Zero-token test LLM** — with `enable_live_llm_inference` off (tests), tokens stay 0, so budgets never trip in-process. The cooperative skip is therefore unit-tested directly (`_process_batch` with the flag pre-set) rather than via a live run. **Gap:** no end-to-end "real run trips mid-flight and skips" test because the fake LLM yields 0 tokens — see TMX-BUDGET-1b.
5. **float cost in hashed payload** — `cost_used_usd` float, same cross-language caveat as TMX-A6-2 (current Python verifier re-hashes identically). Consistent; TMX-A6-2a covers the int-micro-USD switch if needed.
6. **Downstream** — skipped segments are `BLOCKED` ⇒ report `REVIEW_REQUIRED` ⇒ doc `IN_REVIEW`. Loud, never silently finalized as TRANSLATED (A3).

## 7. Fix

No code changes needed from red team (default-off + A3-wrapping already cover the failure modes). Documented gaps spawned as follow-ups (below).

## 8. Deploy

- [x] Tests: full suite (see status log); budget 7/7 + A6-2 6/6
- [x] Ruff clean (graph.py retains 2 pre-existing E402 — TMX-GRAPH-E402)
- [x] Ratchet 17/17 (no loosening; node extraction kept mega_files green)
- [x] Commit: `0b8ca74`
- [x] Pushed to origin/main (`fbcebc7..0b8ca74`)
- [x] `.context/active_tasks.md` updated

### Spawned follow-ups
- **TMX-BUDGET-1a** — surface budget posture in the dashboard/Trust Center UI (remaining budget, breach badge).
- **TMX-BUDGET-1b** — end-to-end integration test with a token-emitting fake LLM that trips the budget mid-run and asserts the skip + `BUDGET_EXCEEDED` event.
- **TMX-BUDGET-1c** — per-tenant budget config (currently global settings); pairs with TenantContext.

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-03T~20:40Z | — | `[Spec]` | Created; baseline 917 passed/0 failed (post-A6-2) green |
| 2026-06-03T~20:55Z | `[Spec]` | `[Verify]` | Code + node extraction done; budget 7/7 + A6-2 6/6; ratchet 17/17; awaiting full suite |
| 2026-06-03T~21:05Z | `[Verify]` | `[Done]` | Shipped `0b8ca74`; full suite 924/0; ratchet 17/17 no loosening; node adapter extracted to its own module |

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-03T~20:40Z | — | `[Spec]` | Created; baseline 917 passed/0 failed (post-A6-2) green before start |
