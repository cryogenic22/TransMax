# Phase 1 Keystone — Build Plan (MQM annotation → engine → independent judge)

**Status:** v1.0 — accepted; K1–K3 built (2026-06-14). K4–K7 specified, gated on review condition 1.
**Companion:** `VISION-GAP-ANALYSIS-AND-ROADMAP.md` (the 12-area verified scorecard + Phase 0–5 roadmap).
**Decision of record:** `docs/decisions/0007-mqm-engine-and-epic-reconciliation.md`.

---

## 1. Why this is the keystone

The verified audit (A1, A2, A11) found that TransMax's quality story rests on three things that don't exist as specified: an MQM measurement instrument (Divergent — an ad-hoc `ConfidenceService`), an independent critique/judge with separation of authorship (Absent — the translator self-certifies; separation survives only by graph node-ordering), and a judge-reliability eval (Divergent — CI tests the gate, not a judge).

All three hinge on one shared object — a **span-level MQM annotation**. An independent **judge** emits it → a pure **MQM engine** scores it → the **risk-tier engine** decides how many judges → the **Black Book** semantic matchers run inside the judge → the **eval harness** measures the judge against it → the **reviewer cockpit** renders flagged-spans-first from it. Build the *annotation → engine → judge* triad first and five downstream areas unlock.

## 2. The architecture: producer / calculator / decider

```
TODAY:    translate ──(self-gates inline, emits status='PASSED')──▶ gates ──(overwrites quality_report)──▶ decide_next_step
                      └─ separation exists ONLY because gates runs after translate ─┘   ← fragile (A2/A3)

KEYSTONE: translate ──▶ [ deterministic annotators ]──┐
          (no status)   [ independent JUDGE node     ]──┴──▶ annotations[] ──▶ MQM ENGINE (pure) ──▶ verdict ──▶ decide_next_step
                          (emits annotations only)                              (the ONLY thing that
                                                                                 can set pass/fail)
```

Each role is **structurally incapable** of doing another's job: producers write to `annotations[]`, the engine alone writes the verdict, the translator emits no status key. This replaces separation-by-convention with separation-by-construction.

## 3. Reuse-and-reconcile mandate

This is a strangler-fig reconciliation, **not** a greenfield rebuild. Concretely:
- Severity + dimensions extend the existing `app/core/defect_taxonomy.py` (added a `NEUTRAL` tier, the seven `MqmDimension`s, the `SEVERITY_PENALTY_MULTIPLIER` ladder, and a `CATEGORY_TO_DIMENSION` bridge) — the deterministic gates are **not** re-authored; their violations convert to annotations via `MqmAnnotation.from_violation`.
- The metric-profile registry **copies** the proven `app/agents/prompts/registry.py` pattern (versioned YAML, semver `latest`, content-hash) so the codebase keeps one mental model — and it is the reconciliation home for the two disconnected profile systems (`regulatory_profiles.py`, `profile_resolver.py`).
- The MQM engine is the new single source of truth for scoring; `ConfidenceService` becomes an adapter **only after a shadow diff** (see condition 4) — the SDK scorer fork (`transmax_sdk/quality/scoring.py`) is unified in the same cutover loop (K5), not before.

## 4. Ticket ledger

| # | Ticket | Scope | Reversibility | Status |
|---|---|---|---|---|
| K1 | **TMX-MQM-1** | MQM annotation object (§5.7) + taxonomy reconciliation (NEUTRAL, 7 dimensions, SPM, category→dimension bridge) | `one-way` (schema) | **Done** |
| K2 | **TMX-MQM-2** | Content-type metric profile registry + 5 versioned profiles (ICF/SmPC-PIL/PV/PRO-COA/Promo) | `two-way` | **Done** |
| K3 | **TMX-MQM-3** | Pure MQM-2.0 engine (`score`/`score_from_violations`) + shadow harness; spec-binding tests | `one-way` (bytes) | **Done** |
| K4 | **TMX-MQM-4** | Independent judge node; wire the dead `reviewer` prompt → v2 with the §5.7 output schema | `two-way` (flagged) | **Gated on cond. 1** |
| K5 | **TMX-MQM-5** | Graph rewire (strip self-cert; gates→annotators; engine sole decider); `ConfidenceService`→adapter **after shadow diff**; unify SDK fork | `two-way` (flagged) | Spec |
| K6 | **TMX-MQM-6** | Bounded revise w/ conservation diff-reject + ensemble + disagreement escalation (Tier-0/1) | `two-way` | Spec |
| K7 | **TMX-MQM-CAPTURE** | Wire reviewer confirm/override → `MqmAnnotation.human_decision` so Phase 2 starts with gold, not cold (cond. 6) | `two-way` | Spec — Phase 1 |
| — | **TMX-MQM-1a** | Persist `mqm_annotations` table + Alembic revision (deferred from K1 — engine/judge need only the in-memory object) | `one-way` | Spec |

## 5. Review conditions — cleared / gated

The plan was reviewed against its own "no vacuous green" standard. Six conditions were raised; their disposition:

| # | Condition | Disposition |
|---|---|---|
| 1 | **Model-family independence rests on an infra assumption** in tension with the private/EU-resident, single-validated-model constraint. If only one in-boundary model exists, judge independence degrades to "different prompt/context" — materially weaker. | **GATES K4 — decision needed.** Do we have ≥2 sufficiently-independent in-boundary model families at acceptable cost/latency? If not, design compensating controls (stronger planted-defect gates, more aggressive disagreement escalation, cross-prompt adversarial judging) and state the weaker guarantee explicitly rather than letting the router flag imply independence we don't have. Tracked as the open decision in ADR-0007. |
| 2 | **Engine must not conflate "failed" with "insufficient sample"** — per §5.6 a short sample is a *route-to-human* signal, not a quality FAIL. | **Cleared in K3.** `passed` is the pure quality verdict (`CQS ≥ PT AND not critical_auto_fail`); `insufficient_sample` is a **separate** flag with a confidence interval; the routing layer owns the disposition. `_sqc_interval` is a named, documented heuristic explicitly flagged as the §8.3 open calibration item — not a hidden placeholder. |
| 3 | **`is_auto_fail` on the annotation is a second source of truth** for the one thing the design exists to protect. | **Cleared in K1/K3.** Auto-fail is **engine-derived** from `severity == CRITICAL AND profile.critical_auto_fail`; the engine ignores the annotation's `is_auto_fail`. The field is a non-authoritative denormalised convenience kept consistent with severity by `model_post_init` (a producer cannot make it lie). Pinned by `test_engine_ignores_annotation_is_auto_fail_flag` + `test_auto_fail_is_governed_by_profile_flag_not_annotation`. |
| 4 | **K3's scorer swap would change numbers for every legacy caller**, flag or not. | **Cleared in K3.** `ConfidenceService` is **untouched** this loop. K3 ships `shadow_compare_legacy(...)` which runs both scorers over identical inputs and returns a diff. The cutover (K5) happens only after the distributions are diffed and signed off — same shadow discipline the vision applies to profile changes (E4.S2), applied to the cutover that actually has blast radius. |
| 5 | **Tier-0 economics are multiplicative and unbudgeted** — ensemble (2–3 judges) × revise loop (2–3 iterations, re-judged) ≈ **6–9 judge calls per Tier-0 segment**, on the most expensive content, during a Day-215 sprint across 24 languages. | **Reckoned for K4/K6.** Worst case per Tier-0 segment ≈ `judges × (1 + max_revise_iterations)` model calls. Mitigations to design in: cap `max_revise_iterations` at 2 for Tier-0/1; reserve the ensemble for Tier-0 only (single strong judge for Tier-1/2 per §8 open decision 1); reuse the existing `app/services/budget_guard.py` per-job ceiling; deterministic-class fixes (standard phrases, units) go through deterministic reviser, never a judge round-trip (§8 open decision 2). The number is now a number in the plan, not an emergent surprise. |
| 6 | **Nothing in K1–K6 captured the human-override gold signal**, so Phase 2 (κ ≥ 0.80 calibration) would start cold. | **Added as K7 (TMX-MQM-CAPTURE), scheduled inside Phase 1.** The annotation already carries `human_decision`; K7 wires reviewer confirm/override into it (reconnecting the override→learning bridge the audit found reachable from no endpoint). Cheap now, expensive to backfill. |

## 6. What shipped in this increment (K1–K3)

Additive, behind no risk to the live pipeline (the graph still runs `ConfidenceService`):

| File | Change |
|---|---|
| `app/core/defect_taxonomy.py` | +`NEUTRAL` severity, `MqmDimension` (7), `SEVERITY_PENALTY_MULTIPLIER` (0/1/5/25), `CATEGORY_TO_DIMENSION` + `dimension_for_category()` |
| `app/core/mqm_annotation.py` | new — `Span`, `MqmAnnotation` (§5.7) + `from_defect`/`from_violation` reconciliation constructors |
| `app/core/metric_profiles/registry.py` + `__init__.py` | new — versioned profile registry (PromptRegistry pattern) |
| `app/core/metric_profiles/{icf,smpc_pil,pv,pro_coa,promo}/v1.0.0.yaml` | new — the 5 §5.4 profiles |
| `app/services/mqm_engine.py` | new — pure `score()`/`score_from_violations()` + `shadow_compare_legacy()` |
| `tests/test_mqm_{annotation,engine}.py`, `tests/test_metric_profiles.py` | new — 39 tests incl. spec-binding (RQS=99; SmPC/Promo CQS boundaries) + condition tests |

**Verification:** 39 new tests + 53 existing quality/profile/gate tests green; app boots; shadow helper agrees with the legacy scorer on a Critical numeric mismatch (legacy `BLOCKED` ↔ MQM `critical_auto_fail`).

## 7. Next

K4 is gated on **review condition 1** (model-family independence) — the one decision to resolve before pouring the judge. K5 (graph rewire + shadow cutover) is the loop to red-team hardest; it ships behind a per-tenant `mqm_engine_enabled` flag. K7 (override capture) can proceed in parallel.
