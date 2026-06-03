# Loop spec-compliance audit — 2026-05-11 (Agent 4 / 4)

**Scope**: 10 Sprint-2 chain tickets explicitly enumerated + worksheet-modifying commits since 2026-05-09. The worksheet is the spec (stage 2 ACs); the commit content is the delivery.

## Headline

**GREEN.** 10/10 in-scope tickets verdict Match or Partial-explicit. Zero Drift. Zero Tests-only. Discipline holds or improves vs the 2026-05-09 baseline (18 Match, 1 Partial-explicit, 0 Drift, 0 Tests-only). Two ACs across the set ship Partial-explicit with named follow-up tickets (A1 audit-event hooks deferred to TMX-3050a and TMX-3500c, both pending the v2 audit ledger's frontend SDK / null-job-id path). No tests-only anti-pattern reappears. Sprint-2 chain ships the C-04 (audit-v2 writer), C-07 (circuit-breaker), C-08 (quality-gate singleton), C-13 (auto-promote learning rules) Critical/High audit findings as real source-code changes with G2/G3 verification.

## Per-ticket table

| Ticket | AC count | Met | Partial | Missing | Drift | Verdict |
|---|---|---|---|---|---|---|
| TMX-3003 | 9 | 9 | 0 | 0 | 0 | Match |
| TMX-3050 | 9 | 8 | 1 (A1 audit-hook → TMX-3050a) | 0 | 0 | Partial-explicit |
| TMX-3060 | 10 | 10 | 0 | 0 | 0 | Match |
| TMX-3045 | 11 | 11 | 0 | 0 | 0 | Match |
| TMX-3053 | 7 | 7 | 0 | 0 | 0 | Match |
| TMX-3052 | 10 | 10 | 0 | 0 | 0 | Match |
| TMX-3012d | 8 | 8 | 0 | 0 | 0 | Match |
| TMX-3500 | 12 | 11 | 1 (A1 audit-event → TMX-3500c) | 0 | 0 | Partial-explicit |
| TMX-3101 | 8 | 8 | 0 | 0 | 0 | Match |
| TMX-3107 | 11 | 11 | 0 | 0 | 0 | Match |

Verdict totals: **8 Match, 2 Partial-explicit, 0 Drift, 0 Tests-only.**

## Spot checks (high-load-bearing)

- **TMX-3003** — `97b91e3` touches `app/core/config.py` + new `tests/test_config_production_safety.py`. Grep confirms `assert_production_safe` (5 hits), `InsecureProductionConfigError` (4 hits), `app_env` field (line 41). Lying-backlog finding closed with the real function the active_tasks claimed had shipped. G2 reproduce-the-failure landed first.
- **TMX-3045** — `7231c7d` touches 9 files including `app/services/learning_service.py` (kills auto-promote), new `app/services/rule_promotion.py`, `app/auth/permissions.py` (RULE_APPROVE permission verified present), new migration `20260510_tmx_3045_rule_approval_fields.py`, `app/models/models.py` (3 approval columns verified), and 21-test regression file. `rule_promotion.py:117` confirms `log_event` ordering BEFORE the row mutation (A1-correct).
- **TMX-3052** — `fb3c8ee` covers all 11 changed files including instance refactor, Protocol + stub, all 5 callsites (`graph.py`, `learning_service.py`), and 6 test-file patches. One-way reversibility flagged correctly; class-level state genuinely deleted (verified in diff).
- **TMX-3500** — `99e2d81` ships all 5 templates (URS/FS/IQ/OQ/PQ verified on disk), `pack_builder.py`, `traceability.py`, shared `_worksheet_parser.py` (DRY refactor against `audit_worksheet_drift.py`), and 10-test suite. Pack builder produces 78-row matrix vs G3 floor of 30.
- **TMX-3101** — `c531b5a` ships writer + 15 tests including the byte-exact spec-binding test. Canonical algorithm pinned in module docstring AND worksheet stage 3 (load-bearing redundancy). v1 writer untouched per AC-8 (verified by file list).
- **TMX-3107** — `7149403` ships builder + Protocol + LocalFS impl + S3 stub + schema-relax migration. 18 tests (17 required + 1 bonus). Idempotency refusal, cross-org isolation, day-boundary, empty-day all verified by named tests.

## Concerns

**None of severity ≥ Drift or Tests-only.**

The two Partial-explicit verdicts (TMX-3050, TMX-3500) are both A1 audit-event hooks deferred to spawned tickets gated on TMX-3101 dependencies. TMX-3101 has now landed — so TMX-3050a (frontend audit-event-write SDK consumer) and TMX-3500c (REG_PACK_GENERATED via audit-v2) are unblocked. Recommend filing them on next sprint planning.

## Anti-patterns spotted

None of the worst-case anti-patterns appear. Spot-checked all 10 worksheets for the tests-only-pattern (CLAUDE.md G2/G3 violation). Every commit touches non-test source paths that address the user-visible failure mode. Even TMX-3012d (cosmetic close) touches three non-test files (`runner.py`, `auth/factory.py`, `api/auth.py`) in addition to the regression-test file.

Minor scope-drift observations (all benign):
- **TMX-3045** added a tightening in `app/api/knowledge.py:create_rule` / `:import_rules` to stamp `approved_by` on curator-authored direct creates. This is RED-TEAM Item-#7 surfaced in stage 6 and fixed in-loop. Not scope drift — it closes the same Pillar-1 invariant. Documented.
- **TMX-3052** drops 9 net-new `Any` annotations to keep the ratchet green (stage 7 fix). Discipline observation: ratchet acts as a quality lever even for typing hygiene.
- **TMX-3060** carried out 7 STALE-STATE worksheet header reconciliations in the same commit chain. The reconciliation is in-scope (the ticket's purpose was to detect AND fix worksheet drift), but it touches 9 other worksheets' headers. Cleanly scoped: each touched worksheet got a State-bump + commit-SHA backfill, no functional code change.

## Discipline observations

**Worksheets are aging WELL.** Stage 5 (Eval/Test) and Stage 6 (Red team) are NOT being rubber-stamped:

- Stage 5 captures explicit pre-fix RED output in TMX-3045, TMX-3050, TMX-3052, TMX-3053, TMX-3060, TMX-3101, TMX-3107, TMX-3500. G2 gate observed.
- Stage 6 carries real Tier-2 22-item walkthroughs in TMX-3050, TMX-3052, TMX-3107, TMX-3500. TMX-3107 stage 6 includes a thoughtful 5-item "Findings I deliberated" subsection with explicit accept/reject reasoning per finding (S3 retention sentinel, orphan-on-INSERT-failure, etc.).
- Stage 7 (Fix) is genuinely populated: TMX-3052 stage 7 fixes 9 net-new `Any` annotations the loop introduced; TMX-3107 stage 7 catches an unused `Any` import via ratchet; TMX-3101 stage 7 nudges typing. These are real-pass-through-the-checklist patches, not formal flourishes.
- Backfill discipline: every ticket has a follow-up commit (12c64aa, ac13687, d1bd97e+1853cd5, 7cbd2c4+834c4ee, 0e44d0e, 8afedd2) that backfills SHA + flips worksheet State to `[Done]`. The drift-audit script TMX-3060 introduced is being USED — TMX-3101 worksheet status log explicitly references the post-push drift-audit run.
- Reversibility tags are differentiated and load-bearing: TMX-3052, TMX-3045, TMX-3101, TMX-3107 are `one-way` with named Programme-Lead awareness; TMX-3003, TMX-3012d, TMX-3050, TMX-3053, TMX-3060, TMX-3500 are `two-way` with valid reasoning. Not rubber-stamped.

**Worksheet drift was caught and fixed in-loop.** TMX-3060 itself spotted that its OWN worksheet was STALE-STATE post-commit (9038414 self-bump). The discipline pattern is self-correcting now that the drift-audit script is operational.

**Cross-pod coordination is visible.** Worksheets reference upstream/downstream tickets explicitly (TMX-3050 spawns 3050a/b/c gated on TMX-3101; TMX-3101 spawns 3103/3104/3105/3109/3110/3101a; TMX-3500 spawns 3500a-e). The dependency chain is the spec.

## Recommendations

1. **File TMX-3050a and TMX-3500c.** Both were spawn'd from Partial-explicit gates; the blocking dependency (TMX-3101 v2 writer) is now on origin/main. Two new tickets, both small, owner Audit & Validation.
2. **Promote `_worksheet_parser.py` to canonical helper.** TMX-3500's DRY refactor extracted this from the drift script. Currently lives in `scripts/`. As more consumers emerge (TMX-3045's own follow-up tickets, future audit-extract tooling), consider promoting to `app/quality_gate/worksheet_parser.py` or similar shared location.
3. **Consider TMX-LAZY-SINGLETON-HELPER.** TMX-3052 and TMX-3053 now both implement the same `threading.Lock`-guarded double-checked module-cache pattern. The "rule of three" trigger is one copy away. The TMX-3052 worksheet explicitly tags this with a placeholder ticket id. Worth recognising on the backlog.
4. **Consider TMX-AUTH-ENDPOINT-ORDERING.** TMX-3107 stage 5 surfaced a pre-existing test-ordering issue in `tests/test_auth_endpoints.py::test_noauth_documents_endpoint_accessible`. Not caused by this loop, but loop runners should note it before the next full-suite green run.
5. **The drift-audit script is doing its job.** No action needed; recommend keeping the pre-commit advisory hook in `.pre-commit-config.yaml` and considering escalating to CI-gating (currently advisory) once 2-3 consecutive audits are green.

## Verdict vs 2026-05-09 baseline

| Verdict | 2026-05-09 | 2026-05-11 | Δ |
|---|---|---|---|
| Match | 18 | 8 | — (smaller scope this audit) |
| Partial-explicit | 1 | 2 | +1 |
| Drift | 0 | 0 | — |
| Tests-only | 0 | 0 | — |

The two Partial-explicit verdicts both name the spawn'd follow-up ticket explicitly — this is the GOOD partial (G3-aware deferral), not the BAD partial (silent miss). Discipline is holding.

**Bottom line: GREEN. Ship the next sprint.**
