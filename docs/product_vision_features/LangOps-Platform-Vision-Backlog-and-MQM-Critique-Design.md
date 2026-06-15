# Agentic LangOps for Regulated Industries
## Product Vision, Strategic Backlog, and Detailed Design (MQM Quality Engine + Critique Agent)

**Audience:** product, engineering, applied-science and regulatory/quality leads on the build team.
**Status:** v0.1 — working reference. Sections 5 and 6 are build-ready specifications; the backlog (Section 4) is the planning baseline.
**Scope:** Pharma/life sciences first, with cross-industry hooks (banking, legal) called out where the same machinery applies.

---

## 0. How to use this document

This is the single source of truth for *what we are building and why*, and the *engineering specification* for the two components that carry most of the platform's defensibility: the MQM quality engine and the critique agent.

- **Sections 1–3** set direction: vision, the principles every story must respect, and the architecture at a glance.
- **Section 4** is the strategic backlog — epics, capabilities, representative stories, sequencing. Treat it as the planning baseline, not a frozen contract.
- **Sections 5–6** are the detailed designs. These are deliberately precise: data models, formulas, interfaces, failure modes.
- **Sections 7–9** cover the eval strategy, open decisions (ADR candidates), and a glossary.

Where a figure or claim depends on the prior market research, it is referenced rather than restated. Where a number is a design proposal (a weight, a threshold), it is flagged as configurable.

---

## 1. Product vision

### 1.1 North star

> A governed language operation in which digital agents do the drafting, terminology enforcement, quality scoring, formatting and package assembly, and accountable human experts do the judgement, validation and sign-off — so regulated content reaches every market faster, at lower cost, and with a stronger audit trail than the manual process it replaces.

The wording matters. We are not selling "AI translation". We are selling a **language operation** — a managed, validated, auditable capability — in which the unit of value is a compliant, approved, in-market document, not a translated segment.

### 1.2 The shift we are betting on

| From (incumbent CAT/TMS world) | To (agentic LangOps) |
| --- | --- |
| Segment + translation-memory as the atomic unit | Document and submission as the unit of reasoning |
| Quality measured late, by sampling, subjectively | Quality estimated continuously, span-level, against a calibrated rubric |
| Compliance checked by humans at the end | Regulatory rules enforced in-line by a compliance agent, with humans adjudicating exceptions |
| Humans translate, tools assist | Agents draft, humans validate and approve |
| Priced per word | Priced per compliant outcome |
| Audit trail reconstructed after the fact | Traceability produced by construction |

### 1.3 Vision pillars

1. **Human accountability is structural.** A named, qualified human signs every Tier-0/Tier-1 output. The platform makes that signature meaningful by giving the reviewer a defensible, evidence-backed package — not a wall of text to re-read.
2. **Quality is a measured quantity, not an opinion.** Every output carries an MQM score, span-level error annotations, and a pass/fail against a content-type-specific threshold.
3. **Compliance is in the loop, not after it.** EMA QRD standard phrases, MDR/IVDR language matrices, MedDRA terminology and the like are enforced as rules the platform checks, cites and escalates.
4. **Validated and private by default.** EU data residency, private model deployment, GAMP 5 / CSV validation, 21 CFR Part 11 / EU GMP Annex 11 controls are platform properties, not project add-ons.
5. **Built to be transferred.** Everything — runbooks, evals, golden datasets, validation evidence — is produced so a client GCC can operate it after BOT handover.

### 1.4 What we are explicitly **not** building (scope discipline)

- Not a general-purpose consumer translator.
- Not a thin wrapper over an incumbent TMS (we may *interoperate* with XLIFF/Veeva, but the workflow engine is ours).
- Not a fully autonomous "no human" pipeline for regulated content. The EMA reflection paper requires close human supervision; our design treats that as a feature, not a constraint to engineer around.
- Not a bespoke per-client codebase. One platform, configured by content-type profiles and connectors.

### 1.5 Success metrics (north-star + supporting)

**North-star:** *Compliant cycle time per document type* — calendar time from content-ready to approved-in-market, at non-inferior quality.

Supporting metrics, all instrumented from day one:
- **First-pass MQM quality** (per content type) and pass rate at the first human review.
- **Reviewer hours per 1,000 words** (the bottleneck we are actually attacking).
- **Cost per compliant outcome** versus the incumbent baseline.
- **On-time Day-215** delivery rate for labelling.
- **Critical-error escape rate** — Critical MQM errors found *after* sign-off (target: zero; this is the metric that protects the franchise).
- **Judge↔human agreement** (the critique agent's own reliability; see §6.10).

---

## 2. Product principles (non-negotiables the build team enforces)

These are binding. A story that violates one of these is not "done", regardless of demo quality.

1. **Separation of authorship.** The agent that *judges* an output must be independent of the agent that *produced* it — different model where feasible, never a shared context or scratchpad, and the judge never sees the author's reasoning trace. This is the precondition for a valid LLM-as-judge (§6.2).
2. **No vacuous green.** A passing score must be *earnable, not gameable*. Every quality gate is backstopped by planted-defect probes, judge-disagreement escalation, and human spot-audit of "passed" content (§6.5). A green dashboard that cannot be falsified is not trusted.
3. **Conservation before correctness.** When revising, the platform fixes flagged spans and preserves everything else. It does not silently rewrite, "improve" or re-order approved structure. Over-helpful rewriting is how regulated meaning gets lost.
4. **Determinism where it counts.** Standard-phrase substitution, terminology enforcement, numeric/unit handling and rule checks are deterministic and reproducible. Generative latitude is confined to where it adds value and is always downstream of a check.
5. **Traceability by construction.** Every agent action, model version, prompt version, retrieved source and human decision is logged to an immutable, queryable trail. If it is not logged, it did not happen.
6. **Human accountability is real.** The reviewer's confirmation is an electronic signature (Part 11), captured against a specific version, reversible only by a new signed action.
7. **Private and validated by default.** No content leaves the validated boundary. Models, prompts and rule sets are version-controlled, validated artefacts under change control.

> These map to the governance posture used elsewhere in your work (separation of authorship; no vacuous green; conservation before correctness; a structural floor rather than reliance on individual discipline). They are stated here as platform law so the build team can hold each other to them.

---

## 3. Architecture at a glance

A fuller treatment is in the research report; this is the orientation the backlog assumes.

**Two planes.** A *data plane* (the agents that move and transform content) and a *control plane* (governance, eval, audit, routing). The control plane is not optional middleware — for regulated work it is the product.

**Data-plane agents**
- **Orchestrator** — plans the job from content type, risk tier, locales and regulatory context; coordinates the specialists; owns the state machine.
- **Ingestion/parsing agent** — Word, structured XML, PDF, IDML, XLIFF → a normalised document model.
- **Terminology agent** — enforces approved termbases, MedDRA, QRD standard phrases.
- **Translation agent(s)** — RAG-grounded drafting against TM, termbase, prior approved product information, regulatory corpora.
- **Critique/QA agent** — span-level MQM annotation and the bounded revise loop (§6).
- **Compliance agent** — QRD structure, standard-phrase fidelity, readability heuristics, MDR/IVDR language matrices, claim↔reference linkage.
- **Back-translation & reconciliation agent** — ICF / PRO-COA workflows.
- **Formatting/DTP agent** — layout and artwork fidelity.
- **ICR-support agent** — assembles reviewer-ready packages and manages queries.

**Control-plane services**
- **Risk-tier engine** (routing), **MQM quality engine** (§5), **Eval harness + golden datasets** (§7), **Audit/traceability store**, **Validation & change-control registry** (models, prompts, rules, termbases as versioned artefacts).

**Risk tiers drive routing.** Tiering is the single most important control. It decides how much human review, sampling vs 100% evaluation, and which gates apply.

| Tier | Examples | Evaluation | Human role |
| --- | --- | --- | --- |
| **Tier 0 — Critical** | SmPC dosing/contraindications, ICF safety/risk sections, labelling standard phrases, PV narrative causality | 100% MQM, Critical-error auto-fail, dual judge ensemble | Mandatory qualified review + signed approval |
| **Tier 1 — High** | Full SmPC/PIL, protocols, PSUR, PRO/COA items | 100% MQM | Mandatory review; targeted to flagged spans |
| **Tier 2 — Moderate** | Med-info responses, MSL materials, promotional transcreation | MQM + statistical sampling | Review where flagged or below threshold |
| **Tier 3 — Low** | Internal drafts, non-regulated comms | MQM sampling | Spot-audit only |

---

## 4. Strategic backlog

### 4.1 Conventions

- **Hierarchy:** Epic → Capability → Story. Stories are INVEST-shaped with explicit acceptance criteria.
- **Every story is tagged** with: risk tier(s) it touches, the principle(s) (§2) it must honour, and its dependencies.
- **Definition of Ready (regulated additions):** acceptance criteria written; test data identified; the validation/audit implications named; the eval that will prove it exists or is in the same sprint.
- **Definition of Done (regulated additions):** automated tests green *and* non-vacuous (planted-defect check passes); audit-trail entries verified; model/prompt/rule versions pinned; reviewer-facing evidence renders correctly; documentation updated for the eventual transfer.

### 4.2 Release map (Now / Next / Later, against BOT phases)

- **R0 — Walking skeleton (weeks 0–6, Build).** Prove the spine end-to-end on a trivial path: ingest → translate one segment → MQM score → log to audit → render to a reviewer → capture a signed decision. No quality target; the point is that the *control plane* works.
- **R1 — Wedge workflow: SmPC/PIL labelling, Day-215 (months 1.5–6, Build).** Rules-heavy, high-frequency, unambiguous ROI. Ship the full loop for this one workflow to a measurable quality bar.
- **R2 — ICF + back-translation/reconciliation (months 4–9, Build→Operate).** Second high-value workflow; introduces the back-translation agent.
- **R3 — Operate at scale (months 6–18, Operate).** Add PV narratives, PRO/COA orchestration, MLR transcreation; Veeva/eCOA/CTMS integration; outcome-based SLAs live.
- **R4 — Transfer & extend (months 18–36, Transfer).** GCC handover package; banking and legal vertical configurations.

### 4.3 Epics

> Stories below are *representative*, not exhaustive — enough to size the work and lock the interfaces. Detailed designs for E4 and E5 are in §5–§6.

#### E1 — Document model & ingestion
*Capability:* turn heterogeneous source files into a normalised, segment-and-structure-aware document model that survives round-trips.
- **E1.S1** As the platform, I parse DOCX/XLIFF/IDML/structured XML/PDF into a normalised document model that preserves structure, inline tags and layout anchors. *AC:* round-trip export is byte-faithful for tags and structure on the test corpus; no content loss; structure tree is queryable. *Tier:* all. *Principle:* conservation.
- **E1.S2** As the platform, I segment text while keeping document- and section-level context attached to each segment. *AC:* every segment carries section path, surrounding context window, and content-type label.
- **E1.S3** As the platform, I detect and protect non-translatables (codes, doses, units, placeholders). *AC:* zero unintended edits to protected tokens; protected spans flagged for the numeric/unit checker.

#### E2 — Terminology & knowledge (RAG)
*Capability:* a living, governed knowledge layer the agents retrieve from and the platform enforces.
- **E2.S1** Ingest and version approved termbases, MedDRA, and QRD standard phrases as governed artefacts. *AC:* every term/phrase has a version, effective date and source; changes are change-controlled.
- **E2.S2** Serve termbase/TM/prior-approved-PI via retrieval to the translation, critique and compliance agents. *AC:* retrieval returns source-cited candidates; retrieval misses are logged and escalate rather than silently proceed.
- **E2.S3** Deterministic standard-phrase substitution for QRD content. *AC:* approved phrases are inserted verbatim; any deviation is raised as a Critical terminology error (see §5.3). *Principle:* determinism, no vacuous green.

#### E3 — Translation agent(s)
- **E3.S1** RAG-grounded draft translation at document level with terminology constraints. *AC:* terminology adherence ≥ target on the eval set; document-level coherence checks pass.
- **E3.S2** Confidence/quality-estimation signal emitted per segment for routing. *AC:* low-confidence segments are flagged to the risk-tier engine before review.
- **E3.S3** Translator agent never self-certifies. *AC:* no path exists by which the translation agent sets its own pass status. *Principle:* separation of authorship.

#### E4 — MQM quality engine *(detailed design: §5)*
- **E4.S1** Compute raw and calibrated MQM scores from span annotations, per the content-type profile. *AC:* formulas match §5.5 exactly; outputs reproducible bit-for-bit given the same annotations and profile.
- **E4.S2** Content-type metric profiles (ICF, SmPC/PIL, PV, promo) configurable as versioned artefacts. *AC:* profile change is change-controlled and re-runs historical scores in shadow for comparison.
- **E4.S3** Statistical Quality Control for short documents: confidence intervals and "insufficient sample" flags. *AC:* documents below the sample-size floor return a score *with* an interval and a 100%-evaluation requirement, never a bare point score. *Principle:* no vacuous green.

#### E5 — Critique / QA agent *(detailed design: §6)*
- **E5.S1** Independent span-level MQM annotation (the judge). *AC:* judge runs on a separate model/context; emits structured annotations per §6.7; cites the rule/term it invokes.
- **E5.S2** Bounded translate→critique→revise loop with conservation constraint. *AC:* reviser edits only flagged spans; loop halts on pass, max-iterations, or no-improvement; every iteration logged.
- **E5.S3** Ensemble judging with disagreement escalation. *AC:* judge disagreement above threshold escalates to human rather than averaging. *Principle:* no vacuous green.
- **E5.S4** Confidence-and-escalation policy wired to the risk-tier engine. *AC:* Tier-0 always escalates on any Critical or near-threshold result.

#### E6 — Compliance / regulatory checks
- **E6.S1** QRD structure and standard-phrase fidelity checker. *AC:* deviations flagged with the QRD reference; structural omissions block sign-off.
- **E6.S2** MDR/IVDR language-matrix enforcement (which languages are mandatory per market). *AC:* missing-language gaps surfaced before release.
- **E6.S3** Readability heuristics for PILs and claim↔reference linkage for promo. *AC:* checks produce reviewer-facing, citable findings.

#### E7 — Human–agent collaboration UI & review workflow
- **E7.S1** Reviewer workspace: source/target/back-translation side-by-side, flagged spans first, with the evidence and the suggested fix. *AC:* a reviewer can confirm/override each span and reach a signed decision without leaving the view.
- **E7.S2** Electronic signature capture (Part 11). *AC:* signature bound to user, version, timestamp, meaning-of-signature; immutable.
- **E7.S3** Query/clarification threads between reviewers and the ICR-support agent. *AC:* queries and resolutions are part of the audit trail.

#### E8 — Audit, traceability & validation
- **E8.S1** Immutable event log of every agent action, model/prompt/rule version, retrieval and human decision. *AC:* any output is fully reconstructable from the log; tamper-evident.
- **E8.S2** Validation & change-control registry for models, prompts, rules, termbases, profiles. *AC:* nothing runs in production that is not a registered, validated version; rollbacks are one action.
- **E8.S3** GAMP 5 / CSV evidence generation. *AC:* validation evidence is produced as a by-product of the pipeline, not assembled manually.

#### E9 — Orchestration & risk-tier routing
- **E9.S1** Risk-tier engine assigns tier from content type, section and signals; routes accordingly. *AC:* routing decisions are explainable and logged; tier rules are versioned.
- **E9.S2** State machine and handoff between agents and to humans. *AC:* no orphaned jobs; every state transition is recoverable and audited.

#### E10 — Integrations
- **E10.S1** Veeva Vault (RIM/PromoMats/QualityDocs) connector. *AC:* documents and approvals round-trip with metadata fidelity.
- **E10.S2** eCOA / CTMS / RIM connectors for clinical and submission flows. *AC:* contract-tested against partner sandboxes.

#### E11 — Analytics & LangOps dashboards
- **E11.S1** Operational dashboard: cycle time, first-pass quality, reviewer hours, cost per outcome, Critical-error escape rate, Day-215 on-time. *AC:* metrics reconcile to the audit log; exportable for SLA reporting.

#### E12 — Security, data residency & private model platform
- **E12.S1** EU-resident, private model deployment within the validated boundary. *AC:* no content egress beyond boundary; pen-tested; GDPR/IP controls evidenced.
- **E12.S2** Secrets, access control, RBAC aligned to reviewer roles. *AC:* least-privilege; access changes audited.

#### E13 — Eval harness & golden datasets *(the meta-capability; see §7)*
- **E13.S1** Golden datasets per content type with human-MQM gold annotations. *AC:* datasets versioned; inter-annotator agreement measured (target Fleiss' κ ≥ 0.80).
- **E13.S2** Automated eval gates in CI: translation quality, judge reliability, planted-defect recall, regression. *AC:* a release is blocked if judge↔human agreement or planted-defect recall regresses. *Principle:* no vacuous green.

### 4.4 Cross-cutting non-functional backlog
Latency/throughput SLAs per tier; reproducibility (pinned versions, seeded determinism where required); disaster recovery; cost governance per model call; accessibility of the reviewer UI; observability of the control plane.

---

## 5. Detailed design — MQM quality engine

### 5.1 Purpose and placement

The MQM engine is the platform's measurement instrument. It converts span-level error annotations (produced by the critique agent, §6, or by humans) into a reproducible numeric score and a pass/fail rating against a content-type-specific specification. It is deliberately **separate from the thing that produces annotations** — the engine does pure, deterministic arithmetic over an annotation set, so the same annotations always yield the same score. The judgement lives in the critique agent and the human; the engine is the calculator and the rule-keeper.

It sits in the control plane and is called: (a) continuously during the critique loop, (b) at gate checkpoints for routing, and (c) at human review to present the evidence.

### 5.2 The seven dimensions, instantiated for pharma

MQM-Core defines seven top-level error dimensions. We use all seven and pin pharma-relevant subtypes and worked examples to each. (The dimensions and their meanings are fixed by the MQM typology; the subtype selection and examples are our instantiation.)

| Dimension | What it means (MQM) | Pharma-relevant subtypes we annotate | Worked example (EN→DE/FR) |
| --- | --- | --- | --- |
| **Terminology** | Use of domain/term-base terms; consistency | Wrong term vs approved termbase; QRD standard-phrase deviation; MedDRA mismatch; inconsistent term within a submission | Rendering an approved standard phrase in the linguist's own words → Critical |
| **Accuracy** | Correspondence of meaning source↔target | Mistranslation, Omission, Addition, Untranslated; **numeric/unit/dose error** (custom subtype); negation flip | "twice daily" rendered as "once daily" → Critical |
| **Linguistic conventions** | Grammar, spelling, punctuation, register of the target language | Grammar, spelling, punctuation, register | Agreement error that changes which drug a warning applies to → Major |
| **Style** | Adherence to style spec, naturalness | Awkward, inconsistent style, organisation style | Clunky but unambiguous phrasing in a PIL → Minor |
| **Locale conventions** | Local formatting norms | Number/date/decimal/measurement format; local address/regulatory formatting | Decimal comma vs point in a dose table → Major (ambiguity risk) |
| **Audience appropriateness** | Fit for the intended reader | Readability for patients; reading-level mismatch for ICF/PIL | Clinical jargon in a patient leaflet → Major |
| **Design & markup** | Layout, tags, formatting integrity | Broken inline tag; lost emphasis on a warning; layout corruption | Bold warning rendered as body text → Major |

Two custom subtypes we add explicitly because they carry outsized regulatory risk: **numeric/unit/dose fidelity** (under Accuracy) and **standard-phrase fidelity** (under Terminology). Both are deterministically checkable and both default to Critical when violated.

### 5.3 Severity model and the pharma severity rubric

MQM severity levels and the recommended exponential **Severity Penalty Multipliers (SPM)** are: **Neutral = 0, Minor = 1, Major = 5, Critical = 25**. We adopt these as defaults and keep them configurable.

We pin a pharma rubric so severity assignment is consistent across judges and humans:

| Severity | SPM | Pharma rule of thumb | Examples |
| --- | --- | --- | --- |
| **Critical** | 25 | Could cause patient harm, regulatory rejection, or renders content unfit. **Auto-fail** regardless of score. | Dose/frequency/route error; omitted contraindication or warning; negation flip; standard-phrase deviation; wrong drug name |
| **Major** | 5 | Seriously affects understandability/usability or appears in a high-visibility section | Altered efficacy claim; ambiguous numeric format in a dosing table; jargon in patient-facing text |
| **Minor** | 1 | Limited impact; does not impede use | Stylistic awkwardness; minor punctuation |
| **Neutral** | 0 | Preferential; flagged for attention, acceptable | Reviewer-preferred wording that is not an error |

**The Critical auto-fail rule is absolute** and cannot be overridden by an otherwise-passing score. This is the single most important guardrail in the engine.

### 5.4 Content-type metric profiles

Different content carries different risk, so each content type gets a versioned **metric profile** that sets: which subtypes are in scope, **Error-Type Weights (ETW)**, the **Passing Threshold (PT)**, the **Acceptable Penalty Points (APP)** per 1,000 words, and whether evaluation is 100% or sampled. Proposed starting profiles (all configurable, all to be calibrated against gold data before go-live):

| Profile | ETW emphasis | PT (calibrated) | APP / 1,000 words | Evaluation | Critical auto-fail |
| --- | --- | --- | --- | --- | --- |
| **ICF (patient-facing)** | Accuracy ×3, Terminology ×3, Audience ×2 | 97 | 3 | 100% | Yes |
| **SmPC/PIL (labelling)** | Accuracy ×3, Terminology ×3 (standard-phrase Critical), Design ×2 | 98 | 2 | 100% | Yes |
| **PV narrative** | Accuracy ×3, Terminology ×3 | 97 | 3 | 100% | Yes |
| **PRO/COA item** | Accuracy ×3, Audience ×2 (concept equivalence) | 97 | 3 | 100% + cognitive debriefing | Yes |
| **Promotional / transcreation** | Style ×2, Audience ×2, Accuracy ×2 | 90 | 10 | Sampled + 100% on claims | Yes (claims only) |

Rationale: labelling and ICF tolerate almost no error and weight Accuracy/Terminology hardest; promotional content legitimately allows stylistic latitude (transcreation), so Style/Audience are weighted up and the tolerance is looser — but *claims* within promo snap back to Critical, because a mistranslated claim is a regulatory event.

### 5.5 Scoring model (exact)

The engine implements the MQM 2.0 scoring model. Definitions:

- **EWC** — Evaluation Word Count (source words evaluated).
- **RWC** — Reference Word Count, fixed at **1,000**.
- **MSV** — Maximum Score Value = **100**.
- **ETW** — Error-Type Weight (from the profile).
- **SPM** — Severity Penalty Multiplier (0 / 1 / 5 / 25).

Per error type *i*:

```
ETPT_i = ETW_i × Σ_severity ( ErrorCount_{i,severity} × SPM_severity )
```

Aggregate:

```
APT  = Σ_i ETPT_i                      # Absolute Penalty Total
PWPT = APT / EWC                       # Per-Word Penalty Total
NPT  = PWPT × RWC = (APT × 1000)/EWC   # Normed Penalty Total (penalty pts / 1,000 words)
```

**Raw Quality Score** (the portion of content that is correct, on a 0–100 scale):

```
RQS = MSV × (1 − PWPT) = 100 × (1 − APT/EWC)
```

*Check:* 10 minor errors (SPM 1) in 1,000 words → APT = 10, PWPT = 0.01, RQS = 99. Matches the MQM spec example.

**Calibrated Quality Score** (magnifies the narrow band near 100 so thresholds are interpretable). Given a profile's APP and PT:

```
SF  = (MSV − PT) / APP                 # Scaling Factor
CQS = MSV − (NPT × SF)
```

*Check:* PT = 90, APP = 10 → SF = (100−90)/10 = 1. At NPT = 10, CQS = 100 − 10 = 90 (pass boundary); at NPT = 20, CQS = 80 (fail). For a stricter SmPC profile, PT = 98, APP = 2 → SF = 1; NPT = 2 → CQS = 98; NPT = 3 → CQS = 97 (fail).

**Pass/fail:**

```
PASS  iff  QS ≥ PT   AND   CriticalErrorCount = 0
FAIL  otherwise
```

The engine reports both RQS (comparable across profiles) and CQS (interpretable within a profile), the dimension-level breakdown, and the pass/fail with the deciding reason.

### 5.6 Statistical Quality Control for short documents

Regulated documents are often far below the 500–20,000-word range MQM assumes — a single SmPC section or ICF clause may be 80 words. At those sizes a point score is unstable: one error swings it wildly. The engine therefore implements SQC for small samples:

- Below a configurable **sample-size floor** (proposed 500 words), the engine returns the score **with a confidence interval**, not a bare point estimate, and sets an **insufficient-sample flag**.
- For Tier-0/Tier-1, short content is **always 100% evaluated** (no sampling) and routed to human review regardless of score — a high short-document score is treated as "not yet trusted", honouring *no vacuous green*.
- Confidence intervals are surfaced in the reviewer UI so a near-threshold short document is visibly uncertain rather than falsely precise.

### 5.7 Annotation data model

The engine consumes and the critique agent produces a single canonical annotation object. (Straight quotes used deliberately — this is a schema.)

```json
{
  "annotation_id": "uuid",
  "document_id": "uuid",
  "segment_id": "uuid",
  "locale": "de-DE",
  "content_type": "SmPC",
  "risk_tier": 0,
  "source_span": { "text": "twice daily", "start": 120, "end": 131 },
  "target_span": { "text": "einmal taeglich", "start": 140, "end": 155 },
  "dimension": "Accuracy",
  "subtype": "Mistranslation",
  "severity": "Critical",
  "is_auto_fail": true,
  "explanation": "Frequency altered from twice daily to once daily.",
  "rule_ref": "DOSING-FIDELITY",
  "evidence_refs": ["termbase:v12#freq", "approved_PI:2024-06#sec4.2"],
  "suggested_fix": "zweimal taeglich",
  "produced_by": "critique-agent",
  "judge_id": "judge-A",
  "judge_confidence": 0.94,
  "model_version": "judge-model@1.4.0",
  "prompt_version": "critique-prompt@2.1",
  "human_decision": null,
  "created_at": "iso-8601"
}
```

Notes: `rule_ref` and `evidence_refs` make every annotation *citable* — the reviewer sees *why*. `produced_by`, `judge_id`, `model_version`, `prompt_version` make it *reproducible* and *auditable*. `human_decision` is filled at review (confirm / override / amend) and is what feeds calibration (§6.10).

### 5.8 Engine pipeline (per document)

1. Receive document model + annotation set + content-type profile (versioned).
2. Validate annotations against schema and profile scope; reject malformed.
3. Compute ETPT per type → APT → PWPT → NPT.
4. Compute RQS and CQS; apply Critical auto-fail.
5. If EWC < floor → attach confidence interval + insufficient-sample flag.
6. Emit score object: scores, dimension breakdown, pass/fail + reason, sample-quality flags, full provenance.
7. Write the score object and inputs to the audit store.

### 5.9 Determinism, reproducibility, interfaces

- The engine is **pure**: same annotations + same profile version ⇒ same output, always. No model calls inside the engine.
- **Interface (conceptual):** `score(document_model, annotations[], profile_version) → ScoreObject`. Profile is referenced by version, never inlined, so a re-score is exact.
- **Re-scoring:** a profile change triggers a *shadow* re-score of affected historical documents for impact analysis before adoption (E4.S2).

### 5.10 Failure modes & guardrails

| Failure mode | Guardrail |
| --- | --- |
| Score gamed by under-annotation (judge misses errors) | Backstopped by §6 ensemble + planted-defect recall in CI; engine cannot fix bad input, so the *input producer* is held to a reliability bar |
| Short-document false precision | SQC interval + insufficient-sample flag + forced human review |
| Profile drift / silent threshold change | Profiles are versioned, change-controlled, shadow-re-scored |
| Critical error masked by good overall score | Critical auto-fail, non-overridable |
| Inconsistent severity between annotators | Pharma severity rubric (§5.3) + IAA tracking (§7) |

---

## 6. Detailed design — critique / QA agent

### 6.1 Role

The critique agent is the platform's *independent assessor*. It does two jobs, kept distinct:

1. **Judge** — produce span-level MQM annotations (dimension, subtype, severity, evidence, suggested fix) over a translation, grounded in the termbase, approved prior PI and regulatory rules. These annotations feed the MQM engine (§5).
2. **Drive the revise loop** — direct a *separate* reviser step to fix flagged spans, then re-judge, within strict bounds.

It is the embodiment of two principles: *separation of authorship* (it must be independent of whatever produced the translation) and *no vacuous green* (its passes must be hard to fake).

### 6.2 Separation of authorship (independence requirements)

These are hard requirements, not preferences:

- The judge runs on a **different model** from the translation agent wherever feasible; at minimum a **different prompt, different context, and no shared memory or scratchpad**.
- The judge **never sees the translator's reasoning trace** — only source, target, and grounding. Seeing the author's rationale biases the judge toward agreement.
- The judge has **no ability to set pass status directly** — it only emits annotations; the deterministic engine decides pass/fail. The agent cannot mark its own homework.
- The **reviser is a distinct step** from the judge. The thing that proposes a fix is not the thing that then certifies the fix is good; the next judging pass re-evaluates independently.

This three-way split — author → independent judge → independent reviser, with a deterministic engine and an accountable human on top — is the structural floor that makes the quality signal trustworthy.

### 6.3 The critique loop

```
draft ─▶ JUDGE (annotate spans) ─▶ MQM engine (score)
              │
              ├─ PASS & no Critical ─▶ route per tier (human review or audit-sample)
              │
              └─ FAIL ─▶ REVISE (fix flagged spans only) ─▶ re-JUDGE ─▶ re-score
                                                                  │
                            ┌─────────────────────────────────────┘
                            ▼
   STOP when: PASS  |  max_iterations reached  |  no_improvement between iterations
   THEN if not PASS ─▶ escalate to human with full annotation history
```

- **Conservation constraint on REVISE:** the reviser may edit **only** the flagged spans and must not touch unflagged text, structure or approved standard phrases. Diffs are computed and any out-of-scope change is rejected automatically.
- **Stopping criteria:** pass; or `max_iterations` (proposed 2–3 for Tier-0/1, to avoid the loop "polishing" its way to a hollow pass); or no measurable improvement. Non-passing content escalates — it is never force-passed.
- **Every iteration is logged** (annotations, edits, scores, versions) so the reviewer and the auditor can see the whole trajectory.

### 6.4 Ensemble judging

- **Multiple judges** for Tier-0/Tier-1 (proposed: two judges of different model lineage; a third as tie-breaker).
- **Reference-free QE** (source↔target) is the baseline; **reference-based** judging is used additionally where a TM match or approved prior PI provides a reference.
- **Aggregation is risk-averse:** take the **most severe** classification across judges for any span, and treat **judge disagreement above a threshold as an escalation signal**, not something to average away. Averaging disagreement is precisely how vacuous greens are manufactured.

### 6.5 Anti-gaming controls (no vacuous green, operationalised)

1. **Independence** (§6.2) — removes the largest source of self-flattery.
2. **Planted-defect probes** — known errors are seeded into eval batches; the judge must catch them. Recall on planted defects is a CI gate (E13.S2). A judge that stops catching planted Criticals fails the build.
3. **Disagreement escalation** (§6.4).
4. **Critical auto-fail** in the engine (§5.5) — no score can buy back a Critical.
5. **Human spot-audit of passed content** — a sampled fraction of auto-passed Tier-2/3 output is human-reviewed; escapes feed back into calibration and tighten thresholds.
6. **The reviser cannot edit the rubric, the profile, or the termbase** — it changes text, never the standard it is judged against.

### 6.6 Confidence & escalation policy

Escalate to a human (rather than auto-proceed) when **any** of:
- Tier-0 content, always, on any Critical or near-threshold result.
- Judge ensemble disagreement above threshold.
- Judge confidence below a per-tier floor.
- Calibrated score within a configurable band of the threshold (the "uncertain" zone).
- A regulatory-rule or standard-phrase violation is flagged.
- Novel terminology or low TM/termbase leverage (the platform is least sure here).
- Short document below the SQC floor (§5.6).

Auto-approve only Tier-2/3, high-confidence, high-leverage, low-risk content — and even then it is subject to spot-audit.

### 6.7 Agent contract (structured I/O)

The judge is constrained to structured output and a narrow remit. (Straight quotes — schema.)

**Input**
```json
{
  "source_segment": "…",
  "target_segment": "…",
  "content_type": "SmPC",
  "risk_tier": 0,
  "metric_profile_version": "smpc@3.2",
  "grounding": {
    "termbase_matches": [ … ],
    "approved_PI_refs": [ … ],
    "qrd_standard_phrases": [ … ],
    "regulatory_rules": [ … ]
  },
  "reference_translation": null
}
```

**Output** — an array of annotation objects matching §5.7, plus a per-segment confidence. The judge **must**: classify each error by dimension + subtype + severity from the fixed typology; cite `rule_ref`/`evidence_refs`; provide a `suggested_fix`. The judge **must not**: rewrite the whole segment; invent terminology not in grounding; change severity rubric; emit free-form prose outside the schema.

### 6.8 Grounding (RAG)

The judge retrieves and **must cite**: approved termbase entries, MedDRA, QRD standard phrases, approved prior product information, and the active regulatory rule set. If retrieval returns nothing for a term the judge believes is governed, it **flags and escalates** rather than guessing — a retrieval miss is a signal, not a licence to improvise. Every citation is stored in `evidence_refs` so the reviewer sees the basis for each call.

### 6.9 Human-in-the-loop interaction

- The reviewer sees **flagged spans first**, each with: the source, the target, the dimension/severity, the cited evidence, and the suggested fix. The reviewer's job is adjudication, not re-reading the whole document.
- For each annotation the reviewer **confirms, overrides, or amends**; the decision is captured against the version as a Part-11 signature.
- Reviewer decisions are the **gold signal**: confirms validate the judge; overrides are labelled training/calibration data (§6.10). The system thanks no one and nudges no one — it captures the decision and moves on.

### 6.10 Evaluating the judge itself (meta-eval & drift)

The judge is a model; it must be measured like one.

- **Judge↔human agreement** tracked continuously using the human decisions in §6.9 — both score-level correlation and span-level agreement (Cohen's/Fleiss' κ, target **κ ≥ 0.80**, consistent with the annotation discipline used elsewhere in your clinical-extraction work).
- **Planted-defect recall & precision** as a CI gate.
- **Drift detection:** alert when agreement, recall or precision regress beyond control limits over a rolling window; a regression **blocks release** (E13.S2).
- **Calibration loop:** systematic over-/under-flagging is corrected by recalibrating the judge prompt/thresholds against the growing gold set, then shadow-tested before adoption.

### 6.11 Judge failure modes & mitigations

| Failure mode | Mitigation |
| --- | --- |
| Leniency / sycophancy drift (passes things it shouldn't) | Independence (§6.2); planted-defect recall gate; spot-audit of passes |
| Self-preference (favours same-lineage output) | Cross-lineage judging; reviser separate from judge |
| Over-flagging (false positives erode trust) | Precision tracking; calibration; severity rubric |
| Reward-hacking the loop (polishing to a hollow pass) | Capped iterations; conservation constraint; human escalation on no-pass |
| Position/verbosity/ordering bias | Structured output; randomised presentation in eval |
| RAG miss → improvisation | Mandatory citation; missing-rule → escalate |
| Unstable short-doc judgements | SQC floor + forced human review |

---

## 7. Eval & golden-dataset strategy (summary)

The eval harness (E13) is the meta-capability that makes everything above trustworthy and transferable.

- **Golden datasets per content type**, with human-MQM gold annotations, versioned, with measured inter-annotator agreement (κ ≥ 0.80) following a documented annotation SOP.
- **Layered evals:** translation quality (terminology adherence, document coherence), judge reliability (agreement, planted-defect recall/precision), end-to-end workflow (cycle time, first-pass pass rate), and regression.
- **CI gates** that block release on regression of judge reliability or planted-defect recall — the automated expression of *no vacuous green*.
- **Everything versioned and documented** so the client GCC inherits a working eval regime at transfer, not just a codebase.

---

## 8. Open decisions (ADR candidates for the build team)

1. **Judge model strategy** — single strong judge with strict independence vs. always-ensemble. Recommendation: ensemble for Tier-0/1, single judge for Tier-2/3, revisit on meta-eval data.
2. **Reviser placement** — agentic reviser vs. deterministic rule-based fixes for the deterministic classes (standard phrases, units). Recommendation: deterministic for those classes, agentic only for genuinely linguistic fixes.
3. **Sample-size floor** for SQC (proposed 500 words) — calibrate against real document-length distributions per content type.
4. **Calibration cadence** — how often to recalibrate the judge against the gold set, and the shadow-test bar before adoption.
5. **Max-iterations** per tier — proposed 2–3 for Tier-0/1; validate that more iterations do not just manufacture hollow passes.
6. **Where determinism ends** — formalise the boundary between deterministic checks and generative latitude as a published rule.

## 9. Glossary

- **APT / PWPT / NPT** — Absolute / Per-Word / Normed Penalty Total (MQM scoring intermediates).
- **APP** — Acceptable Penalty Points per Reference Word Count (the tolerance that defines the threshold).
- **CQS / RQS** — Calibrated / Raw Quality Score.
- **ETW / SPM** — Error-Type Weight / Severity Penalty Multiplier.
- **EWC / RWC** — Evaluation / Reference Word Count (RWC fixed at 1,000).
- **ICF** — Informed Consent Form. **PIL** — Patient Information Leaflet. **SmPC** — Summary of Product Characteristics.
- **MQM** — Multidimensional Quality Metrics. **QRD** — EMA Quality Review of Documents (templates/standard phrases).
- **PRO/COA** — Patient-Reported Outcome / Clinical Outcome Assessment. **PV** — Pharmacovigilance.
- **QE** — Quality Estimation (reference-free quality prediction).
- **SQC** — Statistical Quality Control. **TM** — Translation Memory.
- **BOT** — Build–Operate–Transfer. **GCC** — Global Capability Centre. **LangOps** — Language Operations.

---

*v0.1 — prepared as the build-team reference. Scoring formulas conform to the MQM 2.0 scoring model (MQM Council, 2024). Weights, thresholds and tolerances are starting proposals to be calibrated against gold data before go-live. Regulatory posture (EMA reflection paper, draft EU GMP Annex 22, FDA draft AI guidance) is tracked in the companion research report and should be re-checked at each phase gate, as several texts are draft and in flux.*
