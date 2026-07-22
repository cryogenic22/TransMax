# TMX-WEBHOOK-FIRE — fire the accepted webhook or fail loud

**State**: `[Verify]` — on branch `loop/webhook-fire`; merge pending
**Owner**: Platform & Observability
**Sprint**: vision-delivery-2
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — additive behaviour on an existing (previously non-functional) request field; no schema migration, no public-API shape change. The new 422 on private webhook targets rejects values that were previously accepted-and-ignored, which is the A3-correct direction (loud beats silent) and is env-flag escapable.
**Pre-mortem**: if this fails in production, the failure mode is the dispatch task tying up a worker thread on a slow receiver (~10s timeout × 3 attempts + backoff ≈ 33s per job) or the SSRF guard 422-ing a legitimate integrator URL whose host merely *looks* private.
**Blast radius**: v1 job-creation path only (`app/api/v1/translations.py`, `app/schemas/api_v1.py`), one Settings flag, one new service module. Integrators supplying `webhook_url` (today: zero-functional field). No pipeline, model, or frontend surface touched.

**Loop-driven-dev gates** (per `~/.claude/skills/loop-driven-dev`):
- [x] **G1 Anti-bloat (between stage 2 and 3)** — net-new code path passes the 5-test rubric:
  (a) needed at all? YES — no outbound-callback path exists anywhere in `app/`; `webhook_url` is accepted and silently dropped (the exact A3 silent-failure class).
  (b) <5 callers? YES — 2 callers: the v1 router schedules `dispatch_job_webhook`; the schema validator imports `is_private_webhook_host` (single source of truth for the host predicate — no fork).
  (c) bundle/binary impact <5%? YES — one ~150-line module, zero new dependencies (httpx already in requirements).
  (d) reuses existing patterns? YES — `emit_v2_audit_event` shim, `org_context`, call-time `SessionLocal` resolution (same reason as `_audit_v2_emit._session_factory`), Starlette BackgroundTasks ordering.
  (e) ships with a red test? YES — 5 of 6 tests fail on the pre-fix tree (stage 5 evidence).
- [x] **G2 Reproduce-the-failure (before stage 4)** — red tests written and run BEFORE the fix; verbatim failing output in stage 5.
- [x] **G3 Completion (between stage 7 and 8)** — YES: the commit changes source (`translations.py` schedules dispatch; `webhook_dispatch.py` delivers; schema 422s private targets); a repro of the original failure (job created with `webhook_url` → silence) now produces an outbound POST with the terminal status, or a loud `WEBHOOK_DELIVERY_FAILED` audit event + WARNING. Proven by the red→green pair in stage 5, not tests-only.

---

## 1. Task

`JobCreateRequest.webhook_url` (`app/schemas/api_v1.py:57`) is the only occurrence of `webhook_url` in `app/` — the field is accepted, validated as an `HttpUrl`, and then never read again. An integrator who registers a callback gets neither a call nor an error: a silent failure in a regulated path (A3). Fix (preferred path per ticket): dispatch a terminal-status callback in the v1 background path — POST `{job_id, status, request_id, timestamp}` to `webhook_url` with a 10s timeout, 3 attempts, exponential backoff. A1 ordering: emit a v2 audit event (`WEBHOOK_DISPATCH_ATTEMPTED`) BEFORE the outbound side effect, `WEBHOOK_DELIVERED` on success, and `WEBHOOK_DELIVERY_FAILED` on exhaustion (`logger.warning`, never raise into the job path). SSRF guard at request validation: reject private/loopback/link-local hosts with a 422 unless `Settings.webhook_allow_private_targets` (default `False`) is set. Addenda at play: **A3** (no silent fallbacks — the theme), **A1** (audit before side effect), **A6** untouched (no LLM calls), **A5** (payload carries the stable `job_id`).

## 2. Spec — acceptance criteria

- [x] AC-1: `POST /api/v1/translations/` with a valid `webhook_url` fires exactly ONE outbound HTTP POST to that URL after the background pipeline reaches a terminal state; the JSON body carries `job_id` (the stable doc id), `status` (the ACTUAL terminal Document status read from the DB — never a substituted value), `request_id`, and a non-empty UTC ISO-8601 `timestamp`.
- [x] AC-2: A `WEBHOOK_DISPATCH_ATTEMPTED` v2 audit event is emitted BEFORE the first outbound attempt (A1), `WEBHOOK_DELIVERED` on success, `WEBHOOK_DELIVERY_FAILED` (with `attempts` and `last_error`) on exhaustion of 3 attempts. Success is asserted positively on the chain, not inferred from absence of failure.
- [x] AC-3: With `webhook_allow_private_targets=False` (default), a `webhook_url` targeting `localhost`/`127.*`/`10.*`/`172.16-31.*`/`192.168.*`/`169.254.*` (or IPv6 loopback/ULA/link-local) is rejected with a 422 whose detail names the webhook; public hosts pass; flag `True` bypasses (dev/test only).
- [x] AC-4: Delivery failure (5xx or connect error on all 3 attempts) never alters the job's terminal status and never raises out of the background path; it is loud — WARNING log + `WEBHOOK_DELIVERY_FAILED` audit event.
- [x] AC-5: Jobs without `webhook_url` schedule no dispatch task and emit no `WEBHOOK_*` events (behaviour unchanged).

Out of scope for this ticket: DNS-rebinding-resistant SSRF (resolving hostnames and pinning IPs), webhook signing/HMAC, retry-after-process-restart durability (a crash between pipeline and dispatch loses the callback — noted in stage 6), per-tenant webhook config, dispatch on the v2/regulatory job path.

## 3. Design

Add `app/services/webhook_dispatch.py` (G1-justified above) and schedule `dispatch_job_webhook` as a SECOND `BackgroundTasks` task immediately after `run_pipeline_background` — Starlette executes background tasks strictly in order, so the dispatcher observes the job's terminal state without touching the pipeline. The dispatcher re-reads the terminal status from the DB at call time (A3: report what IS, never what was expected), emits the A1 audit event via the existing `emit_v2_audit_event` shim inside `org_context(org_id)`, then POSTs via `httpx.Client` (`timeout=10s`, `follow_redirects=False` — a public receiver 30x-ing to an internal IP must not be followed) with 3 attempts and exponential backoff. The whole dispatch is wrapped in a documented failure containment (same posture as `_audit_v2_emit`): a flaky receiver must never corrupt an already-terminal job; every failure is surfaced via WARNING + audit event, never swallowed silently. The SSRF predicate `is_private_webhook_host` lives in the same module and is imported (lazily, to keep the schema layer import-light) by a `field_validator` on `JobCreateRequest.webhook_url` — one source of truth, no fork.

Alternatives rejected: (1) **dispatch inside `app/agents/runner.py`** — outside ticket scope, couples notification delivery into the pipeline module, and the runner is shared by callers (reprocess paths) that have no webhook concept; (2) **inline in `translations.py`** — ~120 lines of retry/backoff/SSRF/audit infrastructure inside a router mixes abstraction layers and pushes the file toward bloat; (3) **fallback AC (422 "not supported yet")** — unnecessary, dispatch is surgical; attempted first per ticket and it fits; (4) **async dispatcher with `httpx.AsyncClient`** — no benefit: BackgroundTasks runs sync tasks in a threadpool, and the sibling task (`run_pipeline_background`) is already sync; matching it keeps one execution model.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/config.py` | +9 | `webhook_allow_private_targets: bool = False` flag (SSRF guard escape hatch, dev/test only) |
| `app/schemas/api_v1.py` | +34/-2 | `field_validator("webhook_url")` — 422 on private/loopback/link-local host unless flag set |
| `app/api/v1/translations.py` | +45/-15 | schedule `dispatch_job_webhook` AFTER the pipeline task when `webhook_url` present; hoisted 4 pre-existing E402 mid-file imports to top (broken-window fix, no behaviour change) |
| `app/services/webhook_dispatch.py` | +245 (new) | dispatcher: DB status read → A1 audit → POST w/ retry/backoff → DELIVERED/FAILED audit; `is_private_webhook_host` predicate (single source of truth for schema + dispatcher) |
| `tests/test_webhook_fire.py` | +359 (new) | 6 tests / 29 cases: fire-on-terminal, SSRF 422 (parametrized), public-accepted, failure-containment, no-webhook-no-dispatch, predicate boundaries |

## 5. Eval / Test

### RED run (pre-fix, G2 evidence — 2026-07-22, tree at 3f9f40d + tests only)

```
python -m pytest tests/test_webhook_fire.py -q
```

```
28 failed, 1 passed in 13.05s
```

Key verbatim assertion failures (focused re-run of the three headline tests):

```
>       assert len(captured) == 1, (
E       assert 0 == 1
E        +  where 0 = len([])

>       assert resp.status_code == 422, (
E       AssertionError: private/loopback webhook target 'http://127.0.0.1/cb' must be rejected with 422 when webhook_allow_private_targets is off (SSRF guard); got 201: {"job_id":"de816406-dd1f-457b-8ea1-46117b656c89","status":"processing", ...}
E       assert 201 == 422

>       assert len(attempts) == 3, (
E       AssertionError: expected 3 delivery attempts (retry w/ backoff) against a failing receiver; got 0
E       assert 0 == 3
```

(The 1 pre-fix pass is `test_no_webhook_url_schedules_no_dispatch` — AC-5's
"behaviour unchanged without the field", correct on both trees by design.)

### GREEN run (post-fix)

```
python -m pytest tests/test_webhook_fire.py -q
```

```
29 passed in 18.77s
```

```
python -m pytest tests/test_webhook_fire.py tests/test_api_contract.py tests/test_api_contracts.py tests/test_tmx_3012c_request_autoinjection.py tests/test_tmx_3012c_runner_org_context.py -q
```

```
40 passed, 1 warning in 15.47s
```

Static gates on changed files: `ruff check` — All checks passed; `mypy` —
zero findings attributable to the changed files (the 76 reported errors are
pre-existing in transitively-imported modules: `app/models/auth.py`,
`app/auth/*`, unchanged here); `black --check app/` already fails on 109
PRISTINE files repo-wide (pre-existing CI debt, not widened — the new module
is black-clean). `python scripts/ratchet.py check` — "✓ Ratchet OK — all 17
metrics at or better than baseline" (an interim draft tripped the
`backend.type_ignore` ratchet with 2 `# type: ignore[attr-defined]`; fixed
properly by typing the fixture module as `types.ModuleType`, no baseline
change). `python quality-gate/quality_gate.py --staged` — PASSED.

Full-suite regression sweep, A/B against pristine `3f9f40d` (both runs:
`python -m pytest tests/ -q --ignore=tests/evals --ignore=tests/test_webhook_fire.py`,
pristine via `git stash`):

```
current tree : 33 failed, 1316 passed, 2 skipped, 4 warnings, 21 errors in 200.54s
pristine tree: 33 failed, 1316 passed, 2 skipped, 4 warnings, 21 errors in 193.57s
```

`diff` of the sorted FAILED/ERROR lists: byte-identical (only the timing line
differs). All 54 are the documented committed-`transmax.db` schema-staleness /
local-SQLite false-red family from CLAUDE.md known issues (e.g.
`test_auth_endpoints.py::test_noauth_documents_endpoint_accessible` →
`sqlite3.OperationalError: no such table: documents`), pre-existing and
NOT touched by this change. Zero regressions attributable to this diff;
CI (Postgres) is the authoritative green for those suites.

## 6. Red team

Adversarial pass over the diff (Tier-2 checklist + A1-A10 audit):

1. **DNS rebinding / resolved-private hosts (CONFIRMED gap, accepted out of scope).** The SSRF predicate is a literal check: `http://evil.example.com/` whose A record points at 10.0.0.5 passes validation and the dispatcher will connect to the private IP. Mitigations shipped: `follow_redirects=False` (a vetted public host cannot 30x us into the interior) and the guard still blocks every *literal* private target including 169.254.169.254 (cloud metadata). Full fix requires resolve-then-pin-IP at connect time (httpx custom transport) — filed as a stage-8 note for a follow-up ticket; documented in the predicate docstring so nobody mistakes it for covered.
2. **Worker-thread occupancy on a slow receiver.** Worst case ≈ 10s × 3 + 3s backoff ≈ 33s of a threadpool thread per job with a black-holing receiver. Bounded and after the pipeline (which takes far longer anyway); acceptable for pilot volume. Noted in pre-mortem.
3. **Crash between pipeline and dispatch loses the callback.** BackgroundTasks is process-local; a deploy/OOM after the pipeline task but before dispatch drops the webhook silently. Mitigating invariant: the audit chain then contains NO `WEBHOOK_DISPATCH_ATTEMPTED` event — the absence is detectable evidence, and the integrator can poll `GET /{job_id}`. Durable outbox = same follow-up as the stuck-job sweeper family; out of scope (ticket asks for dispatch in the v1 background path).
4. **A1 ordering verified.** `WEBHOOK_DISPATCH_ATTEMPTED` is emitted before `client.post` (webhook_dispatch.py `_dispatch`: audit emit precedes the retry loop). The emit shim's documented broad-except means an audit-write failure does NOT abort delivery — consistent with the shim's Phase-1 contract (gap is surfaced by the TMX-3104 verifier), and the delivery outcome is still separately audited.
5. **Does the 422 break an existing integrator?** The field was 100% non-functional (only occurrence in `app/`), so nobody can have a *working* private-target integration; anyone supplying one was ALREADY silently failed. Converting silence to a 422 with remediation text is the A3-correct direction. Flag `webhook_allow_private_targets` is the escape hatch for dev rigs.
6. **Idempotent replays do not re-fire.** The idempotency early-return path schedules no dispatch — a duplicate `request_id` cannot double-notify a receiver. Verified by code path (early `return` precedes scheduling).
7. **Payload honesty (A3).** `status` is re-read from the DB at dispatch time — if the pipeline crashed and left `error`/`processing`, THAT is what the receiver gets; a missing row aborts with `WEBHOOK_DELIVERY_FAILED(job_row_not_found)` rather than a fabricated status.
8. **`_read_terminal_status` resolves `SessionLocal` at call time** (module-alias attribute read), so the conftest in-place engine swap is honoured — same trap `_audit_v2_emit._session_factory` documents. A top-level `from ... import SessionLocal` would have bound the stale sessionmaker and made the tests vacuously green against the wrong DB.
9. **`v.host` empty-string edge**: pydantic guarantees a host for `HttpUrl`, but `is_private_webhook_host("")` → False → treated as public. With flag off, an (impossible) empty host would be allowed — harmless because httpx cannot connect to an empty host; no silent substitution occurs.
10. **E402 broken windows** in `translations.py` (4 pre-existing mid-file imports) fixed while touching the file — Tier 0, kept minimal (imports hoisted, no reformat of untouched code).

Edge cases consciously NOT covered by tests: IPv6-mapped IPv4 (`::ffff:10.0.0.1` — `ipaddress` classifies it private, covered by the predicate but not pinned in a param), receiver timeouts (`httpx.TimeoutException` is an `httpx.HTTPError` subclass → retry path exercised via 503 instead), multi-tenant org isolation of the audit events (single-tenant pilot; auto-inject mixin covers it).

## 7. Fix

No code findings requiring change — findings 1-3 are accepted-and-documented scope boundaries (each with a detection story), 4-10 verified correct. Follow-up candidates recorded in stage 8 notes: (a) resolve-and-pin SSRF hardening, (b) durable webhook outbox + replay.

## 8. Deploy

- [x] Commit: recorded in the status log below (single commit on `loop/webhook-fire`; NOT pushed — orchestrator merges)
- [ ] CI green: pending merge to `main` (branch worktree; CI runs on PR)
- [ ] `.context/active_tasks.md` updated: orchestrator-owned, not touched from this worktree
- [x] Ratchet baseline updated: not needed — `ratchet check` green with NO baseline change (an interim `type: ignore` regression was fixed at source instead of loosening)

Follow-up candidates for the orchestrator (from stage 6): (a) SSRF resolve-and-pin hardening (DNS-rebinding), (b) durable webhook outbox surviving process restart, with replay.

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created; stages 1-3 drafted |
| 2026-07-22T00:33Z | `[Spec]` | `[WIP]` | G2 red run captured: 28 failed, 1 passed (pre-fix tree) |
| 2026-07-22T01:20Z | `[WIP]` | `[Verify]` | Green: 29/29 + 40/40 target suites; full-sweep A/B vs pristine byte-identical failure sets (all pre-existing false-reds). One commit on `loop/webhook-fire`; merge pending. |
