# TMX-MQM-4 — independent judge (in shadow)

**State**: `[Done, pending push]` · **Owner**: Agent & AI · **Sprint**: MQM Keystone (Phase 1)
**Reversibility**: `two-way` (default-OFF flag; emits to audit, changes no verdict). **Pre-mortem**: judge LLM mis-parse → fewer annotations (skipped, never guessed); cost = one extra call/job (flag-gated). **Blast radius**: new `mqm_judge.py` + `prompts/judge/v1.0.0.yaml`; `run_judge_shadow` in `mqm_shadow.py`; gate node awaits it (no-op when off).

**Gates**: G1 ✓ (the #1 defensibility component; reuses PromptRegistry + RobustParser + the engine; pure parser carries tests) · G2 N/A · G3 ✓ (judge emits §5.7 annotations + a judge-only MQM score to the audit chain; cannot set the verdict).

## 1–3. Task / Spec / Design
Build the independent assessor (§6.2): fed SOURCE+TARGET+grounding ONLY (never the translator's reasoning), emits span-level §5.7 annotations, cannot rewrite, cannot set pass status (the pure engine scores them). **Model-agnostic** per Kapil/ADR-0007: `get_llm(task="judge")` — router off ⇒ default model (single-model + compensating controls); flip to dual-model later with no code change. Runs **in shadow** (default-off `mqm_judge_shadow_enabled`) until the cutover. AC-1 parser maps dimension+severity, skips unknown (no guessing, A3); AC-2 judge never sets verdict; AC-3 separation-of-authorship contract (no reasoning passed); AC-4 fail-safe.

## 4. Code
`app/services/mqm_judge.py` (new: `parse_judge_response` pure + `judge_segments` async); `app/agents/prompts/judge/v1.0.0.yaml` (new, §5.7 schema — wires the previously-dead reviewer concept); `app/agents/nodes/mqm_shadow.py` (`run_judge_shadow` + emit `MQM_JUDGE_SHADOW`); `app/core/config.py` (`mqm_judge_shadow_enabled`); `app/agents/graph.py` (gate node awaits it).

## 5. Test
`pytest tests/test_mqm_judge.py -q` → parser maps/skips, garbage→[], mocked-LLM service parses, empty-when-untranslated. 96-test MQM+gate regression green.

## 6–7. Red team / Fix
Risk: prompt leaks translator reasoning → it's structurally not passed (only source+target+grounding). Risk: judge sets verdict → it returns annotations only; the engine decides. Risk: cost → default-off, per-tenant enable. No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | judge runs in shadow; cutover at MQM-5 phase-b |
