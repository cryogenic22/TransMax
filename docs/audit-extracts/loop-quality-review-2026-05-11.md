# Loop Quality + Anti-Bloat Audit — 2026-05-11

**Agent:** 1 of 4 (verify-audit, read-only)
**Window:** `97b91e3..b16ade7` on `origin/main`
**Range cmd:** `git log --oneline HEAD~35..HEAD` (34 commits)

---

## Headline

**GREEN.** The Sprint 2 chain (TMX-3003, 3050, 3060, 3045, 3053, 3052, 3012d, 3500, 3101, 3107) is uniformly disciplined: every substantive commit closes a named audit finding, ships a G2 reproduce-the-failure test, carries a self-review block, and respects A1-A10 (with addenda explicitly cited in commit bodies). Anti-bloat gate G1 is visibly enforced. Three minor YELLOW concerns flagged below; none block the audit.

## Methodology

- 34 commits surveyed (HEAD~35..HEAD); split roughly 10 substantive source commits + ~14 worksheet/active_tasks backfills + ~10 frontend-toast E2E commits.
- For each substantive commit: ran `git show --stat`, read the commit message self-review block, sampled the largest hunk for shape, checked file size against the 700-line guideline, and cross-referenced A1-A10 claims against the diff.
- Did NOT run pytest, ratchet, or vitest (read-only constraint; covered by agents 2 + 3).
- Time budget: ~25 min, within audit-cycle norms.

## Per-loop verdict table

| Ticket | Commits | 5-test verdict | A1-A10 flags | Anti-pattern | Overall |
|---|---|---|---|---|---|
| **TMX-3003** assert_production_safe | 97b91e3 | **Pass** (a,b,c,d,e all hit — "lying-backlog" fix; 14 regression tests) | A3 explicit (no silent prod fallback); A10 (truthful row) | None | GREEN |
| **TMX-3050** Tiptap XSS sanitiser | 05abca8, 0e44d0e | **Pass** (a XSS-exposed reviewer surface; b/c/d/e safer outcome + 15 vitest cases) | A1 PARTIAL (deferred to TMX-3050a until TMX-3101 lands — disclosed, not silent) | DOMPurify dep justified (24KB minified; stdlib won't do HTML allowlist) | GREEN |
| **TMX-3060** drift audit + push hygiene | 6dc7081, 9038414 | **Pass** (closes audit §6 / Risk D; 447-line CLI that detects worksheet⇄origin/main drift) | A10 reinforces | None | GREEN |
| **TMX-3045** kill rule auto-promote (C-13) | 7231c7d, 12c64aa | **Pass** (a,b,c,d,e all hit; 21 tests; C-13 Critical) | A1 (audit BEFORE row mutation); A3 (silent fallback removed); A4 (operational layer only); A6/A8 PARTIAL — explicitly spawned 3045b/3045d (disclosed) | None | GREEN |
| **TMX-3053** singleton race (C-08) | 3ee727e, ac13687 | **Pass** (double-checked locking; Barrier+sleep deterministic repro 5/5 RED → 50/50 GREEN) | A2 (gate behaviour preserved); A4 (no schema change) | quality_gate.py now 774 lines — see Concern Q1 | GREEN with note |
| **TMX-3052** circuit-breaker race (C-07) | fb3c8ee, d1bd97e, 1853cd5 | **Pass** (instance-based + Protocol-based state store; 5 callsites migrated; A3 fail-loud Redis stub) | A1 (CIRCUIT_BREAKER_TRIPPED audit-event gap → TMX-3052c spawned); A3 (Redis stub raises, not silent); A6 (qualified-supplier fault containment preserved) | None | GREEN |
| **TMX-3012d** DEFAULT_ORG_ID sweep close | d1b8ae3, 536ad54, 83dd5e5 | **Pass — Marginal** (cosmetic comments + 1 regression test that walks `app/` and forbids the literal outside 4 canonical files) | A3 (TenantContextMissing invariant unchanged) | Net-negative LoC; honest "cosmetic" framing | GREEN |
| **TMX-3500** Regulatory Pack scaffold | 99e2d81 | **Pass** (a — yes, pilot-SOW blocker; c — Trust pillar; e — DRY refactor of worksheet parser shared with drift audit; PDF/sign deferred to 3500a-e explicitly) | A8 (prompt-version inventory in PQ template); A10 (.context backlog as input) | stdlib `string.Template` chosen over Jinja2 — correct call | GREEN |
| **TMX-3101** Audit Ledger v2 writer | c531b5a, 7cbd2c4, 834c4ee | **Pass** (closes C-04; domain-separated hashing; spec-binding pinned-bytes test #10 makes any algorithm drift loud) | A1 (canonical chain); A3 (NaN/Infinity rejected, TenantContextMissing propagates); A4 (no v1 model changes); A6 (payload pins model+prompt version) | None — 15 tests, half of them boundary | GREEN |
| **TMX-3107** Daily Merkle anchor builder | 7149403, 8afedd2 | **Pass** (a,b,c,d,e all hit; RFC 6962 domain separation; pluggable AnchorObjectStore mirrors 3052 pattern; A3 empty-day honest NULL) | A1 (chain anchor); A3 (S3 stub fails loud); A4 (schema relax with idempotent migration); A9 (no DELETE FROM) | audit_anchor.py 570 lines — under 700, justified | GREEN |
| **TMX-3618** Playwright visual snapshot | e212408, b16ade7, e62b69c | **Pass — Marginal** (clock-frozen baseline; catches design-token slips like TMX-3601's :root vs .dark drift) | n/a | Real regression class (per-OS baseline noted) | GREEN |
| **TMX-3604 toast chain** (×6 commits) | e1c1f9a, 6d529fd, 944f8d7, fae481d, 1836924, c6f87a0, 9c3adca, c0d886d, 418cbc5, e2ac305 | **Pass** (a,b,e hit — A3 surfacing applied per slice; each commit ≤120 LoC + E2E coverage) | A3 (replaces blocking alert() / silent fail with user-visible error states) | Coordinated micro-ticket pattern; each carries its own worksheet — not bloat | GREEN |

## Concerns

### Q1 (YELLOW) — `app/services/quality_gate.py` size

After TMX-3053, the file is **774 lines** (`wc -l` on HEAD). CLAUDE.md guidance is "past 700 lines without justification". The 3053 increment was small (~85 lines of lock plumbing); the bulk pre-existed. Recommend filing **TMX-QG-MODULARISE** as a low-priority follow-up to split `_load_lang_pack` and `_populate_initial_state` into a sibling module. Not blocking. Reproduce: `wc -l app/services/quality_gate.py`.

### Q2 (YELLOW) — Test volume vs. code volume

- TMX-3107: `tests/test_audit_anchor.py` is **705 lines** for a **570-line** module (1.24× ratio).
- TMX-3101: `tests/test_audit_writer_v2.py` is **585 lines** for a **366-line** module (1.60× ratio).
- TMX-3045: `tests/test_rule_promotion.py` is **476 lines** for a **146-line** module (3.26× ratio).

This is **not** coverage-padding — each suite includes the spec-binding pinned-bytes test (Test #10 in 3101) plus boundary/concurrency cases the addenda demand. But the ratios are high enough to merit a glance from the modularity audit (Agent 2). The 3045 ratio in particular reflects "every state transition needs an audit-emit test" — defensible under A1, worth tracking.

### Q3 (YELLOW informational) — Operational layer growth

TMX-3045 adds 3 columns + 1 module on the `app/models/models.py` operational layer (correctly avoiding A4 deepening — explicitly called out in commit body). TMX-3107 relaxes 4 columns to `NULL` on `app/models/audit_v2.py` (regulatory layer). Both diffs respect the A4 invariant; no cross-layer query was introduced. Flagging only because the dual-model debt remains, awaiting TMX-3017.

### What I did NOT find (good news)

- No `DELETE FROM` in domain code (A9 holds across the window).
- No new `if domain == "X"` chains (config-not-branching).
- No hard-coded `model="gpt-4o"` snuck back in.
- No commits flipped `[Done]` without source-code change (Gate 3 holds — even TMX-3618 ships a real spec file).
- No tests-only ticket masquerading as a bug fix (Gate 2 holds).
- No silent fallback re-introductions in regulated paths (A3 holds — TMX-3045 explicitly forbids re-adding the auto-promote branch).
- No new top-level frontend routes outside `/workspace/*` (A7 holds).

## Recommendations

| Priority | Ticket to file | Rationale |
|---|---|---|
| Low | **TMX-QG-MODULARISE** | quality_gate.py crossing 700 lines; split lang-pack loader (Q1) |
| Low | **TMX-3107a/b/c/d** | already spawned by TMX-3107 (S3 wiring, signing, scheduler) — verify they land on the v3.0 board |
| Low | **TMX-3045a/b/c/d** | already spawned (backfill, A6 LLM provenance, curator UI, A8 prompt pinning) — verify board status |
| Watch | **A6/A8 partials** | TMX-3045 explicitly carries A6+A8 partials. Track that subsequent commits actually pin model_version / prompt_version per the spawned tickets, rather than letting partials calcify (entropy signal) |
| Watch | **Test-to-code ratio** | If next sprint's average exceeds 2.0×, examine whether parametrise/fixture refactor would compress without losing real regressions (Q2) |

## What worked well — patterns worth replicating

1. **Pluggable Protocol-based state stores** — TMX-3052's `CircuitBreakerStateStore` Protocol + InMemory default + Redis stub-raising-NotImplementedError pattern is reused verbatim by TMX-3107's `AnchorObjectStore`. Single source of truth for "how do we stage a backend without lying about its presence" (A3). Codify in a doc.

2. **Pinned-bytes spec test** — TMX-3101 test #10 (`canonical_json({"foo":"bar"})` → hard-coded hex digest) and TMX-3107's equivalent are exactly what a regulator's external verifier needs. Make this a template: any byte-exact spec ships with at least one pinned fixture.

3. **Backfill SHA commits + drift audit** — TMX-3060 closed the "lying backlog" failure mode by codifying push-before-Done. Every Sprint 2 ticket then shipped a small backfill commit (`backfill commit SHA X in worksheet + active_tasks`). This is exactly the entropy-fighting mechanic CLAUDE.md asks for.

4. **Spawn discipline** — every commit body lists spawned follow-ups by ticket ID (e.g. TMX-3052b/c/LAZY-SINGLETON-HELPER on 3052). A6/A8 partials are tracked, not hidden.

5. **Reproduce-the-failure (G2)** clearly enforced — TMX-3053's Barrier+sleep, TMX-3101's tampering test, TMX-3045's `assert 'ACTIVE' == 'PROPOSED'` repro all show the RED state captured before the fix.

6. **Self-review blocks** consistently filled — every substantive commit names Tier-0/1/2 considerations and A1-A10 by ID. Compliance with the pre-commit attestation hook is real, not theatrical.

**Verdict GREEN. Keep going.**

---

*Word count ~1380. Cap respected.*
