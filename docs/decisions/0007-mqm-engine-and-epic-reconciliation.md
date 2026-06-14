# ADR-0007: MQM quality engine (producer/calculator/decider) + vision-epic reconciliation

**Date:** 2026-06-14
**Status:** accepted

## Context

A 24-agent, evidence-grounded audit of the codebase against the four `docs/product_vision_features/` specs (`VISION-GAP-ANALYSIS-AND-ROADMAP.md`) found that TransMax's three defensibility pillars do not exist as specified:

- **A1 — MQM engine: Divergent.** No MQM-2.0 math anywhere; an ad-hoc additive `ConfidenceService` (`100 − penalties`, flat 15/5/100) scores absolute counts independent of document length, and is forked into a second drifting copy in `transmax_sdk/quality/scoring.py`.
- **A2 — independent critique/judge: Absent.** The `reviewer` prompt is authored but wired to nothing; the deterministic quality gate runs **inline inside the translator node**; separation of authorship survives only by LangGraph node-ordering (the gates node overwrites the translator's self-emitted `quality_report['status']='PASSED'`).
- **A11 — judge reliability eval: Divergent.** CI blocks on deterministic-gate correctness, never on judge↔human agreement or planted-defect recall.

Separately, two roadmaps shadow each other: `research/v3_pilot_ready_release_plan.md` defines 11 pilot-hardening epics (E1–E11), while the new vision specs define 14 product-defensibility epics (E1–E14) — colliding numbers, different meanings.

A keystone exists: a span-level MQM annotation is the shared object on which the judge, the engine, risk-tier routing, the Black Book, the eval harness, and the reviewer cockpit all depend. A review of the build plan against the platform's own "no vacuous green" standard raised six conditions (recorded in `PHASE-1-KEYSTONE-BUILD-PLAN.md` §5); conditions 2, 3 and 4 shape this decision and condition 1 is the open question below.

## Decision

**1. Epic reconciliation.** The new vision's **E1–E14 become the canonical product epic map.** The v3 "Pilot Ready" E1–E11 are reframed as *substrate / finishing work* (Phase 5 of the roadmap), not a parallel product plan. There is one epic numbering of record; the v3 plan's epic numbers are historical.

**2. MQM engine as producer/calculator/decider.** Quality is computed by a **pure, deterministic MQM-2.0 engine** (`app/services/mqm_engine.py`) that consumes span-level `MqmAnnotation`s (§5.7) + a versioned content-type metric profile and is the **sole authority on the pass/fail verdict**. Annotation *producers* (deterministic gates today; an independent judge in K4) only emit annotations; they cannot set pass status. This replaces separation-by-convention with separation-by-construction. Three properties are binding:
   - **Auto-fail is engine-derived** from `severity == CRITICAL AND profile.critical_auto_fail`; the annotation's `is_auto_fail` field is non-authoritative (cond. 3).
   - **The engine is pure to the quality verdict only.** Short-document uncertainty is a *separate* `insufficient_sample` flag owned by the routing layer, never folded into `passed` (cond. 2, §5.6).
   - **Cutover happens in shadow.** The engine ships additively; `ConfidenceService` and the SDK fork are reconciled only after a shadow distribution diff (`shadow_compare_legacy`), in the flagged graph-rewire loop (K5, cond. 4).

**3. Reconcile, don't fork.** The engine reuses `defect_taxonomy.py` (extended, not replaced), the metric-profile registry mirrors the existing `PromptRegistry`, and the two pre-existing profile systems (`regulatory_profiles.py`, `profile_resolver.py`) reconcile onto the metric-profile registry rather than spawning a third.

## Consequences

**Better:** one defensible, auditable quality instrument; separation of authorship becomes structural and survives refactors; the scorer fork and profile fork collapse to single sources of truth; every score is reproducible bit-for-bit and emittable to the v2 audit chain.

**Worse / cost:** Tier-0 economics are multiplicative — ensemble × revise loop ≈ 6–9 judge calls per Tier-0 segment (mitigated via `budget_guard`, capped iterations, single-judge for Tier-1/2; `PHASE-1-KEYSTONE-BUILD-PLAN.md` §5 cond. 5). The `ConfidenceService` cutover has real blast radius and must be shadow-diffed before flipping.

**Open decision (gates K4):** *Do we have ≥2 sufficiently-independent, in-boundary model families at acceptable cost and latency?* The private/EU-resident, validated-boundary posture (§1.4, §12) may mean a single validated in-boundary model, in which case judge "different-model" independence degrades to "different prompt and context" — a materially weaker guarantee that the entire defensibility story leans on. This must be answered before K4: either provision a second independent in-boundary model, or adopt compensating controls (stronger planted-defect gates, more aggressive disagreement escalation, cross-prompt adversarial judging) and state the weaker guarantee explicitly.

## Alternatives considered

- **Keep `ConfidenceService`, bolt MQM fields on top.** Rejected: perpetuates the additive-penalty model the vision explicitly replaces, and keeps the fork. The strangler-fig reconciliation removes the divergence as a byproduct.
- **Hard-cut `ConfidenceService` → engine adapter now.** Rejected: silently changes the score distribution for every legacy caller (cond. 4). Shadow-diff-then-cutover preserves the same discipline the vision demands for profile changes.
- **Fold `insufficient_sample` into a FAIL verdict.** Rejected: a short clause that scores 99 hasn't failed — it's "not yet trusted" (§5.6). Folding it leaks routing into scoring and undercuts the pure-calculator purpose.
- **Trust the annotation's `is_auto_fail`.** Rejected: reintroduces "marking your own homework" at the annotation level — the exact leak the keystone closes one layer up.

## Affected teams / surfaces

- **Quality & Regulatory / Agent & AI** (engine, judge, profiles): `app/core/defect_taxonomy.py`, `app/core/mqm_annotation.py`, `app/core/metric_profiles/`, `app/services/mqm_engine.py`, `app/services/confidence_service.py` (K5), `transmax_sdk/quality/scoring.py` (K5), `app/agents/graph.py` (K5), `app/agents/prompts/reviewer/` (K4).
- **Programme Lead:** the open model-family decision (gates K4) and the epic-reconciliation adoption.
