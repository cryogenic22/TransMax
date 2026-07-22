# TMX-DRIFT-IDLINT — Ticket-ID integrity lint in the drift auditor

**State**: `[Verify]` — on branch `loop/drift-idlint`; merge pending
**Owner**: Platform & Observability
**Sprint**: Board hygiene (scripts-only slice of TMX-BOARD-HYGIENE)
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — additive CLI flag on a read-only script; default behaviour (and the advisory pre-commit hook's semantics) byte-identical when the flag is absent.
**Pre-mortem**: if this fails in production, the failure mode is the lint mis-parsing the board (false duplicates / missed orphans) so the TMX-BOARD-HYGIENE sweep triages the wrong list — or worse, the default (flag-less) code path changing and the advisory hook starting to fail commits.
**Blast radius**: `scripts/audit_worksheet_drift.py` (extend, not fork), one new test file. No app/ code, no board edits, no worksheet edits other than this one.

**Loop-driven-dev gates** (per `~/.claude/skills/loop-driven-dev`):
- [x] **G1 Anti-bloat (between stage 2 and 3)** — net-new code path passes the 5-test rubric:
  (a) needed at all? Yes — the board has >=3 colliding IDs and ~95 prose-only IDs; the sweep (TMX-BOARD-HYGIENE) needs a mechanical detector, and the existing auditor is the SSOT for board/worksheet parsing. Extending it (not forking) is the anti-bloat move.
  (b) <5 callers? Yes — one CLI, invoked by humans/orchestrator with `--check-ids`.
  (c) bundle/binary impact <5%? Yes — ~130 lines in one existing script.
  (d) reuses existing patterns? Yes — same argparse/report/exit-code idiom, same `_worksheet_parser` primitives, same synthetic-fixture test pattern as TMX-3060 / TMX-CORRECTIVE-20260511.
  (e) ships with a test that fails without the change? Yes — 6 red tests (see stage 5).
- [x] **G2 Reproduce-the-failure (bug tickets only, before stage 4)** — the "failure" is the auditor's blindness: red tests invoke `--check-ids` against synthetic fixtures exercising each behaviour and fail on the unfixed script (argparse rejects the flag / qualifier headers land in IN-FLIGHT).
- [x] **G3 Completion (between stage 7 and 8)** — `--check-ids` on a synthetic duplicate board exits non-zero and lists the collision; orphans listed advisory; `[Done, pending push]` headers land in DONE_STALE_QUALIFIER; flag-less run byte-identical.

---

## 1. Task

The board (`.context/active_tasks.md`) has at least 3 duplicate/colliding ticket IDs (TMX-3618 names two unrelated tickets; TMX-3604-*/TMX-3705-* prefix collisions are annotated in-file) and ~95 ticket IDs that appear only in prose/Notes with no table row of their own. Separately, ~52 worksheet headers use `[Done, pending push]` / `[Done — X]` vocabulary that the parser cannot tokenise, so they land in the IN-FLIGHT "unparseable" noise where the sweep cannot find them. This loop extends the existing read-only auditor `scripts/audit_worksheet_drift.py` (SSOT — do not fork) with a `--check-ids` opt-in flag adding (1) duplicate board-row ID detection (fails), (2) orphan-ID listing (advisory), (3) a distinct `DONE_STALE_QUALIFIER` report bucket. Default behaviour, and therefore the `drift-audit-advisory` pre-commit hook which invokes the script flag-less, is unchanged this loop. Addenda at play: **A3** (report mechanical facts only — no guessed triage, no silent tolerance of unparseable state), **A10** (`.context/` is the program brain — this lint defends its integrity). Explicitly out of scope: editing `.context/active_tasks.md` or any existing worksheet (the orchestrator owns the sweep).

## 2. Spec — acceptance criteria

- [ ] AC-1 (duplicate detection): given a board where the same TMX-id is the first-cell ID of two different rows in ticket-introduction tables (header first cell `Ticket`), `--check-ids` lists the id with the 1-indexed line numbers of both rows and exits non-zero.
- [ ] AC-2 (recap rows are not introductions): an id with one introduction-table row plus one session-recap-table row (header first cell `Loop`) is NOT listed as a duplicate.
- [ ] AC-3 (orphan listing, advisory): a TMX-id that appears in prose or in another row's Notes cell but is the first-cell ID of no table row anywhere in the file is listed in an advisory orphan section; orphans alone never make the exit code non-zero.
- [ ] AC-4 (DONE_STALE_QUALIFIER): under `--check-ids`, a worksheet whose State header matches `[Done` + trailing qualifier + `]` (e.g. `[Done, pending push]`, `[Done — X]`) is classified `DONE_STALE_QUALIFIER` in the report table and counted in its own Summary bucket; it does not affect the exit code.
- [ ] AC-5 (default unchanged): without `--check-ids`, output contains no ID-integrity section and no `DONE_STALE_QUALIFIER` verdict; qualifier headers classify exactly as before (IN-FLIGHT/unparseable); exit-code semantics unchanged — the advisory hook is unaffected.
- [ ] AC-6 (fail loud): `--check-ids` with a missing `.context/active_tasks.md` exits 2 with an error, never silently passes (A3).

Out of scope for this ticket: editing the board or existing worksheets; changing the pre-commit hook; triaging the real duplicates/orphans (TMX-BOARD-HYGIENE proper); any worksheet-header rewrites.

## 3. Design

Extend `scripts/audit_worksheet_drift.py` in place (it is the SSOT for board/worksheet drift; `_worksheet_parser.py` stays untouched since the board-scan is a new concern local to the auditor). A pure function `scan_board_ids(text)` walks the file line-by-line tracking the current markdown table kind by its header's first cell (`Ticket` = introduction table; anything else, e.g. `Loop`, = recap). It returns (a) id -> line numbers of introduction rows, (b) the set of first-cell ids of ANY table row, (c) id -> first line number of every id occurrence anywhere. Duplicates = introduction ids with >=2 rows (mechanical fact; whether two rows are "the same ticket re-listed" or "two unrelated tickets" is the sweep's triage — the lint deliberately does not guess, per A3). Orphans = ids with zero table rows anywhere. `classify()` gains a default-False `tolerate_done_qualifiers` flag: in the existing unparseable-state fallback, a `\[Done\b[^\]]+\]` match yields the `DONE_STALE_QUALIFIER` verdict (with commit-resolution info in the summary, since the sha lookup already ran). Only duplicates join the failure count, and only under `--check-ids`.

Alternatives rejected: (1) a new standalone `scripts/audit_board_ids.py` — forks the auditor the ticket explicitly says to extend; two scripts would drift (SSOT). (2) Treating ANY table row (including `Loop` recap tables) as an introduction — flags every session-recap re-mention (TMX-MQM-5c etc.) as a duplicate, drowning the >=3 real collisions in ~15 false positives. (3) Making `DONE_STALE_QUALIFIER` and orphans fail the exit code — punishes the current board state before the sweep runs and would change the meaning of exit 1 for callers; the ticket scopes failure to duplicates only. (4) Normalising qualifier headers to `Done` terminal-state classification — that would CHANGE drift verdicts (a `[Done, pending push]` with no commit would become MISSING-COMMIT and start failing default runs via the tolerance flag leaking); a distinct advisory bucket is the surgical, behaviour-preserving read.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `scripts/audit_worksheet_drift.py` | 21-46, 52-56 | docstring: DONE_STALE_QUALIFIER verdict, ID-lint description, `--check-ids` usage line |
| `scripts/audit_worksheet_drift.py` | 82-131 | `TICKET_ID_RE`, `DONE_QUALIFIER_RE`, `_INTRO_HEADER_CELL`, `BoardIdScan` dataclass (`duplicate_ids` / `orphan_ids` properties), `_is_separator_cell` |
| `scripts/audit_worksheet_drift.py` | 134-181 | pure `scan_board_ids(text)` — table-kind tracking (`Ticket` header = introduction table; `Loop` etc. = rows-not-introductions), first-cell id extraction, occurrence map |
| `scripts/audit_worksheet_drift.py` | 281-345 | `classify(..., tolerate_done_qualifiers=False)` — DONE_STALE_QUALIFIER branch in the unparseable fallback, commit-resolution note; default False keeps flag-less output byte-identical |
| `scripts/audit_worksheet_drift.py` | 369-380, 388-400, 419-421, 445-447, 468-483, 486-510, 510, 536-541 | `--check-ids` argparse flag; board read (exit 2 if missing, A3); qualifier bucket count + Summary line; `## Ticket-ID integrity` report section; duplicates join `failure_count`; `DUPLICATE-ID DETECTED` epilogue |
| `tests/test_audit_worksheet_drift_idlint.py` | 1-328 | synthetic board+worksheet git-fixture repo (TMX-3060 / TMX-CORRECTIVE-20260511 pattern) + 7 tests (6 red pre-fix + 1 AC-5 guard) |

## 5. Eval / Test

RED (pre-fix) — new tests against the unmodified script (verbatim tail):

```
python -m pytest tests/test_audit_worksheet_drift_idlint.py -q
```

```
E       AssertionError: Expected explicit missing-board error on stderr; got:
E         stdout:
E         stderr: usage: audit_worksheet_drift.py [-h] [--root ROOT] [--remote-ref REMOTE_REF]
E                                         [--no-color]
E         audit_worksheet_drift.py: error: unrecognized arguments: --check-ids
=========================== short test summary info ===========================
FAILED tests/test_audit_worksheet_drift_idlint.py::test_check_ids_flags_duplicate_intro_rows
FAILED tests/test_audit_worksheet_drift_idlint.py::test_recap_table_row_is_not_a_duplicate
FAILED tests/test_audit_worksheet_drift_idlint.py::test_check_ids_lists_orphans_advisory
FAILED tests/test_audit_worksheet_drift_idlint.py::test_orphan_in_notes_cell_of_another_row
FAILED tests/test_audit_worksheet_drift_idlint.py::test_check_ids_done_qualifier_bucket
FAILED tests/test_audit_worksheet_drift_idlint.py::test_check_ids_missing_board_fails_loud
6 failed, 1 passed in 4.87s
```

(`test_default_run_has_no_id_section` passes pre-fix by construction — it is the AC-5 guard, not the red repro. The 6 failures are the G2 red evidence; each `--check-ids` invocation died in argparse with `unrecognized arguments: --check-ids`.)

GREEN (post-fix) — new tests + the nearest related suite:

```
python -m pytest tests/test_audit_worksheet_drift_idlint.py tests/test_audit_worktree_clean.py -q
```

```
............                                                             [100%]
12 passed in 33.14s
```

Default-behaviour byte-parity check (AC-5) — real repo, flag-less, HEAD's script (`git show HEAD:scripts/audit_worksheet_drift.py` + its `_worksheet_parser.py` copied to scratch) vs the modified script, identical `--root`:

```
python <scratch>/origdrift/audit_worksheet_drift.py --root <worktree> > pre.txt   # orig exit: 1
python scripts/audit_worksheet_drift.py            --root <worktree> > post.txt   # new exit: 1
diff pre.txt post.txt
```

```
BYTE-IDENTICAL flag-less output
```

(Both exit 1 from the repo's pre-existing drift; stdout byte-identical, so the advisory hook's flag-less semantics are unchanged.)

Real-board smoke under `--check-ids` (evidence the lint finds the known collisions; triage stays with the sweep) — verbatim excerpt of `python scripts/audit_worksheet_drift.py --check-ids` (exit 1):

```
## Ticket-ID integrity (--check-ids)
_board:_ `C:\Users\kapil\Documents\transmax-wt\drift-idlint\.context\active_tasks.md`

### Duplicate board-row IDs (2+ introduction rows -> FAIL)
- `TMX-3618`: lines 311, 367
- `TMX-AUDIT-RATCHET-TODO-SWEEP`: lines 269, 393
- `TMX-LANGDETECT-HOLD`: lines 22, 64
- `TMX-MQM-5`: lines 116, 117
- `TMX-SDK-FAILCLOSED`: lines 20, 63
- `TMX-V1-DURABLE-IR`: lines 21, 73

### Orphan IDs (prose/Notes mention, no table row) — advisory
96 orphan id(s):
- `TMX-3012b` (first mention: line 251)
- `TMX-3012e` (first mention: line 364)
[... 94 more advisory rows ...]
```

Summary also gains (under the flag only): `- DONE_STALE_QUALIFIER (Done-with-qualifier header — normalise to [Done]; advisory): 17`. The ticket's context claims verify mechanically: TMX-3618 caught at exactly lines 311/367 (two unrelated tickets), 96 orphan ids (~95 claimed), plus one collision the ticket did not list (`TMX-AUDIT-RATCHET-TODO-SWEEP`, lines 269/393). Lint/type gates on changed files: `ruff check` clean, `ruff format` applied, `mypy` — "Success: no issues found in 2 source files".

## 6. Red team

- **Does the flag-less path really stay byte-identical?** Verified mechanically (diff above): `tolerate_done_qualifiers` defaults False, the board is not even read without `--check-ids`, and `check_ids=False` short-circuits every new print/count. The hook entry (`python scripts/audit_worksheet_drift.py || true`) is untouched.
- **False duplicates from recap tables** — covered by AC-2 test; `Loop`-headed tables are recorded as rows (so their ids are not orphans) but not as introductions.
- **`[PARKED — ...]` and other non-Done unparseable headers** must NOT enter the new bucket: `DONE_QUALIFIER_RE` requires the literal `[Done` + word boundary; `[PARKED — needs schema migration]` stays IN-FLIGHT/unparseable. `\b` also rejects `[DoneX]` garbage.
- **`[Verify] -> [Done, pending push]` mixed lines**: `STATE_TOKEN_RE` finds `[Verify]`, so classification takes the existing non-terminal path before the fallback — pre-existing behaviour, unchanged; the bucket only claims headers with NO parseable token. Accepted residual: such mixed lines are rarer and already visible as STALE-STATE when a commit exists.
- **Duplicate list includes deliberate re-listings** (e.g. TMX-SDK-FAILCLOSED in the convergence table AND Batch A): intentional (design decision, A3) — the lint reports the mechanical fact "same id, two introduction rows"; distinguishing "re-listed" from "two unrelated tickets" (TMX-3618) requires human triage the ticket assigns to the orchestrator. Exit-non-zero under an OPT-IN flag is the specified contract.
- **Orphan noise** (e.g. brace-expansion prose `TMX-MQM-{A,B}` yields a bare `TMX-MQM` mention): advisory-only by AC-3, so noise cannot fail anything; the id regex requires the char after `TMX-` to be alphanumeric and ends on an alphanumeric, bounding the damage.
- **Windows/CRLF**: board read uses `errors="replace"` + splitlines(), same as the parser; line numbers are enumerate-based, CRLF-safe. Non-UTF8 console: report section is ASCII except ids.
- **If this is wrong in production**: worst case is a wrong advisory list under an opt-in flag on a read-only script — no app code, no board mutation, no hook change. Failure domain is bounded.

## 7. Fix

No blocking findings. Two hardenings applied during red team: (1) `DONE_QUALIFIER_RE` uses `\[Done\b[^\]]+\]` so `[DoneX]`/`[PARKED]` cannot enter the bucket (covered by `test_check_ids_done_qualifier_bucket`'s PARKED fixture asserting IN-FLIGHT); (2) missing-board under `--check-ids` exits 2 with an explicit error rather than printing an empty section (AC-6 test).

## 8. Deploy

- [ ] Commit: — single commit on branch `loop/drift-idlint`; merge pending. A one-commit loop cannot self-reference its own SHA without a fabricated claim (A3), so the SHA is recorded in the orchestrator's structured output and backfilled here at merge.
- [ ] CI green: n/a until merge
- [ ] `.context/active_tasks.md` updated — NOT this loop (orchestrator owns the board)
- [ ] Ratchet baseline updated — n/a (scripts/ + tests only)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:10Z | — | `[Spec]` | Created from _template.md; scripts-only slice of TMX-BOARD-HYGIENE |
| 2026-07-22T00:25Z | `[Spec]` | `[WIP]` | Red tests written + failing (6 failed, 1 passed pre-fix) |
| 2026-07-22T00:48Z | `[WIP]` | `[Verify]` | Green 12/12 (new + worktree-clean suite); byte-parity diff clean; on branch `loop/drift-idlint`; merge pending |
