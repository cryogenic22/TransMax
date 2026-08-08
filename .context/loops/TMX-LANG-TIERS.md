# TMX-LANG-TIERS — declared language support tiers, returned in provenance (seam invariant C-9)

**State**: `[Verify]`
**Owner**: Agent & AI
**Sprint**: —
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` — new pure module, no schema/API shape change; nothing consumes it yet
**Pre-mortem**: if this fails in production, the failure mode is a tier claim that looks derived
but is actually stale/wrong — e.g. a language demoted from a deep pack back to generic (a
refactor accident) still reporting QUALIFIED because something cached the old verdict. Mitigated
here by computing the tier fresh on every call, no caching layer introduced.
**Blast radius**: new file `app/core/language_tiers.py` (pure, no I/O side effects besides a
read-only filesystem check of `tests/evals/data/`) + `tests/test_language_tiers.py`. No existing
caller wired yet — `ProvenanceRecord.language_tier` still defaults to `None` in production; only
`resolve_language_tier()` now exists as a correct, tested primitive for `TMX-SEAM-WIRE` to call.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — net-new module justified: `language_tiers.py` is a distinct derived
  concept (pack-registry fact ⊗ eval-corpus fact -> tier) that doesn't belong inside
  `language_packs/factory.py` (registry has no business knowing about `tests/evals/`) nor inside
  `api_v1.py` (schema shouldn't do filesystem I/O). Ticket names several future callers
  (`TMX-SEAM-WIRE` wiring, any surface that reports provenance). Ships with 6 tests that fail
  without the change (see stage 5).
- [x] **G2 Reproduce-the-failure** — greenfield ticket (no bug), but treated the "field always
  None" gap as the failure to reproduce: red tests written first, module temporarily removed,
  `ImportError` captured (stage 5), module restored, tests turned green.
- [x] **G3 Completion** — `resolve_language_tier()` now returns a real, derived `LanguageTier` for
  any code; the AC below (five cases) all pass against real registry/eval-corpus state, not mocks.

---

## 1. Task

`ProvenanceRecord.language_tier` (`app/schemas/api_v1.py:350`) exists as `Optional[str] = None`
since `TMX-SEAM-CONTRACT` and has never been populated — C-9 in the seam conformance suite is
`PENDING` for exactly this reason (`.context/loops/TMX-SEAM-CONFORMANCE.md:100`,
`tests/seam/test_conformance.py::TestC9LanguageTierPending`). Without a real tier, a language
served only by `GenericLanguagePack` is indistinguishable in provenance from one with a deep pack
and measured recall — an unearned capability claim (A3 / ADR-0009 clause 5 — "provenance is
derived from the artefact that produced it... never stored as a string and never surviving a
fallback path").

This ticket builds the derivation function only: `app/core/language_tiers.py`, exposing
`LanguageTier` (str-Enum: QUALIFIED / SUPPORTED / AVAILABLE) and
`resolve_language_tier(lang_code, pair=None, *, eval_data_root=None) -> LanguageTier`, computed at
call time from two live facts — the `LanguagePackFactory` registry and the on-disk
`tests/evals/data/<source>_<target>/critical_safety.jsonl` corpus. Addenda in play: A3 (no
unearned claims), A8/A6 in spirit (the tier is itself a provenance-adjacent fact that must be
reproducible from source, not memorised).

## 2. Spec — acceptance criteria

- [x] AC-1: a language with a deep pack AND golden eval coverage resolves QUALIFIED
      (`en`->`es`: `SpanishPack` + `tests/evals/data/en_es/critical_safety.jsonl`, 10 real cases).
- [x] AC-2: a language with a deep pack and NO golden eval coverage resolves SUPPORTED
      (`en`->`fr`: `FrenchPack` exists, no `tests/evals/data/en_fr/` directory).
- [x] AC-3: a language with no registered pack resolves AVAILABLE (`sw` -> `GenericLanguagePack`
      via the BCP-47 fallback path).
- [x] AC-4: the result is provably derived, not table-looked-up — monkeypatching
      `LanguagePackFactory._packs` to add a fake deep pack for a previously-unregistered code
      flips AVAILABLE -> SUPPORTED; pointing `eval_data_root` at a fixture corpus flips
      SUPPORTED -> QUALIFIED for the same real language (`fr`).
- [x] AC-5: an unknown/garbage code (or empty/whitespace string) resolves AVAILABLE and never
      raises.

Out of scope for this ticket: wiring `resolve_language_tier()` into any code path that actually
populates `ProvenanceRecord.language_tier` on a live response. Grepped the repo — `ProvenanceRecord(...)`
is constructed nowhere in `app/` today (only in `tests/seam/test_conformance.py` and
`tests/test_seam_contract.py`, both asserting the `None` default under C-9-PENDING). There is no
one-line call site to touch; the field is populated by nothing yet, seam-wide. Wiring is
`TMX-SEAM-WIRE`'s job, per the ticket's own instruction to leave it there if it isn't a one-line
change in a place already being touched. This ticket also does not touch
`tests/seam/test_conformance.py`'s C-9-PENDING assertion — flipping that assertion to "wired" is
`TMX-SEAM-WIRE`'s to do once a real call site exists, otherwise the seam suite would claim C-9
COVERED while nothing in production populates the field (the exact unearned-claim pattern this
ticket exists to prevent).

## 3. Design

**Two facts, read live, never cached as a table:**

1. *Deep pack exists* — `LanguagePackFactory.get_pack(lang_code)`; the pack registry
   (`app/services/language_packs/factory.py:194-246`) is the existing single source of truth for
   "which languages have language-specific gates". `isinstance(pack, GenericLanguagePack)` is
   `False` for a deep pack, `True` for the universal fallback (including its BCP-47
   hierarchical-fallback terminal case, which already never raises for garbage input — confirmed
   by hand: `LanguagePackFactory.get_pack("zzzz")` returns `GenericLanguagePack()`).
2. *Golden eval coverage* — a filesystem check for a non-empty, parseable
   `tests/evals/data/<source>_<target>/critical_safety.jsonl`. Deliberately reads the filesystem
   directly rather than `tests/evals/runner.py`'s `SUITES` registry: `SUITES` currently lists only
   `en_es` even though `en_de` and `en_ja` both have real corpora and dedicated test files
   (`test_critical_safety_en_de.py`, `test_critical_safety_en_ja.py`) — `SUITES` is a
   hand-maintained CI-registration list, not the ground truth of "does a corpus exist", and
   depending on it would itself be a stored-fact shortcut of the kind this ticket forbids. An empty
   or unparseable file does not count as coverage (a present-but-empty file proves nothing was
   measured).

No values are memoised anywhere; both lookups re-run on every call. Considered a
`functools.lru_cache` for repeated hot-path calls, but rejected for now — the cost is a dict
lookup plus one `os.stat` plus (only on a pack hit) a bounded file read, cheap enough that a stale
cache's risk (a demoted pack or a deleted corpus silently continuing to report the old, better
tier) outweighs the saving. If a caller needs this on a genuine hot path, cache **the two input
facts** (registry snapshot, corpus directory listing) with an explicit invalidation story, not the
tier itself — noted here rather than built, since no such caller exists yet (G1).

**Alternative considered and rejected:** a `Dict[str, LanguageTier]` keyed by language code,
populated once from the same two facts at import time. Rejected per the ticket's explicit
instruction — this is the stored-string anti-pattern verbatim, and it would silently go stale the
moment a pack is added/removed or a corpus lands, without anyone touching this file.

**Signature:** `resolve_language_tier(lang_code, pair=None, *, eval_data_root=None)`. `pair`
matches the ticket's requested shape exactly (`Optional[Tuple[str, str]]`, defaulting to
`(DEFAULT_SOURCE_LANG="en", lang_code)` since every shipped corpus is English-sourced and
`ProvenanceRecord` only carries one language-facing tier field). `eval_data_root` is a
test-only injection point (keyword-only, defaults to the real `tests/evals/data`) — this is what
AC-4's second half monkeypatches instead of reaching for `unittest.mock.patch` on `Path` globally.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/language_tiers.py` | 1-131 | New module: `LanguageTier` str-Enum + `resolve_language_tier()`, `_has_deep_pack()`, `_has_golden_eval_coverage()` |
| `tests/test_language_tiers.py` | 1-96 | New test file: AC-1..AC-5 (6 tests — AC-4 is two tests, registry-monkeypatch + eval-corpus-fixture) |

No existing file edited — `ProvenanceRecord` wiring is explicitly out of scope (see stage 2).

## 5. Eval / Test

Red (module absent — temporarily moved `app/core/language_tiers.py` out of the tree, `tests/test_language_tiers.py` already written against it):

```
python -m pytest tests/test_language_tiers.py -q
```
```
=================================== ERRORS ====================================
________________ ERROR collecting tests/test_language_tiers.py ________________
ImportError while importing test module 'C:\Users\kapil\Documents\transmax-wt\lang-tiers\tests\test_language_tiers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python313\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\test_language_tiers.py:19: in <module>
    from app.core.language_tiers import LanguageTier, resolve_language_tier
E   ModuleNotFoundError: No module named 'app.core.language_tiers'
=========================== short test summary info ===========================
ERROR tests/test_language_tiers.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.34s
```

Module restored. First green pass surfaced one real bug in the AC-4 registry test itself: the
fake pack subclassed `GenericLanguagePack` (so `isinstance` still matched it as generic) — fixed
by subclassing `BaseLanguagePack` directly. Final green:

```
python -m pytest tests/test_language_tiers.py -q
```
```
......                                                                   [100%]
6 passed in 0.34s
```

Nearest related suites (seam conformance, seam contract, existing lang-pack tests):

```
python -m pytest tests/test_language_tiers.py tests/test_lang_packs_eu.py tests/test_new_languages.py tests/test_language_intelligence.py tests/seam/test_conformance.py tests/test_seam_contract.py -q
```
```
................................................................s..ss... [ 88%]
.........                                                                [100%]
78 passed, 3 skipped in 7.23s
```

Ratchet:

```
python scripts/ratchet.py check
```
```
✓ Ratchet OK — all 17 metrics at or better than baseline.
```

Ruff (new files): `All checks passed!`. Mypy on the new module surfaces zero errors of its own —
`mypy app/core/language_tiers.py` follows imports into the language-pack modules and reports 21
pre-existing errors there (missing `List[<type>]` annotations, `janome` stub gap), none in
`language_tiers.py` or attributable to this change; confirmed by inspecting the file list in the
output.

## 6. Red team

- Ran the Tier-2 checklist mentally against the diff: no `Any`, no bare `except` (both branches of
  `_has_golden_eval_coverage`'s try are typed `except (OSError, json.JSONDecodeError)`), no
  `print`, no silent default masquerading as a real value — `AVAILABLE` is the explicit "no claim
  earned" floor, never a stand-in for "measurement didn't run."
- **Considered:** does `_has_deep_pack` crash on a `None` lang_code? Guarded at the top of
  `resolve_language_tier` (`if not lang_code or not lang_code.strip()`) before it ever reaches the
  factory — confirmed by AC-5's empty/whitespace cases.
- **Considered:** does `LanguagePackFactory.get_pack` itself ever raise on garbage input? Checked
  by hand (`get_pack("zzzz")` → `GenericLanguagePack()`, no exception) and pinned by AC-5.
- **Considered:** is `fr` really uncovered, or did I get lucky? Asserted
  `not Path("tests/evals/data/en_fr").exists()` inside the SUPPORTED test itself, so if a future
  ticket adds `en_fr` coverage this test fails loudly (and correctly) instead of silently drifting
  to a wrong AC.
- **Considered:** case sensitivity — `resolve_language_tier("ES")` vs `"es"`? `_has_golden_eval_coverage`
  lowercases both `source_lang`/`target_lang` before building the path; `_has_deep_pack` delegates
  to `LanguagePackFactory.get_pack`, which already lowercases internally
  (`factory.py:254: code = lang_code.lower()`). Not added as a new AC since it's exercising
  existing, already-tested factory behaviour, not new logic in this module — noted here per red-
  team practice rather than padded into the suite as a redundant test.
- **Considered:** could `pair=(src, tgt)` be passed with `tgt` disagreeing with `lang_code`,
  producing a tier for a different pair than the pack lookup used? Yes, by design — `pair` names
  the (source, target) the *eval-coverage* check runs against, while `lang_code` is what the
  *pack* lookup runs against; a caller who wants a coherent single-language answer passes only
  `lang_code`, matching the ticket's `resolve_language_tier(lang_code, pair=None)` signature. Not
  a defect: the docstring states `pair` defaults to `(DEFAULT_SOURCE_LANG, lang_code)` and that a
  caller with a non-English source must pass an explicit pair.
- No findings requiring a code change.

## 7. Fix

No red-team findings requiring a fix. (The AC-4 test bug — fake pack subclassing
`GenericLanguagePack` — was caught and fixed during stage 5's first "green" run, before red team;
recorded there for the honest sequencing.)

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] CI green: not run (local-only; branch not pushed per instructions)
- [x] `.context/active_tasks.md` — NOT edited (orchestrator owns it, per instructions)
- [x] Ratchet baseline — unchanged; `ratchet check` passes against existing baseline, no update needed

State on close: `[Verify]` — on branch `loop/lang-tiers`, single commit, merge pending.

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created; worktree `C:/Users/kapil/Documents/transmax-wt/lang-tiers`, branch `loop/lang-tiers` |
| 2026-07-22T00:00Z | `[Spec]` | `[Verify]` | Module + tests implemented, red->green captured, ratchet clean; awaiting commit + cross-agent merge |
