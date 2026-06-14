# Capability Spec — Nomenclature
## The drug, substance and brand naming authority

**Audience:** product, applied-science, LangOps, regulatory and pharmacovigilance leads.
**Status:** v0.1 — build-ready specification.
**Placement:** new epic **E14 (Nomenclature & Naming Authority)**; feeds the termbase (E2) at resolution time; consumed by the translation (E3), critique (E5) and compliance (E6) agents; governed under audit/validation (E8); measured by the eval harness (E13). Its negative slice (prohibitions, confusables) is published into the Black Book.
**Companions:** *ADR — Knowledge Architecture for the Language Layer*; *Capability Spec — The Black Book*; *Product Vision, Backlog and MQM/Critique Design*.

---

## 1. Why naming is a first-class capability, not a glossary row

The same molecule carries different approved names in different jurisdictions. The textbook case: the substance whose international nonproprietary name (INN) is **paracetamol** — used in the UK, EU, Australia and India — is approved in the United States under the adopted name **acetaminophen** (also used in Canada and Japan). Other classic divergences include **salbutamol** (INN) / **albuterol** (US), **adrenaline** (INN) / **epinephrine** (US), and **pethidine** (INN) / **meperidine** (US). On top of the nonproprietary names sit market-specific **brand names** (protected trademarks, which launch and withdraw over time), and a set of **look-alike/sound-alike (LASA)** neighbours that must never be confused.

This is a structured, authority-backed, locale-resolved, time-varying graph — and getting it wrong is a Critical error in both senses: patient safety and regulatory rejection. Flattening it into glossary rows discards the structure, the chain of authority, the locale resolution and the safety relationships. Naming therefore gets its own capability, which *feeds* the termbase at resolution time rather than living inside it. The termbase holds approved terms; Nomenclature answers “what is this substance, drug or brand called *here, now, in this context*”.

## 2. Where it sits

Nomenclature is a **positive, specialised** store (per the Knowledge Architecture ADR). It does not duplicate the termbase and it does not hold prohibitions. Its relationship to the other stores:

- **Feeds the termbase** — at resolution time it supplies the market-correct name for a substance or brand; the translation agent never free-translates a drug name.
- **Publishes a negative slice to the Black Book** — derived prohibitions (“never use the US name on an en-GB label”, “never confuse A with B”, “brand X is withdrawn — never reference”) live in the Black Book, generated from the graph, not maintained twice.
- **Maps to MQM** — a name that does not match the resolved approved name is an Accuracy/Terminology error at Critical; a LASA proximity is flagged for review.

## 3. The nomenclature graph (data model)

The store is a graph of substances, names and relationships, every node and edge versioned, effective-dated and provenance-stamped. (Straight quotes — schema.)

```json
{
  "substance_id": "subst:paracetamol",
  "inn": { "name": "paracetamol", "status": "rINN", "authority": "WHO-INN" },
  "identifiers": { "atc": ["N02BE01"], "cas": "103-90-2", "unii": "362O9ITL9D" },
  "monographs": ["PhEur:paracetamol", "USP:acetaminophen"],
  "approved_names": [
    {
      "name": "paracetamol",
      "name_type": "nonproprietary",
      "jurisdictions": ["GB", "EU", "AU", "IN"],
      "locales": ["en-GB", "de-DE", "fr-FR", "..."],
      "source": "INN / BAN-rINN-harmonised",
      "dual_label_with": null,
      "effective_from": "2004-01-01",
      "effective_to": null
    },
    {
      "name": "acetaminophen",
      "name_type": "nonproprietary",
      "jurisdictions": ["US", "CA", "JP"],
      "locales": ["en-US"],
      "source": "USAN",
      "dual_label_with": null,
      "effective_from": null,
      "effective_to": null
    }
  ],
  "brands": [
    {
      "brand": "<market brand>",
      "owner_mah": "<holder>",
      "markets": ["GB"],
      "status": "active",            // active | withdrawn | pre-launch
      "dnt": true,                   // do-not-translate; keep in source unless substitution rule applies
      "effective_from": "...", "effective_to": null
    }
  ],
  "confusables": [
    { "with": "subst:<lasa-neighbour>", "kind": "LASA",
      "guidance": "tall-man lettering", "severity": "Critical" }
  ],
  "provenance": { "created_by": "...", "approved_by": "...", "version": 4 },
  "telemetry": { "resolutions": 0, "name_errors_caught": 0, "confusable_flags": 0 }
}
```

Design notes:
- **Substance is the canonical anchor**, identified by stable external identifiers (INN, ATC, CAS, UNII) so the graph is unambiguous and reconcilable to authority data.
- **Names are edges with jurisdiction, locale, source authority and effective dates** — the same substance resolves to different names by market and by date.
- **`dual_label_with`** captures safety dual-labelling, where two names appear together (the adrenaline/epinephrine and noradrenaline/norepinephrine pairs are the standard examples, retained for patient safety even after BAN→rINN harmonisation).
- **Brands are first-class**, with market, holder, status and a DNT flag; withdrawn brands are retained (effective-dated) so historical documents still resolve.
- **Confusables** carry severity and disambiguation guidance; they are the source of the Black Book “never confuse” prohibitions.

## 4. Authority sources and provenance

Every name traces to an external authority, recorded in `source` and provenance:

- **WHO INN Programme** — proposed and recommended INN lists (the substance-level nonproprietary name).
- **USAN Council / USP** — United States adopted names (the US divergences).
- **National pharmacopoeias** — Ph. Eur. (EDQM), USP-NF, BP, JP — and EDQM Standard Terms.
- **EMA / QRD** — the name forms expected in product information.
- **Brand / trademark registries and the client’s own RIM** — market brand portfolio, launches and withdrawals.
- **ISMP / WHO confused-drug-name lists** — the LASA baseline.

Where authority data is licensed rather than open, sourcing and licensing is an explicit build decision (§15).

## 5. Locale resolution

The core service is a deterministic resolver:

```
resolve(substance_id | brand_id, target_locale, content_type, context)
   → { approved_name, dual_label?, dnt?, source, effective_version }
```

- **Context = substance vs brand** — regulated content (SmPC, PIL) resolves to the nonproprietary name for the market; promotional content may resolve to a market brand.
- **Locale and jurisdiction** — en-US → acetaminophen; en-GB and EU locales → paracetamol.
- **Dual-labelling** — where required, the resolver returns the paired form (for example, the INN with the alternative in parentheses).
- **Effective version** — resolution uses the names valid at the document’s effective date, not merely the latest (§12).
- **Brand DNT** — brand names default to keep-in-source; a market-substitution rule applies only where configured for the content type.

Resolution is logged with the chosen name, source authority and version, so a reviewer sees exactly why a name was used.

## 6. How agents consume and enforce it

1. **Translation agent** — calls the resolver for every detected substance or brand; it never free-translates a name. Unresolved candidates are flagged, not guessed.
2. **Critique agent** — flags any drug/substance/brand name that does not match the resolved approved name as a Critical Accuracy/Terminology error (auto-fail), citing the substance and version. It also flags **confusable proximity** — a name close to a LASA neighbour — for human review.
3. **Compliance agent** — checks dual-labelling requirements and that regulated content uses the nonproprietary form.
4. **Black Book** — the generated negative slice (prohibitions, confusables, withdrawn brands) is enforced as described in the Black Book spec; Nomenclature is the source of those entries, maintained once.

## 7. The negative slice published to the Black Book

Nomenclature owns the positive graph; the Black Book owns the derived don’ts. Generated entries include: “never use \<US name\> in \<EU/UK locale\>”, “never confuse \<A\> with \<B\> (LASA, tall-man)”, “\<brand\> is withdrawn in \<market\> — never reference”, and brand do-not-translate handling. These are generated from the graph and effective-dated with it, so the two stores never drift.

## 8. Setting it up for an organisation

1. **Seed substances** from WHO INN and ATC, anchored by stable identifiers.
2. **Seed nonproprietary names** from USAN and the pharmacopoeias, with jurisdictions and sources.
3. **Seed dual-label pairs and LASA** from the safety baselines.
4. **Onboard the client brand portfolio** from RIM/regulatory, with markets, holders and status.
5. **Validate before activation** — no node or edge goes active without curator/regulatory approval; unverified entries sit proposed.

## 9. Curation lifecycle

```
   CAPTURE ─▶ CURATE ─▶ GOVERN ─▶ CONSUME ─▶ MEASURE ─┐
      ▲                                                │
      └──────────────  CLOSE THE LOOP  ◀───────────────┘
```

1. **Capture.** New INN recommendations (WHO publishes periodically), new brand launches and withdrawals (from client RIM), pharmacopoeia and Standard-Terms updates, new LASA additions, and reviewer overrides on naming all become candidates.
2. **Curate.** The Nomenclature owner, with regulatory, reviews candidates, sets jurisdictions, dual-label requirements and effective dates.
3. **Govern.** Promotion is change-controlled, effective-dated, signed (Part 11); superseded names are deprecated, never deleted.
4. **Consume.** The resolver and agents use active, in-date names; firings update telemetry; the Black Book negative slice regenerates.
5. **Measure.** Resolution hit rate, name-errors-caught, confusable-flag precision, stale-brand counts.
6. **Close the loop.** Any **naming escape** (a wrong name found after sign-off) triggers a mandatory correction *and* a Black Book prohibition, so it cannot recur.

## 10. Roles and RACI

| Activity | Owner (A) | Responsible (R) | Consulted (C) | Informed (I) |
| --- | --- | --- | --- | --- |
| Nomenclature governance | Nomenclature owner | Nomenclature owner | Regulatory / PV | Build team |
| INN / pharmacopoeia updates | Nomenclature owner | Regulatory | Lead linguist | Curators |
| Brand portfolio (launch/withdraw) | Regulatory affiliate | RIM/regulatory | Commercial | LangOps |
| LASA / dual-label safety | PV lead | PV lead | Regulatory | Reviewers |
| Naming escape → correction + prohibition | Quality lead | Nomenclature owner | Regulatory | LangOps |

## 11. Metrics

- **Resolution hit rate** — share of substances/brands resolved without escalation.
- **Name-errors caught** — Critical naming errors the critique agent flags (and escapes that slip past).
- **Confusable-flag precision** — share of LASA flags a reviewer upholds; drives tuning.
- **Stale-brand count** — withdrawn/expired brand entries needing review.
- **Authority-currency lag** — time between an authority update (new INN, pharmacopoeia change) and its adoption in the graph.

## 12. Governance, versioning, audit — and why effective-dating matters here

Names genuinely change over time: nonproprietary names harmonise on a date (the BAN→rINN harmonisation is the canonical example), and brands launch and withdraw. The graph is therefore strictly **effective-dated**: a document with a 2019 effective date resolves to the names valid in 2019, not today’s. Every resolution records the name, source authority and version; promotion and deprecation are signed actions; the firing and resolution logs are immutable and reconstructable. Effective-dating is the property that keeps historical and re-run documents correct.

## 13. Cross-industry analogies

The graph pattern — canonical entity → jurisdiction-resolved name → confusables → DNT — is industry-neutral:
- **Banking / financial services** — legal entity names and LEI codes, regulated product names, instrument identifiers (ISIN/ticker), and confusable entity names.
- **Legal** — party names, court and citation names, statute short-titles, and jurisdiction-specific terms of art.

Only the authorities and content of the graph change; the resolver, enforcement and curation loop are the same.

## 14. Backlog (epic E14)

- **E14.S1** Nomenclature graph data model (substance ↔ INN ↔ national name ↔ brand ↔ confusable), effective-dated. *AC:* substances anchored by stable identifiers; names carry jurisdiction, source and dates.
- **E14.S2** Authority importers (WHO INN, USAN/pharmacopoeia, LASA) with provenance and currency tracking. *AC:* every name traces to a source; import is change-controlled.
- **E14.S3** Locale resolution service. *AC:* `resolve(...)` returns the market-correct name, dual-label and DNT for locale + content-type + context; decisions logged.
- **E14.S4** Enforcement wiring. *AC:* name mismatch → Critical MQM (auto-fail); confusable proximity → human flag.
- **E14.S5** Effective-dated versioning. *AC:* historical/re-run documents resolve to names valid at their effective date.
- **E14.S6** Client brand-portfolio onboarding from RIM. *AC:* launches/withdrawals reflected with markets and status.
- **E14.S7** Negative-slice generation into the Black Book. *AC:* prohibitions/confusables/withdrawn-brand entries generated from the graph, effective-dated with it, never maintained twice.
- **E14.S8** Curation and metrics. *AC:* candidate capture from authorities and overrides; resolution hit rate, confusable precision, currency lag on the dashboard.

## 15. Open decisions (ADR candidates)

1. **Authority data sourcing/licensing** — build vs licence for INN, USAN, pharmacopoeia and LASA datasets.
2. **Excipient naming** (e.g. EU E-numbers) — Nomenclature or termbase.
3. **Dual-labelling policy** — which pairs, which markets, which content types.
4. **Brand substitution vs DNT default** — per content type (promotional may substitute; regulated keeps source/nonproprietary).
5. **Locked-term vs resolved-name conflict** — default tie-break (cross-references the Knowledge Architecture ADR open question).

## 16. Glossary delta

- **INN** — International Nonproprietary Name (WHO); the substance’s international name. **rINN** — recommended INN.
- **USAN** — United States Adopted Name. **BAN** — British Approved Name (largely harmonised to rINN).
- **ATC** — Anatomical Therapeutic Chemical classification code. **UNII / CAS** — substance identifiers.
- **LASA** — Look-Alike/Sound-Alike; confusable drug names. **Tall-man lettering** — mixed-case spelling to disambiguate LASA pairs.
- **Dual labelling** — presenting two approved names together for safety (e.g. INN with the alternative in parentheses).
- **MAH** — Marketing Authorisation Holder. **Ph. Eur. / USP** — European Pharmacopoeia / United States Pharmacopeia.
- **DNT** — Do-Not-Translate.

---

*v0.1 — build-ready. Nomenclature is the positive naming graph; its prohibitions and confusables are published to the Black Book and maintained once. Severities map to the MQM model; name mismatches and locked-name deviations inherit the Critical auto-fail rule. Effective-dating is non-negotiable, because names change over time. Authority sourcing and licensing is an open build decision.*
