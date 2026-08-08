# TMX-TM-FUZZY-HONEST — stop fabricating the fuzzy-TM similarity score

**State**: `[Verify]` <!-- on branch loop/tm-fuzzy-honest; merge pending -->
**Owner**: Document Pipeline (loop agent, batch A3)
**Sprint**: seam-prep
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` <!-- internal service function; no schema, no public-API shape change -->
**Pre-mortem**: if this fails in production, the failure mode is a fuzzy TM match carrying a wrong (but now *plausible-looking*) similarity score into reviewer surfaces / the seam TM, misleading sign-off decisions.
**Blast radius**: `app/services/db_service.py:find_best_match` fuzzy branch only (dead in the live graph — the graph consults `find_exact_matches_batch`); tests. Future consumer: seam TM (ADR-0009).

**Loop-driven-dev gates** (per `~/.claude/skills/loop-driven-dev`):
- [x] **G1 Anti-bloat (between stage 2 and 3)** — net-new code path passes the 5-test rubric:
  (a) needed at all? Yes — replaces a fabricated constant with a derived value inside an EXISTING path; no new module.
  (b) <5 callers? Yes — `_fuzzy_score` / `_assemble_fuzzy_match` have exactly 1 production caller.
  (c) bundle impact <5%? Yes — ~20 lines.
  (d) reuses existing patterns? Yes — same result-dict shape as the exact branch; `SubstitutionType` enum.
  (e) ships with a test that fails without the change? Yes — red test below.
- [x] **G2 Reproduce-the-failure (bug tickets only, before stage 4)** — red test written and run BEFORE the fix; verbatim failing output in stage 5.
- [x] **G3 Completion (between stage 7 and 8)** — source changed (`db_service.py`), repro now passes; see stage 5 green run.

---

## 1. Task

`find_best_match`'s pgvector fuzzy branch (`app/services/db_service.py` ~294) returns a hardcoded `"score": 0.9` regardless of actual cosine distance — a shipped function inventing a regulatory-facing number. This is the house defect (A3: no unearned claims — a quality value must be derived from the artefact that produced it). The path is dead in the live graph today (the graph only consults exact matches), but the seam TM (ADR-0009) needs honest fuzzy scoring. Fix: select the cosine distance into the query result and compute `score = 1 - distance`, structured as pure module-level functions testable without Postgres/pgvector (SQLite CI cannot run `cosine_distance`).

Addenda at play: **A3** (no silent fallbacks / no fabricated values in regulated paths); A2 context (TM scoring is deterministic gate territory, not LLM territory).

## 2. Spec — acceptance criteria

- [x] AC-1: A module-level pure function `_fuzzy_score(distance: float) -> float` exists in `db_service.py`, returns `1.0 - distance`, and raises `ValueError` for a distance outside `[0.0, 2.0]` (geometrically impossible for cosine distance — crash early, never report a number for garbage).
- [x] AC-2: Row→result assembly is a pure function separate from the SQL, so it is unit-testable on SQLite CI with a stubbed row.
- [x] AC-3: The fuzzy branch's returned `score` is derived from the row's actual cosine distance selected by the query (`score == 1 - distance`), NOT the constant `0.9`. Red test: with a stubbed query row at distance `0.04`, the result score is `0.96` — this FAILS against the hardcoded value first.
- [x] AC-4: The fuzzy query itself now selects the distance (labeled column) and still orders by it ascending with the strict `< 0.1` threshold — behaviour of *which* row is chosen is unchanged.
- [x] AC-5: Existing `find_best_match` exact-path tests (`tests/test_tm_bypass.py`, `tests/test_data_ops.py`) still pass.

Out of scope for this ticket: wiring the fuzzy path into the live graph; changing the `0.1` distance threshold; the seam-TM integration itself (ADR-0009 follow-up); embedding-provider changes.

## 3. Design

Compute-real (per ticket + ADR-0009 preference), not delete-the-branch. Two module-level pure functions: `_fuzzy_score(distance)` (the distance→similarity mapping, `1 - d`, with range validation) and `_assemble_fuzzy_match(source_text, target_text, distance)` (row→result dict). The SQL changes from `query(TMSegment)...first()` to `query(TMSegment.source_text, TMSegment.target_text, dist_expr.label("distance"))...first()` so the distance the DB already computed for ordering is carried into the row instead of thrown away. The surrounding `except Exception` fail-soft stays: on any vector-search error the branch yields **no match** (falls through to LLM translate) — fail-soft to *nothing* is A3-safe; fail-soft to an invented number was the defect.

Alternatives rejected:
- **Delete the fuzzy branch** (ticket's alternative AC): ADR-0009's seam TM wants honest fuzzy scoring; deleting now means re-writing it in weeks. Compute-real is the same diff size.
- **Recompute similarity in Python from `match.embedding`**: needs the full 1536-dim vector pulled per row and duplicates math the DB already did; the labeled column is cheaper and single-source.
- **Clamp score into [0, 1]**: rejected — clamping manufactures a value the geometry didn't produce (A3). Out-of-range distance raises; negative similarity (distance > 1) is reported honestly, though the `< 0.1` threshold makes it unreachable today.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/db_service.py` | 17-45 | new module-level `_fuzzy_score` + `_assemble_fuzzy_match` pure functions (no DB needed) |
| `app/services/db_service.py` | 259-263 | `find_best_match` docstring: honest threshold claim (score > 0.9, not > 0.95) |
| `app/services/db_service.py` | 311-328 | fuzzy query selects `cosine_distance` as labeled column; result built via `_assemble_fuzzy_match`; hardcoded `0.9` removed |
| `tests/test_tm_fuzzy_score.py` | all | red-first unit tests: pure mapping (5) + stubbed-query fuzzy path (2) |

## 5. Eval / Test

### RED (pre-fix, verbatim)

```
python -m pytest tests/test_tm_fuzzy_score.py -q
```

```
E       AssertionError: score must derive from the row's cosine distance (expected 0.96), got 0.9
E
E         comparison failed
E         Obtained: 0.9
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_path_score_derives_from_row_distance
...
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_score_zero_distance_is_perfect
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_score_is_one_minus_distance
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_score_reports_negative_similarity_honestly
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_score_rejects_impossible_distances
FAILED tests/test_tm_fuzzy_score.py::test_assemble_fuzzy_match_shape_and_score
FAILED tests/test_tm_fuzzy_score.py::test_fuzzy_path_perfect_row_scores_one
7 failed in 1.32s
```

(The path test also showed `assert 0.9 == 1.0` on the perfect-row case — the fabricated constant both over- and under-reports.)

### GREEN (post-fix, verbatim)

```
python -m pytest tests/test_tm_fuzzy_score.py tests/test_tm_bypass.py tests/test_vectors.py tests/test_terminology_e2e.py -q
```

```
.........s.                                                              [100%]
10 passed, 1 skipped in 12.89s
```

(Skip = `test_vectors.py` real-pgvector integration, requires Postgres; correct on SQLite CI.)

**`tests/test_data_ops.py` caveat (pre-existing, NOT caused by this change):** `test_glossary_ops` / `test_tm_ops` fail identically with the fix stashed (verified: `git stash push app/services/db_service.py` → same 2 failures, `sqlalchemy.exc.OperationalError`). This is the known committed-`transmax.db` schema-staleness false-red documented in CLAUDE.md (TMX-3002 / TMX-AUDIT-DB-3002a). Not rebuilt/committed here per the Kapil-gate.

## 6. Red team

1. **CONFIRMED sibling defect (deferred, follow-up needed):** `get_constraints` (`db_service.py:196-200`) has the SAME fabricated `"score": 0.9` for `tm_matches`. Not fixed here because (a) it uses **l2_distance**, where `1 - distance` is the WRONG mapping (`cos_sim = 1 - l2²/2` on normalized vectors) — an honest fix needs its own design decision (switch to cosine vs. map l2); (b) the loop is dead-in-practice: `match.translated_text` doesn't exist on `TMSegment` (attr is `target_text`), so the first row raises `AttributeError`, swallowed by the surrounding `except` — `tm_matches` is always empty today, the fabricated score is unreachable. Proposed follow-up ticket: **TMX-TM-CONSTRAINTS-HONEST** (fix attr bug + honest scoring + red test).
2. **Swallowed ValueError:** an impossible distance (`<0` or `>2`) raises in `_fuzzy_score`, caught by the branch's `except Exception` → warning + no match. Verdict: A3-safe — fail-soft to *nothing* (segment routes to LLM translate); the defect was fail-soft to an *invented number*. No content is ever substituted.
3. **Score-range behaviour change:** consumers previously saw constant `0.9`; now (0.9, 1.0]. Grepped `app/` for consumers: `translation_engine.py:445` and `batch_translator.py:155` act ONLY on `TM_EXACT`; nothing reads a fuzzy score. Dead path confirmed — no production behaviour changes until the seam TM consumes it.
4. **`float(distance)` conversion** in `_assemble_fuzzy_match` handles Postgres returning `Decimal`/numpy scalar. Covered by design; row stub in tests uses plain float.
5. **Mock brittleness:** the path test pins the `query().filter().order_by().first()` chain shape. Acceptable — the real-DB integration path exists in `test_vectors.py` (runs on Postgres), and the pure functions carry the correctness burden.
6. **No clamping** — deliberate (stage 3): clamping would manufacture a value. Negative similarity is honest and unreachable under the `< 0.1` threshold anyway.
7. Ran the Tier-2 red-flag sweep on the diff: no new module, no new dependency, no `Any`, no bare except added, no print, enum used instead of the raw `"TM_FUZZY"` string literal (single source of truth). `ruff check` clean; `ruff format` clean on the new test file (base `db_service.py` was already whole-file format-dirty at 3f9f40d — left untouched for a surgical diff).

## 7. Fix

Applied from red-team: #1 recorded as follow-up (not silently fixed — it needs its own red test + mapping decision); docstring honesty fix (stage 4 row 2) closed the "Score > 0.95" false claim found while reviewing. Items 2-6: no code change needed — verified safe. Re-ran suite after fixes: green (stage 5).

## 8. Deploy

- [x] Commit: single commit on branch `loop/tm-fuzzy-honest` (SHA reported in the loop-agent structured return; single-commit discipline means the SHA cannot be written into its own commit — orchestrator records it here at merge)
- [ ] CI green: n/a yet (no push — merge pending by orchestrator)
- [ ] `.context/active_tasks.md` updated: n/a (orchestrator owns it)
- [x] Ratchet baseline updated: not applicable

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created from _template.md; stages 1-3 drafted |
| 2026-07-22T00:30Z | `[Spec]` | `[WIP]` | Red test written + run (7 failed, hardcoded 0.9 reproduced); fix applied; green 10 passed / 1 skipped |
| 2026-07-22T01:00Z | `[WIP]` | `[Verify]` | Red-team done (sibling `get_constraints` 0.9 deferred to TMX-TM-CONSTRAINTS-HONEST); on branch `loop/tm-fuzzy-honest`; merge pending |
