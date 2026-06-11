# TMX-TOOLS-CONF-HONEST — No fabricated confidence verdict on a scoring outage

**State**: `[Done]`
**Owner**: Agent & AI + Quality
**Sprint**: 2 · **Started/Closed**: 2026-06-11
**Reversibility**: `two-way` — response-shape addition + honest defaults; revert by restoring the 90.0 default.
**Pre-mortem**: if this fails, a quality-scoring outage renders in the UI as a green "90% · Ready for Review" — a reviewer signs unverified output believing it scored well (the A3 worst case).
**Blast radius**: `app/api/tools.py::universal_translate` return dict; frontend TrustedTranslate page consumes it (TMX-UX-QDASH-REAL).

**Gates**: G1 PASS (no net-new module; honest defaults on an existing path; failing-first test). G2 PASS (test forces `ConfidenceService.calculate_score` to raise and pins the old fabricated 90.0 is gone). G3 PASS (a scoring outage now returns `confidence=null` + `scoring_available=false`, not a green verdict).

## 1. Task
`universal_translate` initialised `confidence_score = 90.0` / `score_band = "High"` and, on a scoring exception, returned those untouched (A3 fabrication). Make the outage honest.

## 2. Spec
- AC-1: on scoring failure → `scoring_available=false`, `confidence=null`, `score_band="Unavailable"`, `needs_review=true`.
- AC-2: a `review_note` explains scoring is unavailable + manual review required.
- AC-3: success path unchanged (real confidence/band still returned).

Out of scope: the frontend rendering of the unavailable state (TMX-UX-QDASH-REAL).

## 3. Design
Initialise the defaults to the honest "unavailable" state; the try-block flips `scoring_available=true` and sets real values only on success; the except sets the review note. Rejected: raising 500 on scoring failure (loses the still-useful translation; the translate succeeded — only scoring failed).

## 4. Code
| File | Change |
|---|---|
| `app/api/tools.py` | honest defaults + except note + `scoring_available` in response |

## 5. Eval / Test
`tests/test_tools_confidence_honesty.py::test_scoring_failure_returns_honest_unavailable` — 2/2 green. Full suite 1160 passed.

## 6. Red team
Other consumers of the endpoint? The e2e specs MOCK the response (don't hit the real endpoint). Frontend handles `confidence: number | null`. No backend consumer asserts a numeric confidence. Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [ ] Commit: <SHA> (batch B)
- [x] active_tasks updated

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done]` | code+test+suite green |
