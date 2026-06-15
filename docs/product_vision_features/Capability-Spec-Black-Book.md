# Capability Spec — The Black Book
## The negative-and-decision knowledge layer

**Audience:** product, applied-science, LangOps and regulatory/quality leads.
**Status:** v0.1 — build-ready specification.
**Placement:** expands epic **E2 (Terminology & Knowledge)** in the master reference; consumed by the critique agent (E5), compliance agent (E6), and terminology agent (E2); governed under audit/validation (E8); measured by the eval harness (E13).
**Companion:** *Agentic LangOps — Product Vision, Strategic Backlog, and Detailed Design (MQM + Critique).*

---

## 1. What a “black book” is (and what we mean by it)

“Black book” is not a standardised localisation term. In general English it means *a book containing a blacklist* — a record of things or people out of favour. In localisation practice it is used informally for one, or a blend, of:

- a **banned-terms / forbidden-renderings** list (the negative counterpart to a glossary);
- a **Do-Not-Translate (DNT)** list (strings that must remain in the source language);
- an account **“bible”** — the canonical reference combining style guide, glossary, prohibitions and prior decisions;
- a **known-error / lessons-learned** log.

Because the term is loose, we define it precisely for this platform and use that definition consistently:

> **The Black Book is the platform’s governed, agent-consumable record of what must *not* be done and what has already been *decided*** — prohibitions, do-not-translate rules, known-error patterns, and adjudicated rulings — scoped to an organisation, brand, account, locale and content type.

It is the institutional memory of *constraints*. Incumbent tools model the positive knowledge well (memory, glossary, style guide) and leave the negative-and-decision knowledge scattered across reviewer comments, emails and individual experience. Capturing it as a first-class asset is both a differentiator and a direct expression of the platform principles: prohibitions are how *no vacuous green* is enforced in domain terms, and curated rulings are how institutional learning survives staff turnover and BOT transfer.

## 2. Where it sits — the asset map

The Black Book is one of four knowledge assets, each answering a different question. Keeping them distinct prevents the muddle that makes glossaries unmaintainable.

| Asset | Question it answers | Polarity |
| --- | --- | --- |
| **Translation memory (TM)** | How have we translated this before? | Example (descriptive) |
| **Termbase / glossary** | Which term is approved here? | Positive (“use this”) |
| **Style guide** | How do we write in this voice/register? | Guidance |
| **Black Book** | What must we never do, and what was already decided? | **Negative + adjudicated** |

The Black Book does not duplicate the termbase. The termbase says “use *zweimal täglich*”; the Black Book says “never render *twice daily* as *einmal täglich*, and here is the ruling and why.” Where the two appear to overlap, the Black Book holds the *prohibition*, the *disambiguation* and the *provenance of the decision*.

## 3. Entry taxonomy

Every Black Book entry is one of the following types. The type drives how the entry is matched and enforced.

| Type | Purpose | Example |
| --- | --- | --- |
| **Forbidden rendering** | A target rendering that must never be used | “Never translate *adverse event* as *…*; use the adjudicated term” |
| **Do-Not-Translate (DNT)** | Source string that must remain untranslated | Brand/product names, trademarks, legal entity names, certain codes/units |
| **Disambiguation rule** | Forces the correct sense where a term is ambiguous | “*Administration* = drug administration, not the company department” |
| **Locale prohibition** | A formatting or cultural choice never permitted in a market | Decimal point in a dose table where the locale mandates a comma |
| **Known-error pattern** | A recurring MT/LLM failure mode with its correction | Negation flips on contraindication sentences in a given language pair |
| **Adjudication / decision record** | A past reviewer ruling, with provenance and effective dates | “For this client, this concept is rendered thus — ruling ref, date” |
| **Regulatory prohibition** | A phrasing that causes rejection or breaches a code | Deviation from a QRD standard phrase; non-compliant promotional claim |

Adjudication records are what make the Black Book more than a blacklist. They carry the *reasoning* and *authority* behind a constraint, which is what a reviewer and an auditor need, and what a new GCC team inherits at transfer.

## 4. Data model

Each entry is a governed, versioned object. (Straight quotes — this is a schema.)

```json
{
  "entry_id": "uuid",
  "type": "forbidden_rendering",
  "scope": {
    "org": "client-x",
    "brand": "product-y",
    "account": null,
    "locale": "de-DE",
    "content_type": ["SmPC", "PIL"]
  },
  "matcher": {
    "kind": "semantic",                  // exact | regex | semantic
    "source_pattern": "twice daily",
    "target_pattern": "einmal täglich",  // the prohibited form, where applicable
    "confidence_floor": 0.85             // required for semantic matches
  },
  "prohibited_form": "einmal täglich",
  "prescribed_alternative": "zweimal täglich",
  "reason": "Frequency altered; dosing-fidelity violation.",
  "severity": "Critical",                // maps to MQM severity; Critical → auto-fail
  "maps_to": { "dimension": "Accuracy", "subtype": "Mistranslation", "rule_ref": "DOSING-FIDELITY" },
  "source": {
    "origin": "reviewer_override",       // reviewer_override | adjudication | regulation | import | agent_proposed
    "decision_ref": "review:2024-06-12#sig-naoki",
    "authority": "lead-linguist-de"
  },
  "status": "active",                    // proposed | active | deprecated
  "effective_from": "2024-06-13",
  "effective_to": null,
  "supersedes": null,
  "evidence_refs": ["approved_PI:2024-06#sec4.2", "qrd:v10.4#dosing"],
  "provenance": { "created_by": "...", "approved_by": "...", "version": 3 },
  "telemetry": { "hits": 0, "false_positives": 0, "last_fired": null }
}
```

Design notes:
- **Three matcher kinds.** *Exact* and *regex* for deterministic strings (DNT, standard phrases, units); *semantic* for concept-level prohibitions an LLM judge detects. Semantic matches carry a `confidence_floor` and **escalate rather than auto-block** below it — *no vacuous green* applied to detection.
- **`severity` and `maps_to` wire the Black Book into the MQM engine.** A Critical entry that fires produces a Critical MQM annotation and therefore an auto-fail; the annotation cites the `entry_id` so the reviewer sees the rule and its authority.
- **`telemetry`** is what makes curation *through the system* possible (§8, §10).
- **Deprecation, not deletion.** Entries are superseded and effective-dated; the trail is immutable for audit.

## 5. Scope and inheritance

Entries resolve through a scope hierarchy with inheritance and override:

```
org  →  therapeutic area / brand  →  account  →  locale  →  content-type
```

A locale-specific prohibition overrides a broader one; a more specific scope wins. Resolution is deterministic and logged, so a reviewer can always see *which* entry fired and *why it applied here*. Conflicts (two active entries that contradict, or an entry that contradicts the termbase) are **detected and surfaced to a curator**, never silently resolved.

## 6. How agents consume and enforce it

1. The **terminology, critique and compliance agents** retrieve in-scope Black Book entries via RAG for the segment under evaluation.
2. **Deterministic matchers (exact/regex)** run as hard checks — DNT strings, units, standard phrases.
3. **Semantic matchers** are evaluated by the critique-agent judge; a match above the confidence floor produces an MQM annotation at the entry’s severity, citing the `entry_id`.
4. **Critical entries** that fire trigger the engine’s Critical auto-fail and block sign-off.
5. **Every firing is logged** with the entry version and the evidence, so enforcement is traceable and the entry’s telemetry updates.

Enforcement never improvises: if an agent suspects a governed prohibition but finds no entry, it flags and escalates rather than inventing a rule (consistent with the grounding policy in the critique-agent spec).

## 7. Setting it up for an organisation (bootstrapping)

A Black Book that starts empty stays empty. Setup seeds it from what the organisation already knows, then validates before activation.

1. **Import legacy assets** — existing banned-terms and DNT lists, QA logs, style-guide prohibitions, reviewer comment history.
2. **Mine institutional memory** — extract recurring corrections from TM/edit history and, once live, from the platform’s own reviewer-override stream (the richest source).
3. **Seed regulatory baselines** — QRD don’ts, MDR/IVDR language obligations, local promotional codes; for banking/legal, the equivalent prohibited-disclosure and terms-of-art sets.
4. **Set scope** — assign each seeded entry to the right level of the hierarchy.
5. **Validate before activation** — no imported or mined entry goes `active` without curator approval. Unverified prohibitions sit at `proposed`. This avoids polluting enforcement with noise on day one.

Bootstrapping is a one-off project per organisation; the steady state is the curation loop in §8.

## 8. Curation lifecycle — keeping it alive *through* the system

This is the heart of the capability. A Black Book is only as good as its curation, and manual curation rots. The platform makes curation a by-product of normal operation.

```
   CAPTURE ─▶ CURATE ─▶ GOVERN ─▶ CONSUME ─▶ MEASURE ─┐
      ▲                                                │
      └──────────────  CLOSE THE LOOP  ◀───────────────┘
```

1. **Capture (mostly automatic).** Every reviewer override and adjudication (the human decisions captured in the critique workflow) becomes a *candidate* Black Book entry. The critique agent additionally **proposes** entries when it detects a recurring error pattern across documents. Candidates land at `proposed`.
2. **Curate (human, lightweight).** A locale curator reviews candidates: promote, merge with an existing entry, adjust scope/severity, or reject. The system pre-fills the entry from the captured decision, so curation is adjudication, not authoring from scratch.
3. **Govern.** Promotion is change-controlled: versioned, effective-dated, approved, conflict-checked against the termbase and other entries. Deprecation supersedes rather than deletes.
4. **Consume.** Active entries are enforced by the agents (§6); firings update telemetry.
5. **Measure.** The platform reports per-entry hit rate, false-positive rate (reviewer dismisses the flag), and staleness (never fires / superseded). Curators prune dead entries, tighten over-firing ones, and recalibrate semantic confidence floors. This is the “curated *through* the system” part — the platform tells the curator which entries are earning their place.
6. **Close the loop.** Any **Critical escape** (a Critical error found *after* sign-off) triggers a **mandatory** Black Book entry, so the same escape cannot recur. This converts every failure into institutional learning and is the single most important habit for protecting the franchise.

## 9. Roles and RACI

| Activity | Owner (A) | Responsible (R) | Consulted (C) | Informed (I) |
| --- | --- | --- | --- | --- |
| Black Book governance & policy | LangOps lead | LangOps lead | Regulatory/Quality | Build team |
| Per-locale curation | LangOps lead | Lead linguist (locale) | Regulatory affiliate | Reviewers |
| Candidate capture | Platform (automatic) | Critique agent / reviewers | — | Curators |
| Conflict resolution | LangOps lead | Lead linguist | Termbase owner | — |
| Escape → mandatory entry | Quality lead | Lead linguist | Regulatory | LangOps lead |

Contributors are, in effect, *every reviewer*, because their overrides feed capture. The deliberate design point is that contributing to the Black Book costs a reviewer nothing extra — it is the same signed decision they were already making.

## 10. Curation metrics

Tracked per entry and per scope, surfaced on the LangOps dashboard (E11):
- **Hit rate** — firings per 1,000 words; identifies entries that earn their place vs. dead weight.
- **False-positive rate** — share of firings a reviewer dismisses; high FP means over-broad matcher or wrong severity.
- **Staleness** — time since last fired; candidates for deprecation review.
- **Escape-derived ratio** — share of entries created from Critical escapes; a falling ratio over time is evidence the loop is working.
- **Semantic-match precision** — for `semantic` entries, judge precision against reviewer decisions; drives confidence-floor recalibration.

## 11. Governance, versioning, audit

- Entries are **versioned, change-controlled artefacts** in the validation registry (E8.S2), like prompts and termbases.
- Promotion and deprecation are **approved actions** with electronic signatures (Part 11), bound to user, version and timestamp.
- The **firing log is immutable** and reconstructable: for any output, an auditor can see which entries applied, at which versions, and what the reviewer decided.
- Effective-dating means a re-run of a historical document uses the entries that were active *then*, not now.

## 12. Cross-industry analogies

The machinery is industry-neutral; only the content of the entries changes.
- **Banking / financial services** — prohibited disclosures and financial-promotion phrasings, banned claim language, DNT for legal entity and product names, jurisdiction-specific don’ts (e.g. KID/PRIIPs, MiFID II comms).
- **Legal** — forbidden renderings of terms of art, jurisdiction-specific prohibitions, certified-translation constraints, DNT for cited authorities and party names.

In each case the Black Book is the same negative-and-decision layer, seeded from that industry’s regulatory baselines and curated through the same loop.

## 13. Backlog (slots under E2)

- **E2.S4** Black Book data model and scope/inheritance resolution. *AC:* deterministic, logged resolution; conflict detection against termbase and other entries.
- **E2.S5** Three matcher kinds (exact, regex, semantic) with confidence-floor escalation for semantic. *AC:* deterministic matchers are hard checks; semantic matches below floor escalate, never auto-block. *Principle:* no vacuous green.
- **E2.S6** Enforcement wiring: firings produce MQM annotations citing `entry_id`; Critical entries trigger auto-fail. *AC:* reviewer sees rule + authority for every firing.
- **E2.S7** Bootstrapping importer + memory miner with `proposed`-state quarantine. *AC:* nothing activates without curator approval.
- **E2.S8** Curation loop: automatic candidate capture from overrides and agent proposals; curator promote/merge/reject UI. *AC:* candidates pre-filled from captured decisions.
- **E2.S9** Curation telemetry (hit rate, FP rate, staleness, semantic precision) on the dashboard. *AC:* metrics reconcile to the firing log.
- **E2.S10** Close-the-loop rule: Critical escapes create mandatory entries. *AC:* a Critical escape cannot be closed without a Black Book entry being created or explicitly waived with sign-off.

## 14. Open decisions (ADR candidates)

1. **Semantic matcher implementation** — embedding similarity vs. dedicated judge prompt vs. both; and how confidence floors are calibrated per locale.
2. **Candidate-capture threshold** — how many overrides of the same pattern auto-propose an entry (avoid flooding curators).
3. **Black Book vs termbase boundary** — formal rule for which artefact owns a given constraint, to prevent drift and duplication.
4. **Inheritance override semantics** — confirm “most specific scope wins” covers all real conflict cases, or whether explicit priority is needed.
5. **Waiver policy** — when a Critical escape may be closed *without* a new entry, and who may sign that waiver.

## 15. Glossary delta

- **Black Book** — the platform’s governed negative-and-decision knowledge layer (this document’s definition).
- **DNT** — Do-Not-Translate; a source string kept untranslated by rule.
- **Candidate / proposed entry** — a captured constraint awaiting curator approval before it can be enforced.
- **Escape** — a Critical error found after sign-off; triggers a mandatory Black Book entry.
- **Firing** — a Black Book entry matching content during evaluation.
- **Matcher** — the detection mechanism for an entry (exact, regex, or semantic).

---

*v0.1 — build-ready. The Black Book complements, and does not duplicate, translation memory, termbase and style guide. Severities map to the MQM model in the companion design; Critical entries inherit the Critical auto-fail rule. Weights, thresholds and confidence floors are starting proposals to be calibrated against gold data before go-live.*
