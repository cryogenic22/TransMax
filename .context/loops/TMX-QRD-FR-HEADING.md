# TMX-QRD-FR-HEADING — fix English mandatory heading in the French SmPC profile

**State**: `[Verify]` — on branch `loop/qrd-fr-heading`; merge pending
**Owner**: Quality & Regulatory (loop agent, batch A3)
**Sprint**: convergence batch (post-ADR-0009)
**Started**: 2026-07-22
**Closed**: —
**Reversibility**: `two-way` <!-- registry data fix; no schema, no API shape -->
**Pre-mortem**: if this fails in production, the failure mode is the FR QRD header
check enforcing the WRONG heading text — either silently accepting an untranslated
English section 5 in a French SmPC, or (once the checker regex is accent-aware)
flagging a CORRECT French SmPC as non-standard. Both are regulated-path false
verdicts (A3).
**Blast radius**: `app/core/regulatory_profiles.py` (one literal in
`EMA_SMPC_FR_FR.mandatory_headings`); consumed only by
`QualityGateService.check_mandatory_headers` (quality_gate.py:751), which is dead
unless `enable_qrd_checks` is on (TMX-QRD-WIRE). No other consumer
(`grep mandatory_headings app/` → registry + quality_gate only). Pods: Quality &
Regulatory. Users: none until the flag flips — this ticket makes the flip safe.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — no net-new code path. One data literal corrected +
  tests. New test module `tests/test_qrd_fr_heading.py` follows the existing
  per-ticket pattern (`test_qrd_wire.py`); ships with tests that fail without
  the change.
- [x] **G2 Reproduce-the-failure** — red tests written and run BEFORE the fix
  (verbatim output in stage 5).
- [x] **G3 Completion** — source (`regulatory_profiles.py`) changed, not just
  tests; repro (English heading accepted / French list wrong) now resolves.
  Checked post-fix in stage 5.

---

## 1. Task

`EMA_SMPC_FR_FR.mandatory_headings` in `app/core/regulatory_profiles.py:40`
contains the English "5. PHARMACOLOGICAL PROPERTIES" among five correct French
headings — a copy-paste from the EN profile. Replace it with the official QRD
French heading "5. PROPRIÉTÉS PHARMACOLOGIQUES" (EMA QRD template, Annexe I —
Résumé des Caractéristiques du Produit), matching the sibling headings' accented
uppercase style. Addenda at play: **A3** (no unearned green on a regulated path —
the gate must not silently accept untranslated English, and must not flag correct
French), **A2** (the fix lives in the deterministic gate's registry, not in
prompts).

**How the list is actually consumed (read before fixing):**
`check_mandatory_headers(text, profile_id)` (quality_gate.py:751-779) is
*per-segment*: it first tests whether the segment "looks like a numbered header"
via `^\d+\.\s*[A-Z\s\(\)]+$` (ASCII-only uppercase), and if so flags
STRUCTURE_ERROR when the text is not a member of `mandatory_headings`. Two
consequences, verified by direct probe:
1. **Today's live defect**: English "5. PHARMACOLOGICAL PROPERTIES" in a French
   job matches the regex AND is in the FR list → **silently accepted**. An
   untranslated heading passes the QRD check — vacuous green, A3.
2. The ticket's stated false-positive ("correct French SmPC flagged") is
   currently *masked* by a second latent bug: the ASCII-only regex never
   recognises accented lines (DÉNOMINATION, DONNÉES, PROPRIÉTÉS) as headers, so
   they are skipped, not flagged. The moment that regex becomes accent-aware
   (it must, eventually), the English list entry would flag every correct
   French section 5. The registry fix is the root cause either way; the regex
   is a **separate finding**, out of this ticket's scope (see stage 6).

## 2. Spec — acceptance criteria

- [x] AC-1: `REGULATORY_PROFILES["EMA_SMPC_FR_FR"]["mandatory_headings"]` equals
  exactly the six official French QRD top-level headings, including
  "5. PROPRIÉTÉS PHARMACOLOGIQUES"; no English text remains.
- [x] AC-2: a synthetic French SmPC consisting of all six official French
  headings passes the mandatory-heading check for EMA_SMPC_FR_FR — every
  heading is recognised as mandatory (list membership) and none produces a
  STRUCTURE_ERROR through `check_mandatory_headers`.
- [x] AC-3: the English heading "5. PHARMACOLOGICAL PROPERTIES" submitted under
  EMA_SMPC_FR_FR now FIRES STRUCTURE_ERROR (untranslated heading no longer
  silently accepted).
- [x] AC-4: guard across ALL of `REGULATORY_PROFILES`: no non-EN-locale
  profile's mandatory heading contains the English marker words PROPERTIES /
  CLINICAL / PHARMACEUTICAL / PARTICULARS (word-boundary match, documented
  allowlist for legitimate collisions — currently empty).
- [x] AC-5: existing suites touching the registry stay green
  (`tests/test_profile_gates.py`, `tests/test_qrd_wire.py`).

Out of scope for this ticket: fixing the ASCII-only header-detection regex in
`check_mandatory_headers` (accent-blindness); doc-level completeness checking
(missing-section detection); other profiles' heading content beyond the AC-4
guard.

## 3. Design

One-literal data fix in the registry, guarded by behaviour tests through the
real checker plus a repo-wide anti-copy-paste guard. Alternatives considered:
(a) *also* fix the header regex to `[^\W\d_]`-style unicode uppercase — rejected:
ticket scope is explicitly one line in `regulatory_profiles.py`; the regex change
alters checker behaviour for every profile and deserves its own red-tested loop
(follow-up noted in stage 6). (b) derive FR headings from the EN list via a
translation map — rejected: single-source-of-truth applies to duplicated
*registries*, not to per-locale regulatory constants which are each authoritative
QRD text; a mapping layer is bloat (G1). (c) substring match for the AC-4 guard —
rejected in favour of word-boundary regex so Dutch/German cognates
(e.g. KLINISCHE) can never false-positive the guard.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/regulatory_profiles.py` | 40 | `"5. PHARMACOLOGICAL PROPERTIES"` → `"5. PROPRIÉTÉS PHARMACOLOGIQUES"` in EMA_SMPC_FR_FR |
| `tests/test_qrd_fr_heading.py` | new | red tests: FR SmPC passes; EN heading fires; repo-wide English-marker guard |

## 5. Eval / Test

### Red run (pre-fix) — verbatim

```
python -m pytest tests/test_qrd_fr_heading.py -q
```

```
E       AssertionError: Untranslated English heading was silently accepted by the EMA_SMPC_FR_FR mandatory-heading check
...
E       AssertionError: English marker words in non-EN profile mandatory headings (copy-paste from an EN profile?): [('EMA_SMPC_FR_FR', '5. PHARMACOLOGICAL PROPERTIES')]
E       assert not [('EMA_SMPC_FR_FR', '5. PHARMACOLOGICAL PROPERTIES')]

tests\test_qrd_fr_heading.py:100: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_qrd_fr_heading.py::test_french_smpc_with_all_official_headings_passes_mandatory_check
FAILED tests/test_qrd_fr_heading.py::test_untranslated_english_heading_fires_in_french_profile
FAILED tests/test_qrd_fr_heading.py::test_no_english_marker_words_in_non_english_profile_headings
3 failed in 1.50s
```

### Green run (post-fix) — verbatim

```
python -m pytest tests/test_qrd_fr_heading.py tests/test_profile_gates.py tests/test_qrd_wire.py -q
```

```
..............                                                           [100%]
14 passed in 1.33s
```

Nearest related suites (quality-gate consumers of the registry):

```
python -m pytest tests/test_regulatory_compliance.py tests/test_structure_gates.py tests/test_quality_gates.py tests/test_pharma_gates.py -q
```

```
......................                                                   [100%]
22 passed in 1.32s
```

Lint: `ruff check` on both touched files — "All checks passed!".
Encoding probe: `ascii(headings[4])` → `'5. PROPRI\xc9T\xc9S PHARMACOLOGIQUES'`
(true U+00C9, not mojibake).

## 6. Red team

1. **CONFIRMED, out of scope (follow-up)**: the header-detection regex in
   `check_mandatory_headers` (`^\d+\.\s*[A-Z\s\(\)]+$`, quality_gate.py:767) is
   ASCII-only — accented headings (DÉNOMINATION, DONNÉES, PROPRIÉTÉS) are never
   recognised as headers, so a *misspelled accented* French heading cannot be
   flagged, and doc-level "missing section" detection does not exist at all
   (the check is per-segment membership). The ticket's literal false-positive
   ("correct French SmPC flagged") is masked by this today and would only
   materialise once the regex becomes unicode-aware — at which point THIS fix
   is what prevents it. Traced by direct probe (stage 1). Suggested follow-up
   ticket: TMX-QRD-HEADER-UNICODE (unicode-aware header regex + doc-level
   completeness check, red-tested).
2. **CONFIRMED fixed**: pre-fix, "5. PHARMACOLOGICAL PROPERTIES" under
   EMA_SMPC_FR_FR was silently accepted (matches ASCII regex AND was in the
   list) — untranslated English passing a French QRD check is exactly the A3
   vacuous-green class. Now fires STRUCTURE_ERROR (AC-3 test).
3. **Checked, correct**: EMA_SMPC_EN_GB (line 24) and MHRA_SMPC_EN_GB (line 58)
   legitimately keep "5. PHARMACOLOGICAL PROPERTIES"; the AC-4 guard skips
   `en-*` locales by design. No other code consumer of the heading text exists
   (repo grep: registry + quality_gate only; frontend clean).
4. **Checked, correct**: encoding — the new literal round-trips as U+00C9
   through the import path; test-file and source-file literals compare equal
   under pytest on Windows (cp1252 console does not affect source parsing).
5. **Noted**: `ruff format --diff` would reformat the whole file (pre-existing
   trailing-comma/blank-line debt, untouched by this change). Left as-is for a
   surgical one-line diff; pre-commit hooks are not installed in this
   environment (shared hooks dir contains only `.sample` files), so no hook
   auto-reformats. `ruff check` passes on both files.
6. **Checked, pre-existing**: mypy reports 3 `[index]` errors in
   `resolve_profile` (lines 144-146, `object` not indexable) — verified
   identical on base commit `3f9f40d` (untyped `REGULATORY_PROFILES` value
   inference; untouched by this diff). Not introduced here; belongs to the
   registry-typing debt, out of scope.
7. **Guard robustness**: word-boundary match on the four marker words cannot
   false-positive on cognates (KLINISCHE / PHARMACEUTIQUE); a future profile
   missing the `locale` key fails the guard loudly (KeyError) rather than
   being skipped — fail-loud is the intended behaviour (A3).

## 7. Fix

No code changes required from red team — findings 1 and 5 are documented
follow-ups/deferrals, 2-4 and 6 verified correct. Clean.

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] CI green: n/a (branch commit; merge pending)
- [ ] `.context/active_tasks.md` updated: NO — orchestrator owns it
- [ ] Ratchet baseline updated: n/a

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-07-22T00:00Z | — | `[Spec]` | Created from _template.md; consumption path traced |
| 2026-07-22T00:30Z | `[Spec]` | `[WIP]` | Red tests written + run (3 failed, verbatim in stage 5); one-line fix applied |
| 2026-07-22T00:45Z | `[WIP]` | `[Verify]` | Green (14 + 22 passed); red team clean (2 documented follow-ups); on branch `loop/qrd-fr-heading`; merge pending |
