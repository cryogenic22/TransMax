# TMX-QDASH-CONTRACT — Surface the engine's real score reasoning in the tools response

**State**: `[Done]`
**Owner**: Agent & AI · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way` — pure response-field addition.
**Pre-mortem**: if this fails, the UI has no real per-translation reasoning to show, so it keeps inventing dimension bars (the QDASH mock).
**Blast radius**: `app/api/tools.py` response; consumed by TMX-UX-QDASH-REAL.

**Gates**: G1 PASS (engine already computes `ScoreResult.breakdown_reasoning`; this only stops dropping it). G3 PASS (response now carries `breakdown_reasoning` + the real `score_breakdown` components).

## 1. Task
The engine's `ConfidenceService` returns `components` (base + penalties) and `breakdown_reasoning` (human-readable lines), but the tools endpoint surfaced only `components` and the UI ignored even that — fabricating accuracy/fluency/terminology instead. Surface the real reasoning so the UI can render truth.

## 2. Spec
- AC-1: success response includes `breakdown_reasoning: string[]` from `ScoreResult.breakdown_reasoning`.
- AC-2: `score_breakdown` carries the real penalty `components` dict.

## 3. Design
Engine-first, surface-second: the data already exists; expose it. `breakdown_reasoning = list(score_result.breakdown_reasoning)` on success; `[]` on outage.

## 4. Code
| File | Change |
|---|---|
| `app/api/tools.py` | add `breakdown_reasoning` to scope + response |

## 5. Eval / Test
`tests/test_tools_confidence_honesty.py::test_scoring_success_surfaces_real_breakdown_reasoning` — green.

## 6. Red team
`breakdown_reasoning` could be long; it is a handful of lines per translation, well under any size budget. Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: 4cda63e (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | bundled with TMX-TOOLS-CONF-HONEST |
