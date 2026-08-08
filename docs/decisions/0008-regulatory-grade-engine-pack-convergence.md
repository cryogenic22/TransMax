# ADR-0008: Converge the external "Regulatory-Grade Engine Pack" spine-first

**Date:** 2026-07-13
**Status:** accepted

## Context

An external second-opinion review was produced on 2026-07-13 (Codex / "wha" run) at
`~\Documents\Codex\2026-07-13\wha\outputs\`:

- `transmax-regulatory-grade-engine-pack.md` — a "one kernel, four thin surfaces"
  architecture with 11 workstreams (WS0–WS10), first-10 tickets, and 6 leadership decisions.
- `transmax-regulatory-grade-progress.yaml` — a weighted maturity scorecard (WS0–WS10,
  weights summing to 100) with 6 baseline "red stops".

It was reviewed against live code, not taken on trust. Three findings shaped this decision:

1. **The pack converges with, not competes against, our own plan.** Its quality kernel
   (WS6: deterministic hard-controls **+** evidence-generating MQM assessment, with a
   disposition layer that consumes both) is the architecture we already specified in
   ADR-0007 and built in shadow (producer → calculator → decider, K1–K7). Its canonical
   `Finding` schema is our §5.7 `MqmAnnotation`. Its "signed release scorecard that fails
   on missing evidence" is the direct remedy to our own stated #1 liability — the
   "vacuous-green" hazard (`VISION-GAP-ANALYSIS-AND-ROADMAP.md` §3.a). Its "model may
   propose a rule, never activate it" is our Black Book + learning-service posture. Its
   "no unsafe fallback yields a releasable output" is addendum **A3**.

2. **The pack's WS1–WS10 map almost 1:1 onto our v3 epic E11 "Headless Foundation"**
   (`TMX-3220`–`3232`) — which we deliberately **deferred to v3.1** in the "embedded-first
   counter-descope" (`v3_pilot_ready_release_plan.md` Part III §C.3). So the pack is, in
   effect, arguing to reverse that deferral. But the disagreement is narrower than it
   looks: the pack's own timeline also puts the REST/SDK/MCP **surfaces** last (weeks
   14–20). The genuine delta is only that it wants **WS0 (truthful readiness)** +
   **WS1 (one canonical job identity)** + **WS3 (durable operations)** pulled *forward*,
   because the MQM verdict cutover (TMX-MQM-5b) is about to be built on top of them.

3. **All seven of the pack's "material gap" claims were verified TRUE against code.**
   Two are genuine, previously **un-ticketed** hazards:
   - **SDK fail-open (A3 breach):** `transmax_sdk/pipeline/pipeline.py:113` fabricates
     `f"[{target}] {source}"` and labels it `"MT"` when no model is configured;
     `:311` returns `{}` on a parse error (empty translation, status still computed).
     Not reached by the REST app today (the app never imports the SDK), but becomes a
     live regulated-path A3 breach the moment the SDK/MCP ships as a product surface
     (TMX-3227/3228).
   - **v1 non-durable + lossy reconstruction:** `app/api/v1/translations.py:79`
     runs translation via in-process `BackgroundTasks`; `:140` rebuilds output with
     `". ".join(...)`.
   The other five are TRUE but already ticketed / intended-transitional: source-language
   defaults to `en` on low confidence (`graph.py:120-130`, A3-adjacent, was un-ticketed);
   v2 audit best-effort double-write + `doc_id`(str)≠`job_id`(UUID) identity split
   (TMX-3110d / A4); MQM shadow-only + QRD global-off (intended; cutover TMX-MQM-5b);
   default-org middleware + no DB RLS (TMX-3013).

Separately, this repo was found to be the only one of the three sibling repos
(transmax, onto_wiz, setu) **not** running the CtxPack "ctx" deterministic session-memory
ledger that the other two share, and its own CLAUDE.md referenced a `.claude/settings.json`
that did not exist on disk.

## Decision

**Converge the pack spine-first.** Adopt the engine pack as canonical convergence input
(this ADR is its landing point) and:

1. **Map WS0–WS10 onto the existing epic map** (E1–E14 canonical per ADR-0007; E11 headless)
   — table below. No new parallel epic numbering is created; the pack's workstreams are a
   lens over our epics, not a replacement roadmap.
2. **Pull WS0 and WS1 forward, now**, as the connective spine under the in-flight MQM cutover:
   - **WS0** — a signed, reproducible **release scorecard** (`release-scorecard.json`) that
     goes red on missing evidence and can never report READY without proof (kills
     vacuous-green). Ticket **TMX-RELEASE-SCORECARD**.
   - **WS1** — an ADR + migration plan fixing **one canonical job identity** (reconcile the
     graph's string `Document` identity with the v2 UUID `TranslationJob`). This un-defers
     the identity slice of E11 (`TMX-3221`) into the current phase; the rest of E11 stays in v3.1.
3. **Fix the two verified un-ticketed hazards now** (both surgical, two-way): SDK fails closed
   with typed outcomes instead of fabricating/emptying (**TMX-SDK-FAILCLOSED**); v1 stops the
   lossy `". "`-join and moves toward IR-based reconstruction + durable execution
   (**TMX-V1-DURABLE-IR**). Add **TMX-LANGDETECT-HOLD** to turn the source-language `en`
   default into an explicit hold (A3).
4. **Keep the full headless surfaces (WS10) deferred to v3.1** exactly as descoped — this is
   common ground with the pack's own week-14–20 ordering. E11's REST v2 / webhooks / SDK /
   MCP-parity tickets remain in v3.1; only WS1's identity slice is pulled forward.
5. **Adopt the pack's scorecard YAML as a tracked release-gate artifact**, recomputed only
   from attached evidence, with the 6 red-stops as hard blocks that a weighted score can
   never override.
6. **Onboard this repo to the CtxPack "ctx" session-memory harness** (done this session via
   `ctxpack onboard`), reaching parity with onto_wiz/setu and closing the missing-`settings.json`
   hole. The `.context/` program-brain (curated intent) and the `.claude/ctx/` ledger
   (automatic transcript record) are complementary layers, both retained.

The MQM verdict cutover (TMX-MQM-5b) and any WS1 schema migration remain **one-way, Kapil-gated**.

### WS → epic / ticket mapping

| Pack WS | Our home | State |
|---|---|---|
| WS0 Baseline & truthful readiness | VISION-GAP §3.a vacuous-green + Phase-0 honesty + TMX-PRODSAFE-DEPLOY-ENV + TMX-3000 | **pull forward** → TMX-RELEASE-SCORECARD (the signed scorecard artifact we lacked) |
| WS1 Canonical job / identity | TMX-3221 (job state machine) + TMX-3017 (dual-model rationalise) + A4 | **pull forward** — the identity slice of E11; rest stays v3.1 |
| WS2 Kernel extraction (application service) | TMX-3220 Internal Service API extraction (folded into E7) | as-planned |
| WS3 Durable ops (worker/outbox/idempotency) | TMX-ORCH-CHECKPOINT Loop A [Done]; Loop B (checkpointer) + TMX-3222 idempotency | partial; Loop B deferred (one-way) |
| WS4 Policy / knowledge + starter kit | Black Book (E2/E14) + metric profiles (K2) + QRD-WIRE + regulatory_profiles | strong; pack adds signed policy snapshots + expiry |
| WS5 Provenance / provider control | resolution cascade + A6 qualified-supplier + TM | strong; pack adds per-segment provenance record + typed holds |
| WS6 Quality / MQM / disposition | **MQM Keystone K1–K7 / ADR-0007** | **strongest alignment — already built in shadow;** cutover = TMX-MQM-5b |
| WS7 Format fidelity / IR | E4 + parser registry + FidelityGate + TMX-STABLE-IDS | strong substrate; pack adds canonical IR + XLIFF 2.1 boundary |
| WS8 Evidence / CSV | E2 audit v2 + E3 validation pack + TMX-3500 regulatory pack | strong; pack makes v2 mandatory + external anchor |
| WS9 Security / tenancy / ops | E1 + TMX-3013 + RLS-future | partial; pack adds Postgres RLS + OAuth claims |
| WS10 REST / client / webhooks / MCP parity | E11 TMX-3224–3232 | **deferred to v3.1** (common ground) |

## Consequences

**Better.** The MQM cutover we are about to ship stops resting on sand: a canonical job
identity (WS1) and a truthful release scorecard (WS0) become its foundation, so the
"defensible verdict" the whole product sells is backed by one identity lineage and an
evidence gate that cannot lie. Two real A3 hazards close before the SDK/MCP is ever shipped
as a surface. The pack's independent arrival at our own quality architecture is strong
external corroboration of ADR-0007. ctx onboarding means this session's compaction and all
future ones are banked deterministically, matching the sibling repos.

**Worse / cost.** Pulling WS0 + WS1 forward adds work ahead of the cutover rather than after
it — the cutover ships slightly later than an "MQM-5b immediately" path would. WS1 touches
the dual-model identity split (A4), historically the riskiest schema area; its migration is
one-way and Kapil-gated, so it will not be rushed. The pack's full scorecard has 100 weight
points across WS0–WS10; we are only lighting up WS0/WS1/WS6 evidence now, so early scorecard
runs will read honestly low — which is the point (no vacuous green), but must be communicated
as "truthful baseline", not "regression".

**Newly possible.** A single `release-scorecard.json` that any pod, auditor, or the CI gate
can recompute from evidence; a clean seam to un-defer the rest of E11 in v3.1 without a
re-architecture, because WS1 identity is already canonical.

## Alternatives considered

- **Scorecard + hazards only (rejected).** Adopt just the release-scorecard discipline and
  fix the two hazards, leaving identity/kernel/durable-ops in the deferred E11 untouched.
  Rejected because the MQM verdict cutover (TMX-MQM-5b) writes its evidence against the v2
  `TranslationJob` UUID while the graph still identifies work by the string `Document` id —
  cutting over on that split bakes the identity gap into the very audit trail that is
  supposed to be defensible. WS1 is not optional *before* the cutover.
- **Full kernel-first reset (rejected).** Reverse the embedded-first descope entirely:
  do WS0–WS3 (identity + application-service extraction + durable worker/outbox) before
  resuming any MQM work, per the pack's literal 0–6-week ordering. Rejected because it
  discards months of shadow-validated MQM keystone momentum for a big-bang re-platforming,
  and the pack's own value case (the defensible verdict) *is* the MQM kernel — stopping it
  to rebuild plumbing inverts the priority. We take the pack's ordering discipline (spine
  before surfaces) without its "pause everything" sequencing.
- **Retire the SDK pipeline outright now (noted for later).** The pack recommends replacing
  the in-process SDK pipeline with a generated remote client. Correct end-state, but that is
  E11/v3.1 surface work; for now the SDK is made to **fail closed** (TMX-SDK-FAILCLOSED) so
  it is safe as a non-regulated sandbox until the generated-client cutover.

## Affected teams / surfaces

- **Quality & Regulatory / Agent & AI** — WS6 cutover (TMX-MQM-5b), WS1 identity ADR
  (`app/agents/runner.py:31`, `app/models/audit_v2.py:65-67`, `app/models/database.py`
  vs `app/models/translation.py`).
- **Audit & Validation** — WS0 scorecard (`scripts/`, CI), WS8 v2-mandatory (TMX-3110d).
- **Platform & Observability** — ctx harness (`.claude/settings.json`, `.mcp.json`,
  `.claude/ctx/`), WS3 durable ops, deferred E11.
- **Agent & AI** — TMX-SDK-FAILCLOSED (`transmax_sdk/pipeline/pipeline.py`),
  TMX-LANGDETECT-HOLD (`app/agents/graph.py`, `app/services/language_detection.py`).
- **Document Pipeline** — TMX-V1-DURABLE-IR (`app/api/v1/translations.py`).
- Supersedes nothing; extends ADR-0007 (canonical epic map + MQM engine) with the pack's
  spine-first ordering and evidence-scorecard gate.
