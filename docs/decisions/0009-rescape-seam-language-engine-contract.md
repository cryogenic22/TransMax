# ADR-0009: The reSCApe seam — TransMax is a language engine behind a versioned contract

**Date:** 2026-07-21
**Status:** proposed — requires Kapil's acceptance and reSCApe platform-team acceptance
**Reversibility:** the contract and the client are **two-way** (additive on both sides). The submodule
removal is **two-way**. The locale column on reSCApe's component model is **one-way** and is filed as
reSCApe's own RFC under its Backend Lock.
**Companion:** mirror this ADR into `Scriptiva_SCA/docs/adr/` as their next number so both repos hold
the same decision. Neither copy is authoritative alone.

---

## Context

Two products are in play and their relationship has never been decided in writing.

**reSCApe** (`~\Scriptiva_SCA`) is a structured content authoring platform for pharma
labelling: ~101k lines of API, 2,577 tests, 514 endpoints. It owns `components` /
`component_versions` (stable id, integer versioning, `effective_from`/`effective_to`, a six-state
lifecycle with an enforced transition table and role-gated approvals), market-variant components,
deterministic assembly to a `build_hash`, `LabelSet` scope hierarchy, `DerivedMapping` lineage with
drift and `EquivalenceAttestation`, render to HTML / FHIR ePI / SPL / eCTD, and — significantly —
`signature_records`, a working 21 CFR Part 11 signature model with `manifest_hash`,
`signing_meaning`, actor, roles and authentication context.

**TransMax** owns the language layer: a LangGraph translation pipeline, an MQM 2.0 scoring engine
with versioned content-type metric profiles, an independent judge with planted-defect recall and
Cohen's κ under a CI gate, deterministic language gates (numeric, frequency, negation, terminology),
a prompt registry with content hashes, and a domain-separated chained audit ledger with an
independently re-implemented verifier and Merkle day-anchors.

### The seam that already exists, and why it must change

`packages/transmax` is a **git submodule** of `https://github.com/cryogenic22/TransMax.git`, pinned at
`274557a` — **dated 2026-03-03, the second commit in TransMax's entire history**. Everything that
makes TransMax defensible postdates that pin: audit ledger v2, the verifier, Merkle anchors, the MQM
engine, multi-tenancy, the prompt registry, the injection and budget guards, the drift gate. reSCApe
therefore offers a `"transmax"` provider tier whose pharma-grade quality checks come from a pre-moat
snapshot. The submodule also carries uncommitted local changes, so it is drifting as well as stale.

`apps/api/app/services/transmax_bridge.py` consumes it by **in-process `importlib` against a
filesystem path**, loading `app/services/quality_gate.py` under a mangled `transmax_` namespace
specifically to dodge a collision between the two repos' `app` packages. Six `return None` paths
silently degrade to glossary-deterministic substitution, and semantic similarity falls back to a
token-overlap heuristic — while the response still reports `mode: "transmax_ai"`. That is an unearned
provenance claim, and it is the same defect class as reSCApe's `last_derived_at` advancing without
re-derivation and TransMax's SDK emitting `[target] source` labelled MT.

Critically, **TransMax does not do the translating**. `_run_transmax_pipeline` calls reSCApe's own AI
provider and runs the TransMax quality gate only as post-hoc QC. Its docstring states the reason:
*"the full TransMax LangGraph pipeline requires its own database."* The bridge's author identified the
correct architecture and worked around it.

This violates a rule reSCApe has already accepted. **ADR-0004** (*Headless core + contract seam*,
accepted 2026-07-01) states: *"Every consumer binds to a versioned contract, never to backend
internals."* The TransMax bridge is the clearest violation of that rule in the portfolio. Nothing here
is new policy; this ADR applies existing policy across the repo seam.

### Two further facts that shape the decision

**reSCApe's component model is monolingual.** There is no language or locale column on `components`
or `component_versions`; one language column exists across 23 migrations and it belongs to
carton-label specs. The variant selector branches on market only.
`DerivationType.TRANSLATED_FROM` and `LOCALIZED_FROM` are declared in the enum and written by
nothing. reSCApe's own draft `docs/translation-localization-architecture.md` concedes the workaround:
locale is routed through `market_scope_markets` *"until a dedicated language field exists on
Component."* TransMax is therefore not duplicating reSCApe — it supplies a dimension reSCApe does not
model.

**reSCApe's `audit_log` is not a chained ledger.** It has no `prev_hash` and no sequence column;
rows are individually fingerprinted but unlinked, so deleting or reordering one is undetectable.
TransMax's chain is not a duplicate capability — it is the portfolio's only tamper-evident evidence
plane.

---

## Decision

**TransMax is a deployed service that reSCApe calls over a versioned contract. It is not a package,
not a submodule, and not a module inside reSCApe.** The following ten clauses are the decision.

1. **Retire the submodule.** `packages/transmax` and the `importlib` loader are removed.
   `transmax_bridge.py` is rewritten in place as a thin HTTP client — Backend-Lock-safe, because it
   extends an existing service module rather than adding one.

2. **Ownership is split on a single line: reSCApe owns what a statement *is*; TransMax owns how a
   translation was *produced and adjudicated*.**

   | Concern | Owner |
   |---|---|
   | Component identity, versioning, effective dating, lifecycle, approvals | reSCApe |
   | Market scoping, market-variant components, `LabelSet` scope | reSCApe |
   | Lineage, derivation, drift, equivalence attestation | reSCApe |
   | Assembly, `build_hash`, render (FHIR ePI / SPL / eCTD), submission | reSCApe |
   | Part 11 e-signature | reSCApe |
   | Translation execution | TransMax |
   | Quality adjudication (MQM, judge, deterministic gates) | TransMax |
   | Translation provenance and the tamper-evident chain | TransMax |
   | Language assets: TM, termbase, nomenclature, style, Black Book | TransMax |
   | **Locale as a modelled dimension** | **TransMax (and see clause 7)** |

3. **The contract extends TransMax's existing `app/schemas/api_v1.py`; it is not a new invention.**
   That schema already carries an idempotency key (`request_id`), a governance profile
   (archetype × risk tier × modality × optional regulatory profile) and a `webhook_url` field. What it
   gains: a **source reference block** (`component_id`, `component_version_id`, `hash_canonical`,
   `doc_type`, `market`, `product_ref`, `section_path`), a **constraint block**
   (`termbase_refs` with versions, do-not-translate spans), and a **result block** carrying
   `disposition` (PASS / REVIEW_REQUIRED / BLOCKED), the MQM score with its profile version, the
   provenance record, and `audit.chain_head_hash` with a verification URL. Shape changes go to `v2`
   routes; existing routes stay backwards-compatible.

4. **The translation-memory key is adopted verbatim from reSCApe's draft architecture note:**
   `(source_component_version.hash_canonical, target_locale, termbase_version_id)`. Keying on the
   content hash gives reuse across components; including the termbase version means a terminology
   change invalidates the match automatically. This closes the bind-revalidation hazard in the key
   rather than in a policy someone must remember. A bound segment still runs the deterministic gates;
   binding skips the model, never the checks.

5. **The seam fails closed.** No silent degradation is permitted across the boundary. A missing
   provider, an unavailable engine, an unparseable model response or a low-confidence source-language
   detection returns a typed error or a typed hold — never a glossary-mode substitution, never
   `[target] source`, and never a `mode` value the engine did not earn. Provenance is derived from the
   artefact that produced it (prompt hash, chain entry, match type), never stored as a string and
   never surviving a fallback path.

6. **One engine, no weaker surface.** `transmax_sdk`'s independent pipeline is retired rather than
   hardened; `transmax_mcp` is rewired as a thin wrapper over the same contract. No MCP quality and no
   SDK quality may be weaker than the hosted engine. This closes red-stop RS-01, which is worse than
   the scorecard records — there are four translation paths across two repos, not two.

7. **reSCApe files an RFC for a locale dimension on the component model.** A translated label must
   become a reSCApe component version, or it inherits none of assembly, approval, signature, render or
   submission — and we would rebuild all of it. That requires locale on the component model, in the
   variant selector, and **in the `build_hash`**: today a French and an English label are
   indistinguishable to the build hash. This is the one blocking prerequisite and the one one-way
   change. Until it lands, locale rides in `market_scope_markets` as an explicitly temporary
   workaround, documented as such.

8. **TransMax consumes reSCApe's signatures; it does not build a second signing stack.** A segment
   disposition may carry a signature reference resolved against `signature_records`. TransMax's role
   is to refuse to mark a submission-bound segment lockable without one — the gate lives in the
   engine, the signature lives in reSCApe.

9. **TransMax's chain is the evidence plane for translation events.** reSCApe's `audit_log` records
   the *fact* of a translation job and stores the returned `chain_head_hash`; the verifiable sequence
   lives in TransMax and is provable through its verification endpoint. Neither system reimplements
   the other's evidence model.

10. **TransMax restructures internally into kernel / engine / adapters / contract / surfaces**, so
    that every surface is thin and identical contract tests pass through each. This is the already-
    planned kernel extraction (WS2 / TMX-3220); this ADR fixes its shape and makes the HTTP surface
    its first consumer.

---

## Consequences

**Easier**

- reSCApe stops shipping quality claims backed by a March snapshot, and stops labelling heuristic
  output `transmax_ai`.
- TransMax gains its first real consumer. Fifteen capabilities are currently dark — built, tested,
  merged, called by nothing — because no consumer forces them on. A contract with real content is the
  forcing function that turns them live.
- Validation transfers. A qualified service with its own IQ/OQ/PQ, chain and change control is
  validated once and inherited by every consumer. A module inside reSCApe would have to be
  revalidated by consumer number two from zero.
- Delta-only translation falls out for free: reSCApe already versions components and computes impact
  sets, so TransMax never invents statement identity and never diffs documents.
- Commercial and MLR content becomes a second metric-profile pack rather than a second product. The
  `promo` profile already exists alongside `smpc_pil`, `icf`, `pv` and `pro_coa`.

**Harder**

- Two deploy targets, two release cadences, and a contract that must be versioned and kept
  backwards-compatible. This is real operational cost and it is the price of the validation asset.
- Network latency and partial failure replace an in-process call. Mitigated by the async job +
  callback shape, but it is genuinely more machinery than an import.
- Four things are missing on both sides and must be built: reSCApe has **no webhook receiver**;
  TransMax's `webhook_url` is **accepted and never fired**; reSCApe's translation jobs are an
  **in-memory dict** that dies on restart and TransMax's queue is a **32-line `BackgroundTasks`
  shim**; and reSCApe's API keys **impersonate a human user with full roles**, with no
  service-account principal or scoping.
- Until clause 7 lands, locale is a workaround and must be labelled one everywhere it surfaces.

**Governance**

- reSCApe's Backend Lock (2026-05-17) means a new route module, service module or SQLAlchemy model
  requires an RFC. Clause 1 is lock-safe (rewrites an existing service). Clause 7 is not, and is
  filed as an RFC.
- reSCApe's open `SEC-AGENT-EGRESS` (unguarded outbound POST of credentials and content to an
  operator-supplied URL) must be closed before any outbound call pattern is generalised.
- Both repos run the same harness family — loop-driven-dev, ratchet, quality gate, G3 "no vacuous
  green". Clause 5 is the cross-repo statement of G3.

---

## Alternatives considered

- **Alternative A — keep the submodule and just update the pin.** Cheapest, and it removes the
  staleness but none of the coupling. It binds to `app/services/quality_gate.py`, a module TransMax
  refactors freely and has already scheduled for splitting; every TransMax refactor would silently
  break reSCApe. It also cannot ever run the real pipeline, because that needs its own database.
  Rejected — it fixes the symptom that is easiest to see and none of the ones that matter.

- **Alternative B — move TransMax into reSCApe as a package.** Superficially attractive: one deploy,
  one repo, no network. Rejected on three grounds. A vendored module can run in-process, but a
  regulated engine with its own audit ledger and tenancy cannot — nobody could then answer whose chain
  recorded the translation. It destroys the validation asset, since consumer number two revalidates
  from zero. And it would degrade the portfolio's evidence position, because reSCApe's audit is
  unchained.

- **Alternative C — reSCApe builds its own translation and TransMax is retired.** Rejected. reSCApe's
  translation subsystem is a prototype — an in-memory job dict, ten hardcoded languages, an inline
  French glossary, and zero references to `component_id` in its routes. Rebuilding MQM, the judge, the
  κ gate, the deterministic language packs and the chained ledger inside reSCApe would discard the
  single largest defensibility investment in the portfolio.

- **Alternative D — TransMax stays standalone and reSCApe is not a consumer.** Rejected for now, and
  the reason is diagnostic: TransMax's problem is not missing capability, it is missing consumers.
  Fifteen dark capabilities are dark because nothing calls them. Noted-for-later: the standalone hub
  remains the end state, but it is a surface over a proven engine, not a prerequisite for one.

- **Alternative E — a package/import file-exchange workflow** (reSCApe's own "Workflow B": emit a
  translation package with stable ids, vendor returns keyed units, system creates versions and an
  import receipt). Noted-for-later, not rejected. It is the right shape for a genuine third-party LSP
  and it should remain the fallback path for vendors who cannot integrate. It is the wrong shape for
  our own engine, where a live contract gives per-segment disposition and provenance that a file
  round-trip cannot.

---

## Affected teams / surfaces

**TransMax**
- `app/schemas/api_v1.py` — the contract (clause 3)
- `app/api/v1/translations.py` — durable execution, webhook dispatch (consequence 3)
- `app/services/` — kernel extraction (clause 10); TM key (clause 4)
- `transmax_sdk/` — pipeline retired (clause 6); `transmax_mcp/` rewired
- `.context/active_tasks.md` — supersedes the component-graph and Part 11 e-signature epics proposed
  in `docs/PROGRAM-STATUS-2026-07-21.html` §6–§7; see §8 of that report for the correction

**reSCApe** (`~\Scriptiva_SCA`)
- `.gitmodules`, `packages/transmax` — removed (clause 1)
- `apps/api/app/services/transmax_bridge.py` — rewritten as an HTTP client (clause 1)
- `apps/api/app/services/translation.py`, `services/translation_job.py`,
  `apps/api/app/api/v1/routes/translation.py` — dispatch and job store move behind the client
- `apps/api/app/models/extensions.py` (`TranslationGlossary`), `PHARMA_GLOSSARY_FR` — migrate into
  TransMax's termbase store (clause 2)
- `apps/api/app/models/core.py` — locale column, RFC (clause 7)
- `apps/api/app/services/assembly.py` — locale in the variant selector and `build_hash` (clause 7)
- `packages/contracts/` — the generated client for the seam
- `docs/adr/` — mirror of this ADR
- `delivery/backlog.jsonl` — rows filed in the coordinated quiet window, per their protocol

**Decisions still open** (not settled by this ADR)
1. Does a translated component version require its own approval cycle in reSCApe, or does it inherit
   the source's approval with a linguistic-review addendum?
2. Does the MQM disposition gate reSCApe's transition to `effective`, or only annotate it?
3. Where does nomenclature sit when a market-approved drug name is simultaneously a regulatory fact
   (reSCApe) and a terminology constraint (TransMax)? Current lean: TransMax holds the resolution
   graph, reSCApe holds the approval.
