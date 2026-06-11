# TMX-UX-QDASH-REAL — Kill the fabricated QualityDashboard dimension bars

**State**: `[Done]`
**Owner**: Reviewer Frontend · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way` — component prop refactor (one consumer).
**Pre-mortem**: if this fails, the TrustedTranslate result panel shows a confident "98% Accuracy / 95% Fluency / 100% Terminology" breakdown that NO measurement produced — a reviewer trusts fabricated trust signals (A3 worst case).
**Blast radius**: `frontend/components/ui/QualityDashboard.tsx` (sole consumer: `app/workspace/page.tsx`), `frontend/lib/api.ts` types.

**Gates**: G1 PASS (refactor of existing component; new test). G2 PASS (test asserts the fabricated labels Accuracy/Fluency/Terminology are gone). G3 PASS (UI now renders only real engine data + an honest "unavailable" state).

## 1. Task
`workspace/page.tsx` fed `QualityDashboard` `accuracy: confidence>90?98:85` etc. — fabricated from the confidence number. There is no accuracy/fluency/terminology measurement in the system; `score_breakdown` is penalty components and the engine also emits `breakdown_reasoning`. Render the real data; show an honest unavailable state when scoring didn't run (pairs with TMX-TOOLS-CONF-HONEST + TMX-QDASH-CONTRACT).

## 2. Spec
- AC-1: no "Accuracy"/"Fluency"/"Terminology" labels render anywhere.
- AC-2: expanded panel shows the real `base` + non-zero penalties + the engine `breakdown_reasoning` lines.
- AC-3: `scoringAvailable=false` / `confidence=null` → amber "Quality scoring unavailable — manual review required" + "N/A", never a number.

## 3. Design
Refactor `QualityDashboard` props from a fabricated `metrics` object to `{confidence: number|null, scoringAvailable, breakdown, breakdownReasoning, sourceText}`. Removed the dead `QualitySummaryPill` + `ScoreItem` + duplicate interface. Reused the existing honest `ConfidenceMeter` pattern (penalty rows). Kept the RAG header + PII/formula signals.

## 4. Code
| File | Change |
|---|---|
| `frontend/lib/api.ts` | typed `ToolUniversalResult` (scoring_available, confidence:null, breakdown, breakdown_reasoning) |
| `frontend/components/ui/QualityDashboard.tsx` | honest props + real breakdown + unavailable state; drop fabricated ScoreItem grid |
| `frontend/app/workspace/page.tsx` | map real fields; pass honest props |

## 5. Eval / Test
`frontend/__tests__/QualityDashboard.test.tsx` (3) — green. typecheck/lint/vitest(123)/build all green.

## 6. Red team
QualityDashboard had two duplicate `QualityDashboardProps` interfaces + a dead `QualitySummaryPill` (no importers) — removed. `theme` still derived for header. Build confirms no dangling imports. Clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: f4ad0b1 (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | fabricated dimension bars removed |
