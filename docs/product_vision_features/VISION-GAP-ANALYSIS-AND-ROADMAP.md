# TransMax — Vision Gap Analysis and Disciplined Roadmap

**Status:** v1.0 · 2026-06-14 · Validated against codebase via 24-agent evidence-grounded audit.

This document reconciles the Agentic-LangOps product vision (see the four companion docs in this folder: the [Platform Vision / MQM + Critique design](LangOps-Platform-Vision-Backlog-and-MQM-Critique-Design.md), the [Black Book Capability Spec](Capability-Spec-Black-Book.md), the [Knowledge Architecture ADR](ADR-Knowledge-Architecture-Language-Layer.md), and the [strategy/compass artifact](compass_artifact_wf-3f2bf414-b94d-4452-b7b2-3ed38fb1c625_text_markdown.md)) against what the codebase actually defends today, and sets the build order that follows from the dependency structure.

---

## 1. Bottom line up front

TransMax has a genuinely strong **substrate** — a production-grade translation engine, a domain-separated tamper-evident v2 audit ledger with an independent re-compute verifier, a careful multi-tenant RBAC/auth foundation, a real abbreviation-aware segmenter, and structure-aware DOCX handling. But the **three pillars that make the product defensible rather than merely functional are Divergent or absent**: (1) the deterministic **MQM-2.0 quality engine** does not exist — what ships is an ad-hoc additive `100 − penalties` scorer, forked into two drifting copies; (2) the **independent critique-judge** does not exist — the translator self-certifies through inline deterministic gates while an authored reviewer prompt sits unwired; and (3) the **Black-Book negative-knowledge layer** is architecturally inverted into a positive find-and-replace rule store that the Knowledge ADR explicitly prohibits. Worse than absence, several surfaces **present governance they do not deliver** — the "vacuous green" risk: a `is_strict` flag that never blocks, regulatory profile checks that are dead code, a cosmetic "Reviewer agent" dashboard label, and a CI gate that blocks on deterministic-gate correctness while never measuring judge reliability. The work ahead is therefore mostly **reconcile-and-build on a real substrate**, not greenfield — but the honesty fixes must land first, because a regulator-facing green that cannot be falsified is the single highest-severity liability in the system.

---

## 2. The verified scorecard

Maturity values are the adversarially-corrected `corrected_maturity` from each area's verifier verdict — not the mapper's first pass. Across 12 areas the verifier's corrections ran **toward more honesty, never less** (e.g. A8 "Divergent" held but the resolver and DLQ were found *deader* than mapped; A7's date gate was found *weaker* than claimed).

| # | Capability area (vision epic) | Maturity | One-line truth |
|---|---|---|---|
| A1 | MQM Quality Engine (§5 / E4) | **Divergent** | No ETPT/APT/PWPT/NPT/RQS/CQS, no SPM ladder, no per-word EWC; a forked additive `100 − penalties` scorer occupies the slot. |
| A2 | Critique / QA Agent (§6 / E5) | **Divergent** | No independent judge; reviewer prompt authored but unwired; the translator self-gates inline; zero ensemble or conservation constraint. |
| A3 | Translation Agent(s) (E3) | **Partial** | Real RAG-grounded, gated, deterministically-scored engine; but no risk-tier router, no PI retrieval, separation held only by node-ordering. |
| A4 | Knowledge Layer: 5 stores + Black Book (E2/E14) | **Divergent** | "Black Book" is a positive rule store the ADR bans; `is_strict` never enforced; no precedence engine; only 2 of 5 stores real. |
| A5 | Document Model, Ingestion & Export (E1) | **Partial** | DOCX strong, PDF lossy-by-default; XLIFF/IDML/structure-tree absent; export maps by content+index, not stable segment_id. |
| A6 | Segmentation (E1.S2) | **Partial** | Solid abbreviation-aware segmenter; but no section path, content-type conflated with structural type, context window ephemeral. |
| A7 | Compliance / Regulatory checks (E6) | **Stub** | Profile checks are dead code (no caller passes `profile_id`); standard-phrase fidelity, MDR/IVDR, readability, claim-linkage all absent. |
| A8 | Risk-Tier Engine + Orchestration (E9) | **Divergent** | Tier is caller-supplied metadata that drives nothing; two tier vocabularies; LangGraph compiles with no checkpointer (orphaned jobs). |
| A9 | Audit / Traceability / Validation (E8) | **Partial** | v2 ledger + independent verifier are best-in-repo; but human decisions/retrievals not in v2, no change-control registry, anchor not running. |
| A10 | Reviewer Frontend / HITL UI + e-sig (E7) | **Partial** | Two divergent reviewer surfaces; no Part-11 e-signature anywhere; "Approve All" is a dead button; HITL→learning bridge unwired. |
| A11 | Eval Harness, Judge Reliability, Goldens (E13) | **Divergent** | Real CI-wired harness — but it measures *gate* correctness, not *judge* trust; no κ, no judge↔human agreement, no planted-defect recall. |
| A12 | Security / Residency / Private model + Auth + Integrations + Analytics (E10/E11/E12) | **Partial** | Auth/RBAC/tenancy real and honest; but hosted-OpenAI only (no EU-private model), access changes unaudited, dashboard reports activity not outcomes. |

**Tally:** Solid 0 · Partial 6 (A3, A5, A6, A9, A10, A12) · Divergent 5 (A1, A2, A4, A8, A11) · Stub 1 (A7) · Absent 0.

**Maturity legend:**
- **Solid** — implemented to vision intent; defensible as-is.
- **Partial** — a real implementation exists and delivers some of the vision; load-bearing gaps remain.
- **Divergent** — substantial machinery occupies the slot but is built *differently* from the vision; reconcile/refactor, not greenfield.
- **Stub** — a thin or wired-but-dead skeleton exists; the capability does not actually fire.
- **Absent** — nothing exists; greenfield.

The absence of any **Solid** area is the headline. Every defensibility pillar is Divergent; every supporting surface is Partial or worse.

---

## 3. Three cross-cutting truths

### 3.a The vacuous-green hazard (the highest-severity finding)

The vision's binding principle is *"No vacuous green: a passing score must be earnable, not gameable."* The codebase repeatedly **renders governance it does not enforce** — a regulator-facing green that cannot be falsified. Enumerated, with evidence:

- **No MQM engine** backs the score. The only scorer is additive `100 − (Defects+Drift+Structure+Process)` with flat 15/5/100 weights and no per-word normalisation (`app/services/confidence_service.py:18,68-69,132-133`); short docs always return a bare point score with no confidence interval or insufficient-sample flag (`confidence_service.py:152-158`).
- **No independent judge.** The reviewer prompt is authored and version-pinned but its own header says it is *"not currently wired to any call site"* and `PromptRegistry.load('reviewer')` appears nowhere (`app/agents/prompts/reviewer/v1.0.0.yaml:2`).
- **The translator self-certifies.** Quality gates run inline inside the producing node (`app/agents/nodes/translation_engine.py:541`), which emits `quality_report['status']='PASSED'` under the same key the router reads (`translation_engine.py:768`); separation survives only because a later node overwrites it (`app/agents/graph.py:398`) — fragile to any reorder.
- **Cosmetic "Reviewer agent" label.** The dashboard maps deterministic `GATE_*` audit events to `{id:'reviewer', name:'Reviewer agent', actor_type:'agent'}` (`app/api/dashboard.py:41-55`) — a presentation relabel that dresses a rules engine as an independent assessor in a regulator-facing view.
- **`is_strict` never enforced.** "Block if violated" is fully editable through the API (`app/models/models.py:38`, `app/api/knowledge.py:189`) but silently dropped at consumption (`app/services/db_service.py:137-143`) and never read by the gate — a curator's "strict" rule does nothing at runtime.
- **Dead regulatory profile checks.** `check_mandatory_headers` and `check_date_formatting` only run under `if profile_id:` (`app/services/quality_gate.py:229`), and no production caller passes `profile_id` (`graph.py:290`, `endpoints.py:165`, `translation_engine.py:541`) — only unit tests do. The header check is per-segment and cannot even detect a *missing* heading by construction.
- **CI blocks on gate-correctness, not judge-reliability.** `eval.yml` + `ci.yml` block release on a deterministic critical-defect miss (`.github/workflows/eval.yml:54`, `ci.yml:58`), never on judge↔human agreement or planted-defect recall — because that metric does not exist. A judge degrading to leniency or sycophancy would ship green.

### 3.b The single-source-of-truth / dual-vocabulary divergence

CLAUDE.md's own anti-fork law ("when two registries describe the same thing, pick one canonical") is violated in six places, each a reconcile-before-build hazard:

| Forked concept | Copy A | Copy B | Consequence |
|---|---|---|---|
| Quality scorer | `app/services/confidence_service.py` (has language calibration) | `transmax_sdk/quality/scoring.py` (does not) | Already drifting; an MQM rebuild would have to be done twice. |
| Tier vocabulary | `profile_enums` `TranslationArchetype × TIER_A/B/C` (caller-supplied) | `policy_definitions.RiskLevel` HIGH/MED/LOW (dead) | Neither is the vision's content-derived Tier 0–3; the live verdict path is tier-blind. |
| Profile system | `regulatory_profiles.py` (authority/locale/headings) | `profile_resolver.py` `JobProfile` (archetype/tier) | Two abstractions overlap; neither populates `check_segment`'s `profile_id`, orphaning the regulatory checks. |
| Reviewer surface | `/workspace/documents/[id]` (editable, legacy, partly-mock) | `/workspace/jobs/[id]` (canonical, read-only) | Review is split across two pages; the canonical one is the weaker. |
| Audit chain | v1 `AuditService` (weak string-concat, still primary) | v2 `AuditWriterV2` (domain-separated, catch-up shim) | Two chains describe the same events; the weak one is the only sink for human decisions. |
| TM table | `TMSegment` (`models.py:260`, operational) | `TranslationMemory` (`translation.py:189`, regulatory) | The A4 dual-model divergence; two parallel TM schemas for one concept. |

### 3.c The keystone

Every defensibility pillar converges on one object: the **span-level MQM annotation** — `{segment_id, dimension, subtype, severity, rule_ref, evidence_refs, suggested_fix}` per §5.7/§6.7. It is the shared currency on which six capabilities depend:

```
                       ┌───────────────────────────────┐
                       │  SPAN-LEVEL MQM ANNOTATION      │
                       │  (the keystone object, §5.7)    │
                       └───────────────┬─────────────────┘
        ┌──────────────┬───────────────┼───────────────┬──────────────┐
        ▼              ▼               ▼               ▼              ▼
   JUDGE (A2)     MQM ENGINE (A1)  TIER ROUTING (A8)  BLACK BOOK (A4)  EVAL (A11)
   emits it       scores over it   routes on it       cites entry_id   κ / recall over it
                                                                        │
                                                                        ▼
                                                                  COCKPIT (A10)
                                                                  adjudicates it
```

Today defects carry only `{category, severity, message, segment_id}` (`app/services/quality_gate.py:244`) — no dimension, no `rule_ref`, no `evidence_refs`, no machine `suggested_fix`. Until the keystone exists, the judge has nothing structured to emit, the engine has nothing to score, the tier engine has nothing to route on, the Black Book has nothing to cite, the eval harness has nothing to measure κ over, and the cockpit has nothing to adjudicate. **Phase 1 builds the keystone first for this reason.**

---

## 4. Per-area detail (the reference layer)

Each subsection carries the verifier's `net_assessment` (condensed) and the top gaps with file:line evidence and severity. This is the evidence layer — consult it when scoping a ticket.

### A1 — MQM Quality Engine (§5 / E4) [Divergent]
The §5 MQM-2.0 engine is entirely absent from Python — two independent greps for `ETPT/APT/PWPT/NPT/RQS/CQS/ETW/SPM` returned zero matches, while the vision specifies the exact model. What ships is a bespoke additive `100 − penalties` scorer with no per-word/EWC normalisation, forked into two already-drifting copies. Divergent is correct: a real deterministic scorer occupies the slot, so this is reconcile-and-rebuild, not greenfield.
- MQM math (ETPT/APT/PWPT/NPT/RQS/CQS, EWC normalisation) **Absent** — `confidence_service.py:18,68-69,132-133` (**Critical**).
- Versioned content-type metric profiles (ETW/PT/APP/eval-mode) **Absent** — `regulatory_profiles.py:10-130` carries only headings/date-format (**Critical**).
- Statistical Quality Control (word floor, interval, insufficient-sample flag) **Absent** — `confidence_service.py:152-158` (**High**).
- Single-source scorer **Divergent** — forked `confidence_service.py` vs `transmax_sdk/quality/scoring.py:40-136` (**Medium**).

### A2 — Critique / QA Agent (§6 / E5) [Divergent]
Every load-bearing claim reproduced against source. The deterministic engine is genuinely real (pass/block is a pure function with a hard Critical=Blocked rule, so the LLM does not grade itself) — but the entire separation-of-authorship pillar and the ensemble/conservation/§5.7-annotation machinery are absent and greenfield.
- Independent judge on a distinct model **Absent** — reviewer prompt unwired (`prompts/reviewer/v1.0.0.yaml:2`); back-translation runs same-model with router off (`reverse_translate.py:85`, `config.py:115`) (**Critical**).
- Ensemble + disagreement escalation **Absent** — zero matches for `ensemble/most-severe/disagreement` (**Critical**).
- Conservation constraint on revise **Absent** — fixer's full output written back, no span-diff/out-of-scope rejection (`graph.py:489-506`) (**High**).
- §5.7 span annotation object **Stub** — defects are uncited `{category,severity,message}` (`quality_gate.py:244`) (**High**).

### A3 — Translation Agent(s) (E3) [Partial]
The translation engine is genuinely production-grade (batched LLM calls, deterministic per-segment gates, deterministic scoring, A6/A8 provenance, and an independent back-translation reflexion path on a separate model). It diverges from E3 in three load-bearing ways.
- No risk-tier router consumes the per-segment QE; `ContentRiskTier` is a static upload-time enum (`profile_resolver.py:48`) (**High**).
- No prior-approved-PI retrieval, no source-citations; retrieval misses silently swallowed — an A3 violation (`db_service.py:167-174`) (**High**).
- No terminology-adherence or document-coherence metric; eval tests critical-defect recall only (`runner.py:48-62`) (**High**).
- Separation held only by node-ordering: translator emits `status='PASSED'` under the router's key (`translation_engine.py:768` → overwritten `graph.py:398` → read `graph.py:537`) (**Medium**).

### A4 — Knowledge Layer: 5 stores + Black Book (E2/E14) [Divergent]
Strong curation/governance machinery (signed `promote_rule` with approver + reason + audit-before-mutation; C-13 auto-promote removed) built on the architecturally **inverted** asset. The "Black Book" holds positive `source→target` corrections the Knowledge ADR explicitly bans.
- "Black Book" is a positive rule store, ADR-prohibited; none of the 7 negative entry types exist — `models.py:14,22,23` vs `ADR…:46,101`, `Capability-Spec-Black-Book.md:35` (**Critical**).
- Enforcement levels absent; `is_strict` is a vacuous-green trap — editable but dropped at `db_service.py:137-143`, never read by the gate (**Critical**).
- No precedence/resolution engine — `get_constraints` flattens all stores, no ordering/conflict-surfacing/store-of-origin (`db_service.py:78-176`) (**High**).
- Nomenclature and governed Style-guide stores do not exist; TM duplicated across `TMSegment`/`TranslationMemory` — only 2 of 5 stores real (**High**).

### A5 — Document Model, Ingestion & Export (E1) [Partial]
DOCX ingestion/export is genuinely strong and structure-aware; PDF is lossy-by-default. The vision's canonical XLIFF 2.1 interop layer is absent, the stored model is flat segments, and export round-trips by content+index rather than stable ID. (Two mapper overstatements were corrected *downward* — PDF ingestion is thinner than mapped, the mock-extraction mode defaults off — neither raised the grade.)
- XLIFF 2.1 / IDML / structured-XML ingestion **Absent**; upload allow-list is `.pdf/.docx/.txt` (`documents.py:94`) (**High**).
- No queryable structure tree; the richer `ParsedDocument` IR is a parallel transient shape the upload path does not persist (`parsing/base.py:64-91`, `documents.py:148`) (**High**).
- Non-translatables checked post-hoc, never locked pre-translation (`quality_gate.py:286,308,593`) (**High**).
- Export maps by source-text + sequential-index fallback, not stable `segment_id` (the A5 / TMX-3701 risk) (`document_export.py:284`, `documents.py:520`) (**High**).

### A6 — Segmentation (E1.S2) [Partial]
A genuine abbreviation-aware segmenter exists (Solid for the splitting itself). But E1.S2's actual requirement — section path, persisted context window, and regulatory content-type label per segment — is largely unmet. (One mapper claim corrected: PDF uploads *do* get the segmenter; the bypass is DOCX-only.)
- No per-segment section path; Docling discards heading level (`docling_backend.py:102`); DOCX carries only an integer `section_idx` (`database.py:252-258`) (**High**).
- Context window is an ephemeral, two-sized (500 vs 200) prompt slice, never persisted (`translation_engine.py:415-432`, `batch_translator.py:271-285`) (**Medium**).
- Content-type conflated with structural `element_type` — the regulatory content-type (ICF/SmPC/PIL) is a separate profile concept (`parsing/base.py:17-42` vs vision §`142,251-252`) (**Medium**).
- IDs are random UUID4, not content-addressed `(doc_hash, offset, text_hash)`; re-ingest yields fresh IDs (`database.py:222`, v3 plan:217) (**Medium**).

### A7 — Compliance / Regulatory checks (E6) [Stub]
The only enforced compliance artefacts are two per-segment checks that are provably **dead in production** (no caller passes `profile_id`), plus static profile metadata that is data, not a checker. The four headline E6 requirements are genuinely absent. (The date gate is *weaker* than mapped — it resolves to MINOR, below REVIEW_REQUIRED.)
- Regulatory checks are dead code — `if profile_id:` (`quality_gate.py:229`) never satisfied by any production caller (**Critical**).
- No structural-omission detection; per-segment check cannot detect a missing heading; STRUCTURE_ERROR → MAJOR/REVIEW, never BLOCKED (`quality_gate.py:730-758`) (**Critical**).
- Standard-phrase fidelity (paraphrase-of-approved → Critical) **Absent** — the hardest-to-fake QRD requirement (**Critical**).
- MDR/IVDR language matrix, PIL readability, claim-reference linkage all **Absent** / greenfield (**High/Medium**).

### A8 — Risk-Tier Engine + Orchestration (E9) [Divergent]
The vision's E9 content-derived Tier 0–3 engine does not exist. What exists is a validated request schema (caller-supplied archetype+tier) plus an unrelated, default-off LLM cost-router — and the governance tier is wired to none of the downstream decisions. The verifier found it *deader* than mapped: `resolve_job_profile` has zero production callers, and the cited DLQ recovery path also has none.
- Tier is caller-supplied metadata never read back; drives nothing — not depth, gates, human routing, or model choice (`translations.py:48`, `runner.py:29-39`, `graph.py:49-81`) (**Critical**).
- No tier-conditional human review; routing is defect-driven, so a passing Tier-0 doc never forces qualified review (`graph.py:601-614`) (**Critical**).
- LangGraph compiles with no checkpointer; fire-and-forget BackgroundTask — a crash orphans a PROCESSING doc with no resume (`graph.py:697`, `runner.py:52-59`) (**High**).
- Two tier vocabularies; tier-aware `evaluate_status` is dead while the live verdict path is tier-blind (`policy_definitions.py:54-84` vs `quality_gate.py:352-379`) (**High**).

### A9 — Audit / Traceability / Validation (E8) [Partial]
The v2 ledger primitives are best-in-repo and genuinely close the old C-04 domain-separation defect; the independent verifier's no-vacuous-green property (200 + `ok=false` on tamper) is real. Three vision-critical gaps keep it Partial. (Minor, conservative correction: v2 emit breadth is slightly wider than "2 files" — `llm_usage.py` also emits — but this changes no verdict.)
- No validation/change-control registry — `model_registry` + prompt registry are runtime selection/version-pin tables, no validated-status, no production-gating, no rollback (`model_registry.py:51-166`, `prompts/registry.py:65-152`) (**Critical**).
- Human decisions + retrievals never reach v2; `log_reviewer_action` writes only the weak v1 chain and no production endpoint calls it (`audit_service.py:259-275`) (**High**).
- No Part-11 e-signature primitive binding a re-authenticated signer to a version (**High**).
- Daily Merkle anchor not scheduled, S3 Object Lock is a `NotImplementedError` stub, regulatory pack is string-substituted scaffold (`audit_anchor.py:254-264`, `pack_builder.py:286-324`) (**High**).

### A10 — Reviewer Frontend / HITL UI + e-sig (E7) [Partial]
Two parallel reviewer surfaces and neither delivers the E7 cockpit. The canonical `/workspace/jobs/[id]` review tab is read-only; the editable `/workspace/documents/[id]` has a hardcoded initial scorecard, no flagged-first ordering, no back-translation column, and a dead "Approve All" button. (Verifier correction: the HITL→Black-Book bridge is wired to *no* production endpoint — worse than "mis-routed".)
- No Part-11 e-signature anywhere; "approval" is a metadata PATCH with no signer/version/meaning binding; "Approve All" has no handler (`documents.py:276`, `documents/[id]/page.tsx:377-392`) (**Critical**).
- Back-translation built and persisted but never shown side-by-side; lives only as a disconnected tool (`segments.py:117-166`, `tools/page.tsx:427`) (**High**).
- Per-span confirm/override not first-class; no path from a span decision to a signed outcome (**High**).
- Reviewer overrides do not generate Black-Book candidates — live UI uses PATCH `/segments/{id}`, bypassing `submit_correction` which has no production caller (`segments.py:73-114`, `review_service.py:60-118`) (**High**).

### A11 — Eval Harness, Judge Reliability & Goldens (E13) [Divergent]
A genuine, CI-wired offline harness exists — but it probes the **deterministic gate**, not an LLM judge, over ~30 synthetic sentences plus a DOCX fidelity golden set. Every judge-reliability element the vision demands is absent, so the "no vacuous green" meta-capability is never measured. Reconcile onto the scaffold, not greenfield.
- No judge-reliability eval — no judge↔human agreement, no planted-defect recall/precision, no Fleiss' κ (`runner.py:42-79`) (**Critical**).
- CI release-blocker is on the wrong metric — deterministic-gate miss, never judge regression (`eval.yml:50-101`, `ci.yml:53-58`) (**Critical**).
- No human-MQM gold annotations, no dataset versioning, no inter-annotator κ; datasets are ~10 synthetic sentences per language pair, partitioned by language not content type (**Critical/High**).
- No drift detection on agreement/recall/precision and no calibration loop; the only ratchet tracks code hygiene (`ratchet/baseline.json`) (**High**).

### A12 — Security / Residency / Private model + Auth + Integrations + Analytics (E10/E11/E12) [Partial]
A solid, honestly-labelled auth/RBAC + multi-tenancy foundation (provider ABC, real OIDC, fail-loud tenant scoping, production-safety guard) beneath three unmet headline-vision claims. The most actionable near-term fix is the audit gap on access changes.
- EU-resident PRIVATE model **Absent** — every live call egresses to hosted OpenAI; `data_region`/`azure_openai_endpoint` are read in `trust.py` but never declared in config, so residency always renders "Not configured" (`llm.py:76-80`, `model_registry.py:64-77`, `trust.py:25-26,62-66`) (**Critical**).
- Access changes not audited — `update_user_role` commits with no audit event; login/register emit none (an A1 violation) (`auth.py:324-351`) (**High**).
- Veeva Vault / eCOA / CTMS / RIM connectors do not exist in app code (**High**).
- Dashboard is Divergent — reports generic activity (doc counts, tokens, avg confidence), not the six reconcilable outcome metrics (`dashboard.py:224-265`) (**High**).

---

## 5. Reconciliation: new vision vs in-flight v3 plan

There are now **two epic numbering schemes in play, and they collide**:

- The **new vision docs** define **14 product-defensibility epics (E1–E14)**: E1 document model, E2 terminology/knowledge, E3 translation, E4 MQM engine, E5 critique agent, E6 compliance, E7 HITL UI, E8 audit/validation, E9 orchestration/tiering, E10 integrations, E11 analytics, E12 security/residency/private-model, E13 eval harness, E14 nomenclature (per the Knowledge ADR).
- The **in-flight `research/v3_pilot_ready_release_plan.md`** has **11 pilot-hardening epics (E1–E11)** — a *different* program: rotating the leaked key, removing `transmax.db` from history, rationalising the dual-model schema, rebuilding the audit ledger, instance-scoping the quality gate, Redis-backing the circuit breaker, and similar finishing work.

**The numbers overlap but the meanings do not.** v3 `E2` (audit ledger) is not new-vision `E2` (terminology/knowledge); v3 `E8` is not new-vision `E8`. Treating them as one list would cause exactly the single-source-of-truth fork this document warns about.

**Recommendation.** Adopt the **new vision E1–E14 as the canonical product roadmap** — it is the axis along which TransMax becomes *defensible* rather than merely *functional*. **Demote the v3 E1–E11 to substrate / finishing work**: necessary plumbing and debt-paydown that hardens the foundation the new epics build on, but not itself a source of product differentiation. Where a v3 ticket directly serves a new-vision epic (e.g. v3 audit-ledger rebuild → new-vision E8; v3 dual-model rationalisation → new-vision E2/A4 TM reconciliation; v3 checkpointer → new-vision E9/A8), fold it in as substrate under that epic and retire its standalone v3 number. The roadmap below is expressed in **new-vision epic / area IDs**, with substrate work called out where it is a prerequisite.

---

## 6. The disciplined roadmap

The build order is dictated by the dependency spine, not by area number. The keystone annotation gates everything; the honesty fixes gate trust; the rest parallelises once the keystone and engine exist.

```
 PHASE 0  ──────────────────────────────────────────────────────────────
  Stop the vacuous green (honesty fixes + SSOT cleanups)
                        │
                        ▼
 PHASE 1  ──────────────────────────────────────────────────────────────
  THE KEYSTONE TRIAD:  span annotation (§5.7)  ──►  MQM engine (A1)  ──►  judge (A2)
                        │
        ┌───────────────┼────────────────────────────┐
        ▼               ▼                             ▼
 PHASE 2          PHASE 3                        PHASE 4            (parallel)
 Judge            Black Book + 5 stores          Tier routing +
 reliability      + enforcement + precedence     Part-11 e-sig +
 (A11)            (A4)                            one cockpit + real
                                                 QRD/MDR checks (A7,A8,A10)
        └───────────────┴────────────────────────────┘
                        │
                        ▼
 PHASE 5  ──────────────────────────────────────────────────────────────
  Put it in force (validation registry, scheduled anchor, EU/private model,
  XLIFF/structure-tree/stable-IDs, outcome dashboard, connectors)
```

> No story-point or week estimates are given here by design — the dependency order is the binding constraint; sizing follows in ticket grooming.

### Phase 0 — Stop the vacuous green
**Goal:** make every green falsifiable; remove the surfaces that claim governance they don't enforce. **Reversibility:** two-way — these are corrective deletions and small wirings, individually revertible.
- Enforce or remove `is_strict` so "block if violated" actually blocks at the gate, or delete the editable flag (A4).
- Wire or remove the dead regulatory profile checks — pass `profile_id` through the live call sites, or delete the `if profile_id:` branch so it is not mistaken for live coverage (A7).
- Remove the cosmetic "Reviewer agent" dashboard relabel until a real judge exists (A2/A10).
- Emit an access-change audit event **before** every role mutation and on login/register (A12, addendum A1).
- Add a LangGraph checkpointer + a stuck-PROCESSING sweeper so crashed jobs are not orphaned (A8).
- SSOT cleanups: unify the two scorers, reconcile the two TM tables, and pick one canonical reviewer surface — *before* building on top of any of them (A1/A4/A10; absorbs v3 dual-model substrate work).

### Phase 1 — The keystone triad
**Goal:** build the span-level MQM annotation object, then the deterministic engine that scores it, then the independent judge that emits it. **Reversibility:** one-way — introduces the canonical annotation schema and a new model layer; routes to human approval and a shadow-comparison before cutover.
- Define the §5.7 canonical annotation `{segment_id, dimension, subtype, severity, rule_ref, evidence_refs, suggested_fix}` as the shared currency (keystone).
- Build the MQM-2.0 engine: ETPT/APT/PWPT/NPT/RQS/CQS over an annotation set with EWC per-1000-word normalisation, the 0/1/5/25 SPM ladder, and SQC (word floor + confidence interval + insufficient-sample flag) (A1).
- Build the independent judge: a distinct model fed only source+target+grounding, emitting the §5.7 annotation; never seeing the translator's reasoning; wired as a graph node so the producer no longer self-gates (A2).
- Add the conservation constraint on revise (span-diff + out-of-scope rejection) (A2).

### Phase 2 — Judge reliability (the no-vacuous-green proof)
**Goal:** prove the judge is trustworthy and make CI block on its reliability. **Reversibility:** two-way — additive eval infrastructure.
- Human-MQM gold annotations per content type, versioned, with inter-annotator Fleiss' κ ≥ 0.80 (A11).
- Judge↔human agreement and planted-defect recall/precision metrics (A11).
- A CI gate that blocks release on judge-reliability regression, not just deterministic-gate misses (A11).

### Phase 3 — Black Book + the knowledge layer
**Goal:** invert the asset to negative-and-adjudicated, complete the five stores, and make enforcement and precedence real. **Reversibility:** one-way — schema and resolution-order changes; routes to human approval.
- Reconcile the positive rule store into a strictly-negative, adjudicated Black Book with the 7 typed entry kinds, matchers (incl. semantic + confidence-floor escalation), scope hierarchy (most-specific-wins), and `severity/maps_to` citing `entry_id` (A4).
- Stand up the missing stores — Nomenclature (substance↔INN↔confusables) and a governed Style guide — and consolidate TM to one canonical store (A4/A14).
- Implement the four enforcement levels (suggested/preferred/required/locked) and the deterministic precedence engine (BlackBook→Nomenclature→Termbase→TM→Style) with conflicts surfaced, not auto-reconciled, and store-of-origin logged per applied constraint (A4).

### Phase 4 — Routing, signature, cockpit, real compliance (parallel)
**Goal:** make risk drive the pipeline, make sign-off mean something, and make compliance fire. **Reversibility:** mixed — tier-routing and the cockpit are two-way; the Part-11 e-signature is one-way (regulatory primitive, human-approved).
- Content-derived Tier 0–3 engine that drives evaluation depth (100% vs sampled), gate selection, model strength, and human role — consuming the per-segment QE (A8/A3).
- Part-11 electronic signature bound to user + version + timestamp + meaning, immutable, reversible only by a new signed action (A10/A9).
- Reconcile the two reviewer surfaces into **one** cockpit: flagged-spans-first, source/target/back-translation side-by-side, per-span confirm/override/amend → signed decision; wire reviewer overrides into the learning bridge (A10).
- Real QRD structure + standard-phrase fidelity checker (paraphrase→Critical), MDR/IVDR language matrix, PIL readability, claim-reference linkage — firing on the resolved profile (A7).

### Phase 5 — Put it in force
**Goal:** turn built primitives into operating, validated, in-force controls. **Reversibility:** mixed — registry and connectors are one-way (change-control + external contracts, human-approved); dashboard and structure-tree work are two-way.
- Validation & change-control registry: only validated versions run in production; one-action rollback across models, prompts, rules, termbases, profiles (A9).
- Migrate human-decision and retrieval events into the v2 ledger; retire v1; schedule the daily Merkle anchor and ship S3 Object Lock retention (A9; absorbs v3 audit-ledger substrate work).
- EU-resident / private model deployment within the validated boundary, with residency/encryption evidenced (A12).
- XLIFF 2.1 canonical interop layer, queryable structure tree, and content-addressed stable segment IDs end-to-end (A5/A6).
- LangOps outcome dashboard reconciling to the audit log: cycle time, first-pass quality, reviewer hours, cost-per-outcome, Critical-error escape rate, Day-215 (A12/E11).
- Veeva Vault / eCOA / CTMS / RIM connectors, contract-tested (A12/E10).

---

## 7. Method note

This analysis was produced by mapping the codebase against 12 capability areas (A1–A12) drawn from the vision's E1–E14 epics, then adversarially verifying each map. For every area, two agents ran in tandem — a mapper that catalogued each capability's status with file:line evidence, and an independent verifier that re-ran the greps, re-read the cited code, and rendered a `confirmed / overstated / understated` judgement on every load-bearing claim before issuing the `corrected_maturity` and `net_assessment` used in this document. That is **24 parallel map+verify agents over 12 areas**, with every claim checked at file:line against the actual source and the four vision docs. The notable pattern: the verifier's corrections ran **almost always toward more honesty, not less** — dead code was found deader (A7 date gate resolves to MINOR not MAJOR; A8 `resolve_job_profile` and the DLQ path have zero production callers; A10 `submit_correction` is wired to no endpoint), and the two material overstatements (A5 PDF-ingestion pluggability, A6 segmenter wiring) were corrected downward without raising any grade. The maturity values in §2 and §4 are the verifier's, not the mapper's.
