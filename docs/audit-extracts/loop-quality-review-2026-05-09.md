# Loop quality review — 2026-05-09

**Auditor**: Agent 1 of 4 (parallel verification audit)
**Window**: `HEAD~30..HEAD` on `main`
**Method**: Five-test rubric + A1–A10 + Tier-2 22-item against worksheets in `.context/loops/`

## Verdict

**PASS with minor follow-ups.** The loop board is doing what it's designed to do: every substantive commit has a worksheet, every quality-gate fix has a regression test, no `if domain == X` branching crept in, and the two A1-sensitive schema landings (TMX-3100 / TMX-3012) earned their migrations.

## Per-commit scorecard

| SHA | Subject | Verdict | Rationale |
|---|---|---|---|
| `4eb438d` | TMX-3411 freq-pattern sweep | pass | Data-only addition; line-count ratchet caught growth; extracted `quality_gate_frequencies.py` (120L) (A2). |
| `3dd5623` | TMX-3900 OTel tracing | pass | New `app/services/tracing.py` (180L) + 7 tests; deep module, no leakage into nodes. |
| `dc4795c` | TMX-3705 file-upload validation | pass | Magic-sniff + size cap + AV trigger; 189 test lines for 201 service lines. |
| `a67ad04` | TMX-3800 segmenter | pass | Replaces `text.split('.')` (review C-11); 195L module, 182L tests; abbrev registry not branching. |
| `b043075` | TMX-3700 DOCX ingestion v2 | pass | Tracked-changes via OOXML namespaces; 9 tests; backward-compatible. |
| `349838a` | TMX-3015 soft-delete | pass | A9 implemented as mixin + listener; 7 tests; explicit hard-delete refusal. |
| `9d3c4e7` | ci: init_db before pytest | pass | One-line CI fix for FK setup. |
| `97b2935` | test FK fix post-3011 | pass | Fixture repair, no prod code. |
| `d478641` | TMX-3410-fix digit boundary | pass | Regression test (`test_lang_packs_numeric_boundary_extra.py`, 119L) genuinely fails without the `(?<!\d)…(?!\d)` change. |
| `cbef01f` | TMX-3606 frontend de-tangle | pass | Removes nested-git-repo; bundle preserved in `parking_lot/`. |
| `1b0a2fe` | TMX-3614 FE test harness | pass | Vitest+Playwright wired with pinned warning baseline. |
| `724b276` | Loop 15 FE↔BE integ | pass | New CI job + 3 specs; mocked then real-backend split. |
| `7022f49` | TMX-3100 audit_events_v2 | pass (A1 critical) | Schema-only; 10 tests; CHECK length=32; SoftDeleteMixin **deliberately excluded** (worksheet §3 + regression test). |
| `44ec327` | docs: ADR-0002/3 | pass | Pure docs. |
| `c68a1b4` | TMX-3012 tenant session | pass | ContextVar primitive + auto-inject + auto-filter; 11 tests including soft-delete composition. AC-6/8 explicitly split to `TMX-3012b`. |
| `19e70b9` | docs status flip | pass | Pure docs. |
| `c9e0829` | TMX-3614-lint real-bug pass | pass | Cap 185→172; rules promoted. |
| `cdef0e2` | TMX-3601 design tokens | minor | Net-new; passes value/depth/trust on the design-system surface, but no automated regression test for the tokens themselves (visual-only). |
| `873007a` | TMX-3012b partial middleware | minor | Partial sweep — 44 `DEFAULT_ORG_ID` references still in 13 files. Worksheet acknowledges; no follow-up ticket text yet. |
| `59cba9d`–`f7371a4` (TMX-3602/3603 family) | UI patterns + agentic | pass | Each component carries a vitest spec; design-system page is the canonical home (A7). |
| `0f21dc3` | TMX-3617 middleware→proxy | pass | Next.js 16 deprecation rename; 7-line edit. |
| `e735a71`/`790b6b4`/`318211a` | TMX-3614 cleanup/types | pass | Lint cap walked down 172→84→33 with rule re-promotion. |

## Wins (≤200 words)

The loop discipline is paying off in three observable ways. **First**, every quality-gate fix carries a regression test that *demonstrably* fails without the fix: `tests/test_lang_packs_numeric_boundary_extra.py:119L` exercises CJK adjacency and `10mg` letter-glue, the two cases TMX-3410's original guards missed; `tests/test_quality_gate_frequency_cross_lang.py:188L` covers all 7 new languages. **Second**, ratchet caught its own scope creep mid-loop in TMX-3411 (quality_gate.py crossed 800 lines, forcing the `quality_gate_frequencies.py` extraction) — a textbook "anti-bloat gate fired correctly" moment. **Third**, the two A1-sensitive landings earned the right level of paranoia: TMX-3100 documents *why* `audit_events_v2` deliberately omits `SoftDeleteMixin` (auto-filter would be a tampering vector) and ships `test_audit_events_v2_does_not_inherit_soft_delete` as a regression guard; TMX-3012's auto-inject listener raises `TenantContextMissing` instead of defaulting to a system org (A3). The `(?<!\d)X(?!\d)` digit-only-boundary in `language_packs/base.py:30-47` is the single best refactor in the window — one regex replaces 8 near-duplicates and protects against the next class-of-defect at the base layer.

## Concerns (≤300 words)

1. **Partial sweeps tracked but not ticketed.** TMX-3012 explicitly splits AC-6/8 into "TMX-3012b" but only `873007a` has landed against that name (middleware + test fixtures). 44 `organization_id=DEFAULT_ORG_ID` literals remain in `app/services/{db_service,audit_service,learning_service,resilience}.py` and `app/api/{documents,auth,knowledge,v1/translations}.py`. The transitional markers were the explicit removal anchors; leaving them in violates A3 in spirit even if the listener no-ops correctly. **Follow-up: `TMX-3012c: complete service-layer DEFAULT_ORG_ID sweep`**.

2. **`app/services/quality_gate.py` is 717 lines and still the home of multiple gates.** TMX-3411 narrowly avoided a ratchet trip by extracting frequency data, but the gate logic itself remains a single mega-module. PRD §5 / A2 are well-served by gate plurality, not by one file. **Follow-up: `TMX-3412: split quality_gate.py into per-defect-class modules (numeric, frequency, unit, negation)`**.

3. **`Organization` model lives in `database.py` while `audit_events_v2` references it via `GUID` portable type — the dual-layer (A4) bridge works, but the schema asymmetry deepens** (the C-06 mega-migration still doesn't create 7 of the tables that `audit_events_v2.job_id` FKs into; the migration defensively skips). **Follow-up: `TMX-3017a: complete C-06 unwind for the 7 init_db-only tables before TMX-3017 rationalisation`**.

4. **TMX-3601 design tokens have no automated test.** Visual regressions of brand mark / theme are not caught by vitest. **Follow-up: `TMX-3618: add Playwright visual-snapshot test for /workspace/design-system page`**.

5. **No worksheet for `9d3c4e7` (ci init_db) or `97b2935` (FK test fix).** Both are sub-ticket fixes spawned by 3011's blast; per loop README, even a one-line typo should be recorded with `Stage 5: N/A`. **Follow-up: `TMX-LOOP-HYGIENE: backfill worksheets for 9d3c4e7 and 97b2935`**.

## Modularity drift check (≤200 words)

**No drift detected.** A `grep` for `if (lang|domain|language|country) (==|in)` across `app/services/` returns zero hits. The frequency-patterns dict, language-pack registry (`factory.py`), and abbreviation set in `segmenter.py:39-54` are all data-driven; new languages are dict additions. The base-class consolidation in `language_packs/base.py:_find_missing_numbers` (`base.py:16-48`) is the canonical example of the right move — eight near-duplicate `check_numbers` implementations collapsed into one helper with `accept_decimal_swap` / `digit_translate` config knobs.

The newest non-trivial module — `tenant_scoped.py:145L` — uses a `TenantScopedMixin` marker class plus two SQLAlchemy events; it deliberately avoids reusing `SoftDeleteMixin` as the marker (worksheet §3 explains: `audit_events_v2` is tenant-scoped but NOT soft-delete). That call is the right one — single-source-of-truth wins over false coupling.

The only modularity yellow flag is `quality_gate.py` at 717 lines (Concern #2) — but that's accumulation, not branching. The `quality_gate_frequencies.py` extraction in TMX-3411 sets the precedent for further per-defect-class splits without changing call shape.

---

**Total**: ~880 words. Generated 2026-05-09 by Agent 1 of 4. No code, worksheets, or backlog modified.
