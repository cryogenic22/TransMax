# ADR — Knowledge Architecture for the Language Layer

**Number:** TBD (proposed — assign in repo sequence)
**Status:** Proposed
**Deciders:** product, applied-science, LangOps, regulatory/quality leads
**Placement:** foundational decision for the knowledge layer; governs epics E2 (Terminology & Knowledge), E14 (Nomenclature), the Black Book capability, and the resolution logic in E9 (Orchestration).
**Companions:** *Product Vision, Strategic Backlog, and Detailed Design (MQM + Critique)*; *Capability Spec — The Black Book*; *Capability Spec — Nomenclature*.

---

## Context and problem statement

The platform accumulates several kinds of linguistic knowledge: preferred terms, drug and brand naming, glossaries, locked standard terms, do-not-translate rules, style conventions, past rulings, and prohibitions. Without a placement rule these collapse into one another — a glossary fills with prohibitions, drug names become flat glossary rows, and “use this strictly” gets encoded as a separate store. The result is duplication, drift, and a knowledge base that cannot be curated, audited, or transferred cleanly at BOT.

We need a single, durable rule for **where any piece of linguistic knowledge lives**, so each store has one responsibility, agents can retrieve and apply knowledge with clear precedence, and the whole is governable as one for transfer.

## Decision drivers

- **Maintainability** — each store must have a single, clean responsibility so curation does not rot.
- **Safety and compliance** — naming and locked terms are patient-safety- and rejection-critical; they cannot be diluted in a generic glossary.
- **Curation through the system** — capture, curation and measurement must work per store (see the Black Book spec).
- **Agent-consumability** — clean retrieval and deterministic precedence at translation and critique time.
- **Transferability** — the union must hand over to a client GCC as a coherent, validated asset.

## Decision

**Place knowledge by polarity first, kind second. Enforcement strength is a property, not a place.**

```
Is it a prohibition or a past ruling? ──yes──▶ BLACK BOOK
        │ no  (it is prescriptive — “use this”)
        ▼
What kind of prescriptive knowledge?
  ├─ a drug / substance / brand name resolved by jurisdiction ─▶ NOMENCLATURE  (feeds the termbase)
  ├─ a term or phrase to use ─────────────────────────────────▶ TERMBASE
  ├─ a prior example of how we rendered text ─────────────────▶ TRANSLATION MEMORY
  └─ how to write — voice, register, locale formatting ───────▶ STYLE GUIDE

Then attach an ENFORCEMENT LEVEL to the positive entry:
   suggested | preferred | required | locked
   A “locked” deviation raises an MQM error per the content-type profile.
```

Two corollaries that this ADR makes binding:

1. **The Black Book stays purely negative and adjudicated.** No positive “use this” knowledge enters it. A Black Book firing must always mean “stop”, which only holds if it never carries prescriptive content.
2. **The “bible” is a view, not a store.** The institutional bible is the governed union of the five stores for an account, presented and transferred as one. Nothing is authored *into* the bible.

## The canonical asset map

| Store | Question it answers | Polarity | What lives here | What does **not** live here | Owner |
| --- | --- | --- | --- | --- | --- |
| **Translation memory (TM)** | How did we render this before? | Example | Aligned bitext, fuzzy matches | Approved terms, names, rules | LangOps |
| **Termbase / glossary** | Which term is approved here? | Positive | Approved terms, standard phrases, approved abbreviations, units policy | Drug names (resolved via Nomenclature); prohibitions | Lead linguist |
| **Nomenclature** | What is this substance / drug / brand called *here*? | Positive (specialised) | Substance ↔ INN ↔ per-market approved name ↔ brand ↔ confusables graph | Generic terminology; the negative slice (→ Black Book) | Nomenclature owner / regulatory |
| **Style guide** | How do we write? | Guidance | Voice, register, tone, locale formatting conventions | Terms, names, prohibitions | Lead linguist |
| **Black Book** | What must we never do, and what was decided? | Negative + adjudicated | Forbidden renderings, DNT, known-error patterns, rulings, regulatory prohibitions | Any positive “use this” | LangOps |

## The enforcement-policy model (the property dimension)

Enforcement strength cuts across the positive stores. It is an attribute on an entry, not a separate store. This is the formal home of “once standard terms are translated, they are used strictly as aligned.”

| Level | Meaning | Deviation handling | Typical use |
| --- | --- | --- | --- |
| **suggested** | A hint; the agent may use it | None | Low-confidence fuzzy suggestions |
| **preferred** | Use unless there is a reason | Minor/Major MQM flag | Most termbase entries |
| **required** | Must use | Major MQM flag | Regulated terminology |
| **locked** | Immutable once aligned | Critical or Major auto per content-type profile | QRD standard phrases, approved drug names, aligned standard terms |

A *locked* deviation flows through the same MQM severity model as everything else (see the MQM design): a deviated QRD standard phrase resolves to Critical and triggers auto-fail; a deviated locked drug name resolves to Critical; a deviated preferred term resolves to Major or Minor. One mechanism, graded by the entry’s level and the profile.

## Runtime resolution and precedence

When the translation and critique agents assemble constraints for a segment, the stores compose in a fixed order:

1. **Black Book** — prohibitions and DNT are hard negative gates, checked first.
2. **Nomenclature** — resolve any substance or brand to the market-correct name for the target locale and content type.
3. **Termbase** — apply approved terms; *locked* entries cannot be overridden by anything downstream.
4. **Translation memory** — fuzzy leverage, never overriding a locked term or a resolved name.
5. **Style guide** — voice and locale formatting.

**Conflict handling is explicit, never silent.** A Black Book prohibition always blocks. A contradiction between stores — for example a termbase entry that disagrees with a nomenclature-resolved name — is surfaced to a curator for resolution, logged, and never auto-reconciled. Every resolution decision is recorded so a reviewer can see which store supplied which constraint.

## Worked placement guide

| Item | Store | Enforcement | Notes |
| --- | --- | --- | --- |
| “Most likely” / preferred rendering | Termbase | preferred | TM provides the fuzzy leverage |
| paracetamol vs acetaminophen by market | Nomenclature | locked | “Never use the US name on an en-GB label” → Black Book |
| Glossary | Termbase | varies | The glossary *is* the termbase |
| Aligned standard term, immutable | Termbase | locked | This is the “strict” case |
| QRD standard phrase | Termbase | locked | Plus structural check in the compliance agent |
| Brand name (e.g. a market brand) | Nomenclature (brand layer) | locked / DNT | Kept in source unless a market-substitution rule applies |
| Approved abbreviation | Termbase | required | Expansion policy lives in the style guide |
| Date / number / decimal format | Style guide (locale conventions) | n/a | Maps to the MQM Locale dimension |
| Look-alike/sound-alike confusables | Nomenclature (confusable graph) | n/a | “Never confuse A with B” prohibition → Black Book |
| Past reviewer ruling | Black Book (adjudication) | n/a | Carries provenance and effective dates |

## Anti-patterns (explicitly prohibited)

- **Positive terms in the Black Book.** It becomes a dumping ground and a firing stops meaning “stop”.
- **Drug names as flat glossary rows.** Loses the structure, the authority chain, locale resolution, and the safety relationships; this is a Critical-risk shortcut.
- **Enforcement encoded as separate stores** (a “strict glossary” beside a “soft glossary”). Use the enforcement level on one store instead.
- **Authoring into the “bible”.** The bible is the union view; content has a home store.

## Consequences

**Positive.** Each store is independently curatable and auditable; naming and locked terms are protected from dilution; agent retrieval has clean, deterministic precedence; the union transfers cleanly at BOT.

**Negative / cost.** More stores to build and govern; a precedence/resolution engine is required (E9); conflicts must be surfaced and worked rather than auto-resolved; Nomenclature is a new capability to staff (E14).

**Neutral.** Locale-convention rules (dates, numbers) sit in the style guide for now; whether they warrant a dedicated locale-rules store is an open question.

## Compliance and validation notes

Each store is a versioned, effective-dated, change-controlled artefact in the validation registry (E8). Promotion, deprecation and conflict resolution are signed actions (Part 11). Precedence decisions and store-of-origin for every applied constraint are written to the immutable trail, so any output is reconstructable and any constraint is traceable to its store, version and authority.

## Related backlog

- **E2** — termbase plus the enforcement-level property on entries.
- **E14** — Nomenclature capability (separate spec).
- **Black Book** — E2.S4–S10 (separate spec).
- **E9** — runtime precedence/resolution engine and conflict surfacing.

## Open questions

1. **Locale conventions** — keep date/number/formatting rules in the style guide, or split into a dedicated locale-rules store?
2. **Locked-term vs nomenclature conflict** — define the default when a locked termbase term contradicts a nomenclature-resolved market name (current decision: surface to curator; a default tie-break may still be needed).
3. **Abbreviations** — termbase subset, or their own managed set with an expansion policy?
4. **Excipient naming** (e.g. EU E-numbers) — Nomenclature or termbase?

## Glossary delta

- **Enforcement level** — suggested / preferred / required / locked; a property on a positive entry that grades how a deviation is scored.
- **Precedence** — the fixed order in which stores compose to constrain a segment.
- **Bible (institutional)** — the governed union view across the five stores for an account; a view, not a store.

---

*Proposed. Ratify and assign an ADR number before build. The asset map supersedes the four-asset sketch in the Black Book spec §2 by adding Nomenclature as a fifth (positive, specialised) store.*
