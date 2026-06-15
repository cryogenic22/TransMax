# MQM / Vision Delivery Backlog — the whole list to the end

**Status:** v1.0 — 2026-06-15. The complete, sequenced loop backlog from the current state to full delivery of the vision (`VISION-GAP-ANALYSIS-AND-ROADMAP.md`). Canonical companion to `.context/active_tasks.md` (the live board) and `PHASE-1-KEYSTONE-BUILD-PLAN.md` + ADR-0007.

**Branch:** `feat/mqm-keystone` (PR #14). Everything below `[Done]` is on that branch; the rest is the road ahead. Discipline: 8-stage loop + 3 gates, reuse-and-reconcile (strangler-fig), reversibility-tagged, per-tenant flags, never stage `transmax.db`.

Legend: `[Done]` shipped · `[Next-10]` the immediate resume batch · `[Gated]` blocked on a human decision · `[ ]` queued.

---

## Phase 1 — Keystone (annotation → engine → judge)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-MQM-1 | MqmAnnotation §5.7 + taxonomy reconcile (NEUTRAL, 7 dims, SPM, bridge) | — | one-way | **[Done]** |
| TMX-MQM-2 | Versioned content-type metric-profile registry + 5 profiles | — | two-way | **[Done]** |
| TMX-MQM-3 | Pure MQM-2.0 engine + shadow harness | 1,2 | one-way | **[Done]** |
| TMX-MQM-5c | content-type → metric-profile resolution (reconcile profile forks) | 2 | two-way | **[Done]** |
| TMX-MQM-5a / 5a-emit | engine shadow in gate node + emit diff to v2 chain | 3 | two-way | **[Done]** |
| TMX-MQM-4 | Independent judge in shadow (model-agnostic; §5.7 prompt) | 1,3 | two-way | **[Done]** |
| TMX-MQM-6 | Ensemble + conservation pure helpers | 1 | two-way | **[Done]** |
| TMX-MQM-CAPTURE | Reviewer override → learning bridge (gold) | — | two-way | **[Done]** |
| **TMX-MQM-1a** | Persist `mqm_annotations` table + Alembic + save helper | 1 | one-way | **[Next-10]** |
| **TMX-MQM-6-wire** | Wire conservation diff-reject + ensemble into the live reviser | 6 | two-way | **[Next-10]** |
| TMX-MQM-ENSEMBLE-RUN | Ensemble runner for Tier-0/1 (2+ judges, most-severe, escalate) | 4,6 | two-way | **[Done]** (shadow; default-off; inter-judge κ) |
| TMX-MQM-5c-deepen | Per-segment content-type detection (beyond doc metadata) | 5c | two-way | [ ] |
| TMX-MQM-5b | **Verdict CUTOVER** — engine sole decider, strip self-cert, gates→annotators, ConfidenceService→adapter, unify SDK fork | shadow review | one-way | **[Gated]** (review `scripts/mqm_shadow_report.py` first) |
| TMX-MQM-4b | Judge moves shadow→verdict (after cutover) | 5b | one-way | [ ] |

## Phase 0 — Stop the vacuous green (honesty)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-BB-STRICT | `is_strict` locked rules enforce/block | — | two-way | **[Done]** |
| TMX-AUTH-AUDIT | Structured ACCESS_CHANGE audit on role updates | — | two-way | **[Done]** |
| TMX-DASH-JUDGE-LABEL | Dashboard stops mislabelling the gate as "Reviewer agent" | — | two-way | **[Done]** |
| TMX-ORCH-CHECKPOINT (Loop A) | Stuck-PROCESSING sweeper (no orphaned jobs, A8) — Document+Segment activity anchor | — | two-way | **[Done]** (default-OFF; Loop B checkpointer deferred, one-way) |
| **TMX-AUTH-AUDIT-CHAIN** | Job-less immutable audit trail (system-level chain) for access/config changes | — | one-way | **[Next-10]** |
| **TMX-LOGIN-AUDIT** | Audit login/register/refresh/SSO (extend AUTH-AUDIT) | AUTH-AUDIT-CHAIN | two-way | **[Next-10]** |
| TMX-SSOT-TIER (steps 1-3) | Fix the dead metadata funnel + tier→MetricProfile refinement + unify the governance rule | — | two-way | **[Done]** (step 4 dead-field removal deferred, one-way) |
| TMX-OIDC-CSRF | Verify OIDC `state` on callback (CSRF gap, A12) | — | two-way | [ ] |
| TMX-RBAC-SWEEP | Apply `require_permission` uniformly across all routers | — | two-way | [ ] |

## Phase 2 — Judge reliability / no vacuous green (E13)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-MQM-EVAL | Judge-reliability metric (recall/precision) | 4 | two-way | **[Done]** |
| TMX-MQM-EVAL-CASES | Planted-defect judge gold set + recall gate | EVAL | two-way | **[Done]** |
| TMX-MQM-EVAL-CI | Wire recall/precision into a release-BLOCKING CI gate (regression blocks) | EVAL | two-way | **[Done]** (structure + judge tiers; recall≥0.75/precision≥0.5) |
| TMX-MQM-EVAL-KAPPA | Cohen's κ primitive + durable per-segment judge labels | CAPTURE,4 | two-way | **[Done]** (κ primitive; judge↔human join → TMX-MQM-EVAL-KAPPA-JOIN, needs MQM-1a) |
| TMX-MQM-EVAL-KAPPA-JOIN | Judge↔human κ ≥ 0.80 over CAPTURE gold (needs structured human MQM labels) | EVAL-KAPPA, MQM-1a | two-way | [ ] |
| TMX-MQM-EVAL-DRIFT | Drift detection on agreement/recall/precision (rolling window blocks release) | EVAL-CI | two-way | [ ] |
| TMX-MQM-EVAL-GOLD | Golden datasets per content type w/ human-MQM gold + measured IAA | EVAL-KAPPA | two-way | [ ] |
| TMX-MQM-CALIBRATE | Calibration loop (recalibrate judge prompt/thresholds, shadow-test before adopt) | EVAL-GOLD | two-way | [ ] |

## Phase 3 — Governed knowledge layer (Black Book + 5 stores) (E2/E14)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-ENF-LEVELS | Enforcement levels suggested/preferred/required/locked (generalise BB-STRICT) | — | two-way | [ ] |
| TMX-BB-1 | Refactor TranslationRule → negative+adjudicated Black Book (7 entry types, schema) | — | one-way | [ ] |
| TMX-BB-2 | 3 matcher kinds (exact/regex/semantic + confidence-floor escalation) | BB-1 | two-way | [ ] |
| TMX-BB-3 | Scope hierarchy (org→brand→account→locale→content-type) + most-specific-wins + conflict surfacing | BB-1 | two-way | [ ] |
| TMX-BB-4 | Black Book firing → MQM annotation citing entry_id (severity/maps_to) | BB-1, MQM-3 | two-way | [ ] |
| TMX-BB-5 | Curation loop: curator promote/merge/reject UI + telemetry (hit/FP/staleness/escape/semantic-precision) | BB-1 | two-way | [ ] |
| TMX-BB-6 | Close-the-loop: Critical escape → mandatory Black Book entry | BB-1 | two-way | [ ] |
| TMX-NOM-1 | Nomenclature store (substance↔INN↔per-market↔brand graph) | — | one-way | [ ] |
| TMX-NOM-2 | Confusables (look-alike/sound-alike) graph + checks | NOM-1 | two-way | [ ] |
| TMX-STYLE-1 | Governed Style-guide store | — | one-way | [ ] |
| TMX-TM-UNIFY | Unify the two TM tables (TMSegment vs TranslationMemory) | — | one-way | [ ] |
| TMX-PRECEDENCE | Precedence engine (BlackBook→Nomenclature→Termbase→TM→Style; conflicts surfaced; store-of-origin logged) | BB-1,NOM-1,STYLE-1 | one-way | [ ] |

## Phase 4 — Risk-tier routing + Part-11 + compliance (E6/E7/E9)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-QRD-WIRE | Resolve a regulatory_profiles key → check_segment so QRD/date checks fire (flag-gated, exercisable via optional `regulatory_profile`) | 5c | two-way | **[Done]** (`enable_qrd_checks` default-OFF) |
| TMX-TIER-1 | Content-derived Tier 0-3 engine (from content type/section/signals) | 5c | one-way | [ ] |
| TMX-TIER-2 | Tier drives evaluation depth (100% vs sampled) + gate selection + model strength | TIER-1 | two-way | [ ] |
| TMX-TIER-3 | Tier drives human-review routing (Tier-0 mandatory signed; forced review on insufficient-sample) | TIER-1 | two-way | [ ] |
| TMX-ESIG-1 | Part-11 e-signature primitive (user+version+timestamp+meaning, immutable, in v2) | AUDIT-V2 | one-way | [ ] |
| TMX-ESIG-2 | Sign-and-save reviewer flow + 2FA + signature manifest PDF | ESIG-1 | two-way | [ ] |
| TMX-COCKPIT-1 | Reconcile the two reviewer surfaces into one cockpit | — | two-way | [ ] |
| TMX-COCKPIT-2 | Flagged-spans-first + back-translation column + per-span confirm/override/amend | COCKPIT-1, MQM-1a | two-way | [ ] |
| TMX-QRD-1 | Real QRD structure checker (document-level, missing-heading, blocks sign-off) | QRD-WIRE | two-way | [ ] |
| TMX-QRD-2 | Standard-phrase fidelity (paraphrase of approved phrase → Critical) | QRD-1 | two-way | [ ] |
| TMX-MDR-1 | MDR/IVDR language-matrix enforcement (per-market mandatory languages, missing-language gate) | — | two-way | [ ] |
| TMX-READ-1 | Readability heuristics for PILs | — | two-way | [ ] |
| TMX-CLAIM-1 | Claim↔reference linkage for promo | — | two-way | [ ] |
| TMX-QUERY-1 | Query/clarification threads in the audit trail (E7.S3) | AUDIT-V2 | two-way | [ ] |

## Phase 5 — Put it in force / substrate finish (E1/E8/E10/E11/E12)

| Ticket | Scope | Depends | Rev | Status |
|---|---|---|---|---|
| TMX-VAL-REG | Validation & change-control registry (validated-status gating + 1-action rollback: models/prompts/rules/termbases/profiles) | — | one-way | [ ] |
| TMX-AUDIT-V2-CUTOVER | Emit human decisions + retrievals to v2; retire v1 (finish TMX-3110 phases) | — | one-way | [ ] |
| TMX-ANCHOR-SCHED | Schedule the daily Merkle anchor + wire S3 Object Lock | — | two-way | [ ] |
| TMX-REGPACK-REAL | Real GAMP-5 evidence from executed tests (pytest→OQ, eval→PQ, PDF, signatures) | AUDIT-V2 | two-way | [ ] |
| TMX-PRIVATE-MODEL | EU-resident / private model path (Azure OpenAI EU or self-hosted) + data_region + egress boundary | — | one-way | [ ] |
| TMX-XLIFF | XLIFF 2.1 canonical layer (ingest/export round-trip) | — | one-way | [ ] |
| TMX-STRUCT-TREE | Queryable hierarchical structure tree (promote the IR to the persisted model) | — | one-way | [ ] |
| TMX-STABLE-IDS | Content-addressed stable segment IDs (A5; TMX-3803) | — | one-way | [ ] |
| TMX-NONXLATE-LOCK | Non-translatable detect-and-lock before translation | — | two-way | [ ] |
| TMX-SECTION-PATH | Per-segment section-path breadcrumb (A6) | — | two-way | [ ] |
| TMX-SEG-CONTEXT | Persist the context window per segment | — | two-way | [ ] |
| TMX-DASH-OUTCOMES | LangOps outcome dashboard (cycle time, first-pass quality, reviewer hours, cost/outcome, Critical-escape, Day-215) reconciled to audit log | — | two-way | [ ] |
| TMX-VEEVA | Veeva Vault (RIM/PromoMats/QualityDocs) connector | — | two-way | [ ] |
| TMX-ECOA-CTMS | eCOA / CTMS / RIM connectors | — | two-way | [ ] |

---

## The next 10 loops (resume batch — ungated, build on shipped work)

1. **TMX-MQM-1a** — `mqm_annotations` table + Alembic + persistence helper
2. **TMX-ORCH-CHECKPOINT** — LangGraph checkpointer + stuck-PROCESSING sweeper
3. **TMX-AUTH-AUDIT-CHAIN** — job-less immutable system-level audit trail
4. **TMX-LOGIN-AUDIT** — audit login/register/refresh/SSO
5. **TMX-SSOT-TIER** — collapse the dead tier vocabularies + tier-blind gate into one
6. **TMX-MQM-EVAL-CI** — recall/precision as a release-blocking CI gate
7. **TMX-MQM-EVAL-KAPPA** — judge↔human κ over the CAPTURE gold signal
8. **TMX-MQM-ENSEMBLE-RUN** — ensemble runner for Tier-0/1 (most-severe + escalate)
9. **TMX-MQM-6-wire** — wire conservation + ensemble into the live reviser
10. **TMX-QRD-WIRE** — make the dead QRD/date checks fire (flag-gated)

**Separately gated (needs Kapil):** TMX-MQM-5b (verdict cutover) — run traffic with `mqm_shadow_enabled` on, then `python -m scripts.mqm_shadow_report`, review `block_agreement_rate` + CQS distribution, then flip `mqm_engine_enabled` per tenant.
