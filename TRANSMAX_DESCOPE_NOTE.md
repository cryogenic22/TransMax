# Transmax — Descope and Red-Team Adjustments

**Status:** Companion note to the May 2026 review documents
**Owner:** Product Management — Pharma Translation Agent
**Audience:** Programme Lead, Engineering Lead, Regulatory Affairs Lead, GTM, Steering
**Date:** May 2026

---

## 1. Purpose

This note is a deliberate corrective to the three prior documents:

- *Transmax — Code Review and Enterprise Upgrade Path* (Word, May 2026)
- *Transmax — Headless and Multi-Surface Agent Specification* (Markdown, May 2026)
- *Transmax — Platform Capabilities Specification* (Markdown, May 2026)

Those documents were thorough but also, in places, ambitious to a fault. Architectural elegance and competitive completeness drove some scope that customers will not pay for in v1 and that the team will not deliver in 90 days at the size we sized. This note captures what to cut, what to push, what we underweighted, and the two strategic decisions that change the shape of everything else.

This note **supplements** the prior documents rather than replacing them. They remain the reference for "what good looks like at scale". This note is the reference for "what we actually do in the next 12 months".

---

## 2. Items to Cut or Push

The following thirteen items are removed from the early roadmap. None is wrong on its merits; each is wrong on its commercial timing.

| # | Item | Was scoped at | Adjustment | Rationale |
| --- | --- | --- | --- | --- |
| 1 | Six-layer rule taxonomy (L0–L5) | Phase 1 | Collapse to three layers (regulator, tenant, project) | Brand-level and reviewer-level layers are theoretical for almost every pharma org we will sell to. Six layers in v1 is conflict-resolver complexity that nobody asked for. |
| 2 | Knowledge graph with MedDRA / MeSH / ATC / IDMP entities | Phase 2 | Push to Phase 3, replace with a thin tenant-scoped entity table that customers can populate from their own sources | MedDRA is licensed and expensive. IDMP integration is a programme in itself. Almost no TMS competitor offers this in 2026. |
| 3 | Eight confidence signals | Phase 1 | Three signals in Phase 1 (TM match, glossary adherence, severity-weighted defect rate); back-translation in Phase 2 | The four similarity metrics correlate strongly. Three composed signals get most of the value. Eight is a model-research project, not a product feature. |
| 4 | Per-slice MLflow-versioned calibration models | Phase 2 | Single global isotonic regression refreshed weekly, until per-tenant evidence justifies a slice | Per-slice calibration is high-end ML ops most pharma customers cannot validate or audit. |
| 5 | Per-reviewer calibration / personalisation | Phase 3 | Drop entirely | Pharma reviewers are designed to be interchangeable in a regulated workflow. Per-reviewer personalisation introduces a bias channel a regulator will challenge. |
| 6 | TypeScript SDK and CLI | Phase 1–2 | Push to Phase 3; consider a Java SDK ahead of TypeScript | Customer engineering in pharma is mostly Python and Java; CLI buyers do not exist in regulatory and clinical teams. |
| 7 | MCP server hardening (auth, scopes, idempotency through MCP transport) | Phase 1 | Phase 2 | Strategically right; ecosystem still nascent; will not win 2026 pilots. |
| 8 | eCTD v4.0 native publisher functionality | Phase 3 | Reposition as integration with LORENZ / Extedo / EXT-DM, not native capability | Customers buy dedicated eCTD publishers. We feed them; we do not replace them. |
| 9 | LaTeX support for SAPs and protocols | Phase 3 | Drop entirely | Statistical Analysis Plans are written in English and stay in English. Nobody translates them. |
| 10 | Cross-tenant anonymised boilerplate library | Phase 3 | Drop entirely | Politically toxic, legally fraught, low marginal value over the per-tenant Determinism Library. |
| 11 | Figures pipeline with SVG-text walking and label re-rendering | Phase 3 | Out-of-scope; recommend a DTP partner integration | This is desktop-publishing work, not translation work. Customers outsource it today; building it as platform is gold-plating. |
| 12 | Eleven TLF cell types in the classifier | Phase 2 | Five cell types: header, label, numeric, statistical-notation, footnote | Five covers the actual variation in the CDISC-adjacent corpus. Finer-grained distinctions are noise in v1. |
| 13 | Annual notified-body assessment per release for the EU AI Act | Phase 3 onwards | Once for the platform; per-release is internal evidence only | Material-change reassessments only; per-release external review is overkill and would slow cadence to a crawl. |

Net effect: roughly 30% reduction in engineering scope and 40% reduction in "wow we'd love that" scope without weakening the regulatory story.

---

## 3. Items Underweighted in the Originals

Five areas got too little attention and are now elevated.

| # | Item | Status in originals | Adjustment |
| --- | --- | --- | --- |
| 1 | Glossary and TM management UX | Data model specified; UX assumed | Promote to a Phase 1 deliverable. Bulk import (TBX, TMX), term-conflict resolution, term lifecycle, term-impact telemetry. This is where most TMS customer pain actually lives and where pilots will be won or lost. |
| 2 | Reviewer ergonomics | Functional requirements stated | Promote to a Phase 1 deliverable. Keyboard shortcuts (`j/k` segment nav, `a/r/e` accept-reject-edit, `g` glossary lookup, `c` comment), comment threads, suggested-edit conversations, segment status colour scale, virtualised long lists, undo / redo with audit. |
| 3 | Customer onboarding | Implicit | Treated as an explicit programme. Pilot-to-production typically takes 3–9 months in pharma; onboarding throughput, not engineering velocity, is the revenue bottleneck. |
| 4 | TBX / TMX import on day one | Mentioned in passing | Table-stakes for migrating customers off Phrase or Smartling. Promote to Phase 1 with a quality test on a real customer's existing assets. |
| 5 | Pricing simplicity | Four-tier model proposed | Reduce to two tiers (Pilot, Enterprise) plus the Regulatory Pack as an add-on. Tier proliferation is a post-PMF problem, not a pre-PMF one. |

---

## 4. Two Strategic Decisions That Change Everything Else

The single most important thing the steering committee can do before committing to the upgrade path is to make these two calls explicitly.

### 4.1 Productised SaaS vs Managed Service

Throughout the originals I assumed a productised SaaS with billing, support, marketing, sales and self-service onboarding. There is a genuine alternative path: transmax as the **technical backbone of a managed service delivered by ZS consultants** to pharma clients. The consultants are the GTM; the platform is the engine; the pricing is the engagement fee.

What changes under each path:

| Dimension | Productised SaaS | Managed Service |
| --- | --- | --- |
| Phase 1 priority | Self-service, smooth onboarding, billing, support docs | Consultant enablement, client-engagement playbook, reusable industry packs |
| Customer count | 5–10 in year 1 | 2–4 large engagements in year 1 |
| Contract size | €200k–€800k ARR | €1–4M per engagement (services-led) |
| Team profile | PM + Eng + GTM + Customer Success + Support + Marketing | PM + Eng + Solution Architects + Consultants |
| Validation | SOC 2, ISO 27001, customer DPIA per tenant | Same plus per-engagement validation pack |
| Revenue ramp | Slower; product-led | Faster; consultant-led |
| 12-month roadmap effort | The full Phase 1–2 in the prior docs | ~60% of it; managed-service tools fill the gap |
| Long-term ceiling | Higher (multiples on ARR) | Lower (services scale linearly with bodies), but faster to first revenue and lower capital risk |

A defensible answer is **managed-service-led for 12 months, then transition to dual-track**: prove the capability stack with three flagship pharma engagements, codify the playbook, then productise once we know what to productise. ZS's organisational shape favours this. It also reduces capital exposure during the EU AI Act and FDA AI/ML credibility windows where regulatory demands are still settling.

If we choose the managed-service-first path, the Phase 1 roadmap shrinks substantially. Self-service onboarding, billing, public marketing site, public docs, free-tier SDK distribution — all of these defer.

### 4.2 UI-First vs Embedded-First

The originals argued for agentic-first, pharma-native positioning, then proposed a UI in Phase 1 and a headless platform in Phase 1.

If the real wedge is **embedded** — being the engine inside customers' regulatory copilots, MLR review tools and clinical-content workflows — then the UI in Phase 1 is the demo, not the product. That changes priorities:

- REST API v2, Python SDK and audit ledger get the lion's share of Phase 1 capacity.
- The UI in Phase 1 is a credible reviewer surface but not a beautiful one. It exists to demonstrate the platform and to serve as the hosted review-handoff target. Investment is consistency and reliability, not novel UX.
- Format fidelity and the four-pillar capabilities are still Phase 1; they are why the embedded path is defensible.

If we instead lead with the UI as the product (the more conventional TMS-style positioning), then the prior documents stand as written. We compete with Phrase, Smartling and XTM head-on and we need their feature breadth.

A defensible answer is **embedded-first for 12 months**, with a hosted review surface that customers can deep-link into from their own portals. We get out of the head-on TMS feature war and into a category (regulated-content translation infrastructure) where transmax can credibly own the regulatory differentiator without needing to outspend incumbents on connectors and seat count.

---

## 5. Revised Phase 1 — The Honest 90-Day Scope

Assuming **managed-service-first + embedded-first** as the working hypothesis (subject to steering decision), Phase 1 reduces to the following. Anything not on this list is Phase 2 or later.

### 5.1 Non-negotiables (security, compliance, hygiene)

1. Auth on by default; SECRET_KEY enforced; OpenAI key rotated and removed from git history; .env in .gitignore.
2. Build green; lint green; gitleaks and Dependabot live; PR-gate enforced.
3. Soft deletes on every table; row-level tenant isolation in Postgres.
4. Audit ledger redesigned with domain-separated SHA-256 and a daily Merkle anchor to AWS QLDB or signed S3 Object Lock.
5. Mega-migration unwound into versioned, semantically meaningful steps; migration test harness in CI.
6. Strip the dev-admin fallback in `lib/auth.tsx` and the mock-data fallback in `app/review/[jobId]/page.tsx`.

### 5.2 Format fidelity

7. XLIFF 2.1 canonical layer.
8. Native DOCX ingestion with tracked changes preservation; XLSX, PPTX, HTML, XLIFF, TMX round-trip.
9. PDF (digital only) ingestion with table extraction. OCR fallback in Phase 2.
10. Placeholder-count QA gate; format-fidelity score per segment; Critical / Major / Minor severity bands.
11. PDF/A-1b export with embedded fonts.

### 5.3 Capabilities

12. Three-layer rule system (regulator, tenant, project); signed approval workflow; no auto-promotion. Rule-set hash in JobConfigSnapshot.
13. Glossary CRUD with TBX import; TMX import for translation memory.
14. Determinism Library seeded with **EDQM Standard Terms only** for top six language pairs (en→de, en→fr, en→es, en→it, en→pt, en→ja).
15. Tier-1 / Tier-2 cascade live (Determinism → Exact TM → LLM); segment-result cache live with reported hit rate; pre-translation deduplication.
16. Three confidence signals (TM match, glossary adherence, severity-weighted defect rate); single global isotonic regression; tiered review thresholds; critical-defect overrides (negation, number, unit, drug-name, dose-frequency, polarity).

### 5.4 Surfaces

17. REST API v2 with OAuth 2.1, OpenAPI 3.1 source-of-truth, idempotency keys, signed webhooks.
18. Python SDK 1.0 on PyPI.
19. UI: pick one routing IA (recommend `/workspace/*`), retire the duplicate; reviewer screen with save-and-sign, keyboard shortcuts, virtualised segment list, audit-chain server-side verification badge.

### 5.5 Validation and onboarding

20. Validation Summary Report per release, signed by Programme Lead and Regulatory Affairs Lead.
21. URS / FS / IQ / OQ / PQ scaffolding; risk assessment template; 21 CFR Part 11 attestation document.
22. Vendor security questionnaire response template; HIPAA BAA template; GDPR DPA template.
23. Two paid pilots signed at €25k–€75k each (ZS-mediated under managed-service-first hypothesis).

### 5.6 What's explicitly out of Phase 1

- TypeScript SDK, CLI, MCP-server hardening, eCTD connectors, Veeva connectors, SharePoint connector, Documentum connector, knowledge graph, MedDRA / IDMP, OOML/MathML formula handling, RTF/TLF cell-level segmentation, OCR for scanned PDFs, IDML support, figures pipeline, per-slice calibration, eight-signal confidence, six-layer rules, cross-tenant boilerplate, public bug-bounty, on-prem deployment, multi-region deployment beyond a single EU region.

Each of these is properly scoped in Phase 2 or Phase 3 in the original documents.

---

## 6. Implications for Investment, Timeline and KPIs

### 6.1 Investment envelope

| Phase | Original | Revised |
| --- | --- | --- |
| Phase 0 (stop the bleeding) | Internal | Internal (unchanged) |
| Phase 1 (0–90 days) | €0.6M–€0.9M | €0.4M–€0.6M (managed-service-first reduces self-service / GTM work) |
| Phase 2 (3–6 months) | €1.2M–€1.8M | €0.9M–€1.4M |
| Phase 3 (6–12 months) | €3M–€5M | €2M–€3.5M |
| Phase 4 (12–24 months) | €8M–€15M | Revisit after Phase 2 PMF read |

Revised Phase 1–3 totals: roughly €3.3M–€5.5M over 12 months under managed-service-first, versus €4.8M–€7.7M under productised SaaS in the originals. The productised path carries a larger optionality on long-term ARR; the managed-service path carries a smaller capital risk and a faster path to first material revenue.

### 6.2 Headcount

| Role | Original Phase 1 | Revised Phase 1 |
| --- | --- | --- |
| Product Manager | 1 | 1 |
| Engineering Lead + Engineers | 10 | 8 |
| QA / Validation | 2 | 2 |
| Regulatory Affairs Lead | 1 | 1 |
| Design | 1 | 1 (tighter UI scope) |
| Security Eng | 0.5 | 0.5 |
| Solution Architect (managed-service path) | 0 | 1 |
| Consultant-facing enablement (managed-service path) | 0 | 1 |
| GTM / Marketing / CSM | 1 | 0 (managed-service path absorbs into ZS) |
| **Total FTE** | 16.5 | 15.5 (reweighted) |

### 6.3 KPIs

Original P95 translate-and-review of 5 minutes for a 1k-word document across five languages was aggressive. Revised to **≤ 15 minutes** for Phase 1, **≤ 7 minutes** for Phase 2, **≤ 3 minutes** for Phase 3.

Original Phase 1 commercial KPI of two paid pilots at €25k–€75k stays. Phase 2 revised to **3 production engagements** under managed-service-first (was 5 productised customers). Phase 3 revised to **€3M–€6M annualised revenue** (was €5M–€10M ARR).

Determinism KPI added to Phase 1 customer-facing reporting: percentage of segments resolved without an LLM call, plotted over time per tenant. Useful for both customer cost reporting and our own cost telemetry.

---

## 7. What Stays the Same

The descope does not change any of the regulatory commitments. The system still has to:

- Run a hash-chained audit ledger with cryptographic integrity, anchored daily.
- Capture an immutable JobConfigSnapshot per job with rule-set hash, glossary hash and prompt version.
- Enforce hard locks (numbers, units, drug names, EDQM terms) with Critical-defect blocking.
- Produce a Validation Summary Report per release.
- Hold approved rules and Determinism Library entries to a signed-by-human standard with no auto-promotion.
- Default deny on access; row-level tenant isolation; soft deletes; encrypted at rest.
- Produce evidence bundles a regulator can read.

These are what makes transmax pharma-grade. None is being descoped.

---

## 8. Decisions Owed Before Committing to Phase 1

The steering committee owes the following calls. Until they are made, planning continues but spend stays in Phase 0 (security and hygiene fixes only).

1. **Productised SaaS vs managed service vs hybrid.** Recommendation: managed-service-first for 12 months, dual-track from month 13.
2. **UI-first vs embedded-first.** Recommendation: embedded-first; UI is a credible reviewer surface, not the product.
3. **Region scope for Phase 1.** Recommendation: single EU region (Frankfurt / Dublin); add US in Phase 2; APAC in Phase 3.
4. **Pilot customer profile.** Three named target accounts (real names, real account owners) before kickoff. Top-20 pharma is the right segment but specific accounts must be selected with ZS account leadership.
5. **Open-source posture for the L0 rule pack.** Recommendation: keep proprietary in Phase 1; reconsider once we have three customers signed.
6. **Confidence calibration disclosure to reviewers.** Recommendation: tier label only ("light review" / "full review" / "dual review"), never the raw probability. The number itself is more anxiety-provoking than informative.
7. **Engineering team locality.** Single time zone, multi-time-zone, or follow-the-sun. Recommendation: single hub for Phase 1 (Pune or London); avoid follow-the-sun until Phase 2.
8. **First Regulatory Pack content.** Which regulator's pack do we ship first as the L0 / Determinism content (EMA, FDA, MHRA, EDQM)? Recommendation: EDQM Standard Terms and EMA QRD only; FDA SPL and others Phase 2.

---

## 9. Closing

The original documents described what good looks like across an idealised 24-month arc. This note describes what is actually achievable, sellable and validateable in the next 90 days and the 12 months after them. The two are consistent; the difference is humility about scope and honesty about what customers will pay for in the early life of a regulated product.

If the steering committee aligns with the recommendations in §8, the engineering team can compress the Phase 1 backlog to a workable 90-day plan and we can hold the first paid pilot conversation by the end of Q3 2026. If the steering committee chooses productised SaaS instead, the originals stand and the budget needs to grow accordingly.

---

*End of note.*
