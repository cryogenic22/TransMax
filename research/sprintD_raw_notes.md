Here’s a Sprint D backlog that’s review-ready, scalable, and designed so you can add more languages, more locales, more authorities without turning TransMax into a spaghetti monster.

I’ve split it into Epics → Stories → Acceptance criteria → Notes on scalability. Use it as-is in Jira.

Sprint D Backlog: Global Expansion + Regulatory Localisation + Reflexion (Scalable Design)
Epic D0: Locales and Authority Profiles as First-Class Concepts

Outcome: Locale and authority are part of the product contract, versioned, auditable, and extensible.

TMX-D001 Adopt BCP 47 locales end-to-end

Priority: P0

Owner: Backend Eng

Acceptance criteria:

API accepts and persists target_locale (e.g., fr-CA, ja-JP, en-GB)

Validation: BCP 47 pattern checks, reject invalid locale strings

Audit captures: requested locale, resolved locale, and whether fallback occurred

Backwards compatibility: target_language="fr" maps to target_locale="fr" automatically

Scalability note: This prevents a “pack per country per authority” explosion.

TMX-D002 LanguagePackFactory hierarchical locale resolution

Priority: P0

Owner: Backend Eng

Acceptance criteria:

get_pack("fr-CA") resolves in order: fr-CA → fr → default

Resolution is deterministic and logged

Unit tests cover fallback and direct-hit behaviour for at least 5 locale examples

Scalability note: Adding a new locale becomes “add pack overrides”, not rewrite core.

TMX-D003 Introduce RegulatoryProfile model (versioned + scoped)

Priority: P0

Owner: Backend Eng + QA

Acceptance criteria:

Regulatory profiles stored with:

profile_id, profile_version, authority, doc_type, locale_scope

formatting rules (decimal/date), mandatory headings, canonical phrases references

effective_date

API/job includes regulatory_profile_id or authority that resolves to one

Audit captures chosen profile and version

Scalability note: Authority templates evolve. Versioning stops silent drift.

Epic D1: Regulatory Localisation Controls

Outcome: Locale/authority differences are deterministic, testable, and don’t leak into language packs.

TMX-D010 Add profile-driven formatting gates (dates, decimals)

Priority: P0

Owner: Backend Eng + QA

Acceptance criteria:

Decimal formatting follows profile (. vs ,) without changing numeric value

Date formatting follows profile (DD/MM/YYYY etc.) and rejects ambiguity where required

Violations severity:

value change = critical (BLOCKED)

formatting mismatch = major (REVIEW_REQUIRED)

Scalability note: Formatting rules become data-driven, not hardcoded.

TMX-D011 Mandatory headings verification (template conformance)

Priority: P1

Owner: Backend Eng + QA

Acceptance criteria:

For block-structured docs, profile can declare mandatory headings

System validates presence/order for supported doc types

Missing mandatory heading → major (REVIEW_REQUIRED) or BLOCKED for strict profiles (configurable)

Scalability note: Enables authority-specific template compliance without per-template code paths.

TMX-D012 Canonical phrase sets as “Profile Phrase Library”

Priority: P1

Owner: Backend Eng + PM

Acceptance criteria:

Profiles reference canonical phrase sets (per doc_type/section/audience)

Phrase sets stored versioned, with allowed variants and forbidden variants

Enforcement uses same mechanism as glossary preferred phrases

Audit records which phrase set version applied

Scalability note: You’ll reuse this across 30 authorities without rewriting prompts.

Epic D2: Reflexion as a Triage Signal (Not a Gatekeeper)

Outcome: Reflexion improves trust and flags risk without creating false confidence.

TMX-D020 Add reverse_translate node (configurable, segment-scoped)

Priority: P0

Owner: Backend Eng

Acceptance criteria:

Node runs only when triggered by policy:

high risk OR profile requires OR segment contains safety patterns OR TM_EXACT not used

Stores reverse_translation per segment (configurable storage policy)

Does not run for TM_EXACT segments by default (configurable)

Scalability note: Keeps cost and latency under control.

TMX-D021 Implement semantic checklist validator (structured output)

Priority: P0

Owner: Backend Eng + QA

Acceptance criteria:

Validator returns JSON flags per segment for:

negation preserved

numbers preserved

units preserved

frequency preserved

modality preserved (optional for v1)

Flags contribute to a semantic_risk score (low/med/high)

semantic_risk affects routing (REVIEW_REQUIRED) but never forces PASS

Scalability note: This is safer than cosine similarity alone.

TMX-D022 Similarity score as weak signal (optional)

Priority: P2

Owner: Backend Eng

Acceptance criteria:

Embedding similarity computed between source and back-translation

Stored in audit as “similarity_signal”

Never used alone to pass a segment

Scalability note: Prevents over-reliance on a noisy metric.

Epic D3: Data Model and Audit Extensions

Outcome: Everything added is traceable, versioned, and future-proof.

TMX-D030 DB migration: locale + profile + reflex fields

Priority: P0

Owner: Backend Eng

Acceptance criteria:

Document: target_locale, authority, regulatory_profile_id, regulatory_profile_version

Segment: reverse_translation_ref (or text), semantic_risk, similarity_signal

All fields are optional and feature-flagged for gradual rollout

TMX-D031 Audit schema upgrade for locale + profile + reflexion

Priority: P0

Owner: Backend Eng + QA

Acceptance criteria:

Audit includes:

requested locale, resolved locale, fallback chain

profile id/version, effective date

reflexion trigger reasons per segment

semantic_risk + flags + similarity (if enabled)

Audit remains schema-validated

Scalability note: This is how you keep “global complexity” debuggable.

Epic D4: Certification and Regression for Global Expansion

Outcome: Adding languages/locales is a controlled release, not a gamble.

TMX-D040 Locale fallback tests (fr-CA → fr)

Priority: P0

Owner: QA

Acceptance criteria:

test_locale_fallback.py proves pack resolution and audit capture

Includes at least: fr-CA, fr-FR, pt-BR/pt-PT, zh-Hans/zh-Hant, ar-SA/ar

TMX-D041 Authority profile conformance tests

Priority: P1

Owner: QA

Acceptance criteria:

For one profile (EMA) and one doc type:

decimal format validated

date format validated

mandatory headings validated

TMX-D042 Reflexion regression tests (false confidence prevention)

Priority: P0

Owner: QA + Backend Eng

Acceptance criteria:

Create test cases where similarity is high but meaning is wrong (negation flip, frequency shift)

Ensure system still BLOCKS/REVIEW_REQUIRED based on deterministic checks and semantic checklist

Reflexion never overrides safety gates

Scalability note: This keeps the reflexion feature honest.

Epic D5: Scale Mechanics (Adding more languages over time)

Outcome: Adding a language is repeatable and cheap.

TMX-D050 “Language Pack Kit” template

Priority: P1

Owner: Backend Eng

Acceptance criteria:

Standard folder/template with:

pack config

tokeniser hook (optional)

normalisation rules

certification test file + sample cases

New pack can be added with minimal touch to core code

TMX-D051 Pack registry + versioning

Priority: P2

Owner: Backend Eng

Acceptance criteria:

Language pack versions stored and referenced in audit

Runtime resolution uses explicit version (default “latest approved”)

TMX-D052 Profile registry + versioning

Priority: P2

Owner: Backend Eng + PM

Acceptance criteria:

Same as language packs: profiles are versioned and “approved”

Backward compatibility maintained for old jobs

Sprint D sequencing (recommended cut)

If you want this to land cleanly without ballooning:

Sprint D1 (P0 only)

TMX-D001, D002, D003

TMX-D010

TMX-D020, D021

TMX-D030, D031

TMX-D040, D042

Sprint D2 (expand)

TMX-D011, D012

TMX-D041

TMX-D050

Sprint D3 (polish)

TMX-D022, D051, D052

“Done” definition for Sprint D

You’re done when:

A job can be run with fr-CA and profile HealthCanada and it resolves correctly + logs it.

Reflexion can run only on flagged high-risk segments, produces a semantic_risk, and never causes false PASS.

Audit shows locale/profile/reflexion signals in a way a reviewer can understand.

Adding a new locale doesn’t require changing the orchestrator.

If you tell me which authorities you actually care about first (EMA + Health Canada + FDA?), I’ll also give you a starter set of RegulatoryProfile definitions and a canonical phrase library structure that won’t implode when you add more markets.

I want to cover EU, Middle East, Japan, FDA for now, UK as well. 

Got it. If you want EU, UK, FDA (US), Middle East, Japan covered first, the smartest move is to treat this as 5 regulatory “families” with clear profile boundaries, rather than dozens of country-by-country hacks.

Here’s how I’d set it up so you can scale cleanly.

1) Start with 5 “RegulatoryProfile families”

You’ll end up with multiple profiles per family (doc type + locale), but the family gives structure.

Family A: EU (EMA + QRD)

Authorities: EMA

Locales (initial): en-GB, fr-FR, de-DE, (optional next: es-ES, it-IT)

Doc types: SmPC, PIL, Labelling

Key controls:

QRD section headings and ordering

EU decimal separator defaults by locale

Standard EU phrasing library (QRD-esque phrases)

Family B: UK (MHRA)

Authorities: MHRA

Locales: en-GB primarily

Doc types: SmPC, PIL, Labelling

Key controls:

UK-specific spelling/terminology expectations (minor but real)

Potential divergence from EMA templates in presentation requirements

UK “plain English” preferences for patient leaflets

Family C: US (FDA)

Authorities: FDA

Locales: en-US

Doc types: Prescribing Information (PI), Medication Guide, IFU (if in scope)

Key controls:

US label structure differs materially from SmPC

Date/units expectations (often US-style)

Strong section template enforcement (this is where “profile templates” matter most)

Family D: Middle East (multi-authority, Arabic primary)

Authorities (initial bucket): pick a set: SFDA (Saudi), DHA/MOHAP (UAE), Qatar MOPH, etc.

Locales: ar-SA as a starting point, then ar-AE

Doc types: PIL/leaflet and label fragments first (tables common)

Key controls:

Arabic digit policy (Western vs Arabic-Indic) often market-specific

RTL rendering and punctuation handling

Mixed-script stability (INNs/brand names stay Latin)

Family E: Japan (PMDA/MHLW)

Authorities: PMDA (and MHLW context)

Locales: ja-JP

Doc types: package insert equivalents, patient-facing content

Key controls:

Tokeniser-based glossary enforcement

Preferred phrasing and variant control (kanji/kana choices)

Very strict audience register differences

2) Proposed first wave of locales (keep it tight)

If you want “coverage” without drowning:

EU: en-GB, fr-FR, de-DE

UK: en-GB (but separate MHRA profile from EMA profile)

FDA: en-US

Middle East: ar-SA (add ar-AE later)

Japan: ja-JP

That’s 6 locales across 5 families. It’s a manageable certification surface.

3) The backlog adjustments for Sprint D (tailored to your regions)
Add these stories (or update existing ones)
TMX-D005 Create initial RegulatoryProfile registry for 5 families

Priority: P0

Owner: PM + QA + Backend Eng

Acceptance criteria:

Profiles exist for:

EMA SmPC/PIL/Labelling: en-GB, fr-FR, de-DE

MHRA SmPC/PIL/Labelling: en-GB

FDA PI/MedGuide: en-US

Middle East PIL/Labelling: ar-SA

PMDA pack insert/patient: ja-JP

Each profile includes:

locale formatting: decimal, date

mandatory headings list (doc-type specific)

phrase set references (even if minimal v1)

TMX-D006 Implement per-profile numeric formatting rules + gates

Priority: P0

Owner: Backend Eng + QA

Acceptance criteria:

Decimal separator enforcement per locale

Value preservation always checked

Date format enforcement (where applicable)

For Arabic: digit policy parameterised per profile

TMX-D013 Japanese: tokeniser-based enforcement is mandatory

Priority: P0

Owner: Backend Eng

Acceptance criteria:

No substring matching for Japanese in production mode

Tokeniser match supports:

preferred terms

allowed variants

forbidden variants

Certification suite includes false-positive and false-negative cases

TMX-D014 Arabic: digit policy and mixed-script tests for ar-SA

Priority: P0

Owner: QA + Backend Eng

Acceptance criteria:

Tests for:

western digits preserved where configured

Arabic-Indic digits preserved where configured

mixed script INNs remain Latin

mg/day and mg/kg/day patterns preserved

RTL punctuation stability tests

TMX-D015 FDA: PI structure compliance checks

Priority: P1

Owner: QA + Backend Eng

Acceptance criteria:

For a structured doc input, enforce mandatory sections for PI

Missing sections route to REVIEW_REQUIRED

Phrase set hooks exist (even if initial set small)

TMX-D016 UK vs EU split: MHRA profile fork (en-GB)

Priority: P1

Owner: PM + QA

Acceptance criteria:

Same locale (en-GB) can resolve to different profiles:

EMA en-GB vs MHRA en-GB

Audit records profile chosen and why

4) What to be careful about (so you don’t paint yourself into a corner)
Don’t equate “EU” with “fr-FR”

EU is an authority template family, not a language. Your design already supports that, just keep the discipline:

Locale chooses the language driver

Profile chooses the regulatory template and formatting rules

Middle East is not one profile forever

Start with ar-SA + one authority profile, but keep it easy to clone:

same pack, different profile (digit policy changes, template headings change)

FDA is structurally different

Avoid trying to “fit PI into SmPC blocks”. Treat it as its own doc-type template with its own headings and phrase library.

5) What I’d ask from you to finalise the profile registry (no long back-and-forth)

Just these decisions, and we can lock the first profile pack cleanly:

For Middle East, which authority first: SFDA (Saudi) or UAE (MOHAP/DHA)?

For EU languages, do you want just en-GB/fr-FR/de-DE first, or include es-ES as well?

If you don’t answer, I’d still proceed with SFDA + (en-GB/fr-FR/de-DE) as the safest default.

If you want, I can now draft the actual RegulatoryProfile JSON/YAML definitions for these five families (v1) plus the starter canonical phrase library structure so Engineering can implement without guessing.

provide JSON/YAML
{
  "registry_version": "reg_profiles.v1",
  "generated_on": "2026-01-18",
  "profiles": [
    {
      "profile_id": "EMA_SMPC_EN_GB",
      "profile_version": "1.0.0",
      "authority": "EMA",
      "region_family": "EU",
      "doc_type": "smpc",
      "locale": "en-GB",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "1. NAME OF THE MEDICINAL PRODUCT",
          "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
          "3. PHARMACEUTICAL FORM",
          "4. CLINICAL PARTICULARS",
          "5. PHARMACOLOGICAL PROPERTIES",
          "6. PHARMACEUTICAL PARTICULARS"
        ],
        "strict_heading_match": true,
        "allow_heading_variants": false
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "EMA_QRD_EN_GB_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "EMA_PIL_EN_GB",
      "profile_version": "1.0.0",
      "authority": "EMA",
      "region_family": "EU",
      "doc_type": "pil",
      "locale": "en-GB",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "Package leaflet: Information for the user",
          "What is in this leaflet",
          "1. What <PRODUCT> is and what it is used for",
          "2. What you need to know before you take/use <PRODUCT>",
          "3. How to take/use <PRODUCT>",
          "4. Possible side effects",
          "5. How to store <PRODUCT>",
          "6. Contents of the pack and other information"
        ],
        "strict_heading_match": false,
        "allow_heading_variants": true
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "EMA_QRD_EN_GB_PIL_PLAIN",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "patient", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "EMA_SMPC_FR_FR",
      "profile_version": "1.0.0",
      "authority": "EMA",
      "region_family": "EU",
      "doc_type": "smpc",
      "locale": "fr-FR",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ",",
        "thousands_separator": " ",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "1. DÉNOMINATION DU MÉDICAMENT",
          "2. COMPOSITION QUALITATIVE ET QUANTITATIVE",
          "3. FORME PHARMACEUTIQUE",
          "4. DONNÉES CLINIQUES",
          "5. PROPRIÉTÉS PHARMACOLOGIQUES",
          "6. DONNÉES PHARMACEUTIQUES"
        ],
        "strict_heading_match": true,
        "allow_heading_variants": false
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "EMA_QRD_FR_FR_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "EMA_SMPC_DE_DE",
      "profile_version": "1.0.0",
      "authority": "EMA",
      "region_family": "EU",
      "doc_type": "smpc",
      "locale": "de-DE",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD.MM.YYYY",
        "decimal_separator": ",",
        "thousands_separator": ".",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "1. BEZEICHNUNG DES ARZNEIMITTELS",
          "2. QUALITATIVE UND QUANTITATIVE ZUSAMMENSETZUNG",
          "3. DARREICHUNGSFORM",
          "4. KLINISCHE ANGABEN",
          "5. PHARMAKOLOGISCHE EIGENSCHAFTEN",
          "6. PHARMAZEUTISCHE ANGABEN"
        ],
        "strict_heading_match": true,
        "allow_heading_variants": false
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "EMA_QRD_DE_DE_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "MHRA_SMPC_EN_GB",
      "profile_version": "1.0.0",
      "authority": "MHRA",
      "region_family": "UK",
      "doc_type": "smpc",
      "locale": "en-GB",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "1. NAME OF THE MEDICINAL PRODUCT",
          "2. QUALITATIVE AND QUANTITATIVE COMPOSITION",
          "3. PHARMACEUTICAL FORM",
          "4. CLINICAL PARTICULARS",
          "5. PHARMACOLOGICAL PROPERTIES",
          "6. PHARMACEUTICAL PARTICULARS"
        ],
        "strict_heading_match": true,
        "allow_heading_variants": false
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "MHRA_EN_GB_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "FDA_PI_EN_US",
      "profile_version": "1.0.0",
      "authority": "FDA",
      "region_family": "US",
      "doc_type": "pi",
      "locale": "en-US",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "MM/DD/YYYY",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_source",
        "unit_style": "US"
      },
      "templates": {
        "mandatory_headings": [
          "HIGHLIGHTS OF PRESCRIBING INFORMATION",
          "FULL PRESCRIBING INFORMATION: CONTENTS",
          "FULL PRESCRIBING INFORMATION",
          "INDICATIONS AND USAGE",
          "DOSAGE AND ADMINISTRATION",
          "DOSAGE FORMS AND STRENGTHS",
          "CONTRAINDICATIONS",
          "WARNINGS AND PRECAUTIONS",
          "ADVERSE REACTIONS"
        ],
        "strict_heading_match": false,
        "allow_heading_variants": true
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "FDA_PI_EN_US_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "SFDA_PIL_AR_SA",
      "profile_version": "1.0.0",
      "authority": "SFDA",
      "region_family": "MIDDLE_EAST",
      "doc_type": "pil",
      "locale": "ar-SA",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "DD/MM/YYYY",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_western",
        "script_direction": "rtl"
      },
      "templates": {
        "mandatory_headings": [
          "نشرة داخلية",
          "ما هو هذا الدواء وفيم يُستعمل",
          "قبل استعمال هذا الدواء",
          "كيفية استعمال هذا الدواء",
          "الأعراض الجانبية المحتملة",
          "كيفية حفظ هذا الدواء",
          "محتويات العبوة ومعلومات أخرى"
        ],
        "strict_heading_match": false,
        "allow_heading_variants": true
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "SFDA_AR_SA_PIL_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "patient", "section": "global" }
        }
      ]
    },
    {
      "profile_id": "PMDA_PI_JA_JP",
      "profile_version": "1.0.0",
      "authority": "PMDA",
      "region_family": "JAPAN",
      "doc_type": "package_insert",
      "locale": "ja-JP",
      "effective_date": "2026-01-01",
      "formatting": {
        "date_format": "YYYY/MM/DD",
        "decimal_separator": ".",
        "thousands_separator": ",",
        "digit_policy": "preserve_source"
      },
      "templates": {
        "mandatory_headings": [
          "効能又は効果",
          "用法及び用量",
          "禁忌",
          "警告",
          "注意",
          "副作用"
        ],
        "strict_heading_match": false,
        "allow_heading_variants": true
      },
      "policy_defaults": {
        "risk_level": "high",
        "auto_pass_allowed": false,
        "reflexion": {
          "enabled": true,
          "trigger_rules": ["SAFETY_PATTERN", "NO_TM_EXACT", "REQUIRED_BY_PROFILE"]
        }
      },
      "phrase_sets": [
        {
          "phrase_set_id": "PMDA_JA_JP_CORE",
          "phrase_set_version": "1.0.0",
          "scope": { "audience": "hcp", "section": "global" }
        }
      ]
    }
  ]
}

registry_version: reg_profiles.v1
generated_on: "2026-01-18"
profiles:
  - profile_id: EMA_SMPC_EN_GB
    profile_version: 1.0.0
    authority: EMA
    region_family: EU
    doc_type: smpc
    locale: en-GB
    effective_date: "2026-01-01"
    formatting:
      date_format: DD/MM/YYYY
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "1. NAME OF THE MEDICINAL PRODUCT"
        - "2. QUALITATIVE AND QUANTITATIVE COMPOSITION"
        - "3. PHARMACEUTICAL FORM"
        - "4. CLINICAL PARTICULARS"
        - "5. PHARMACOLOGICAL PROPERTIES"
        - "6. PHARMACEUTICAL PARTICULARS"
      strict_heading_match: true
      allow_heading_variants: false
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: EMA_QRD_EN_GB_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global

  - profile_id: EMA_PIL_EN_GB
    profile_version: 1.0.0
    authority: EMA
    region_family: EU
    doc_type: pil
    locale: en-GB
    effective_date: "2026-01-01"
    formatting:
      date_format: DD/MM/YYYY
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "Package leaflet: Information for the user"
        - "What is in this leaflet"
        - "1. What <PRODUCT> is and what it is used for"
        - "2. What you need to know before you take/use <PRODUCT>"
        - "3. How to take/use <PRODUCT>"
        - "4. Possible side effects"
        - "5. How to store <PRODUCT>"
        - "6. Contents of the pack and other information"
      strict_heading_match: false
      allow_heading_variants: true
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: EMA_QRD_EN_GB_PIL_PLAIN
        phrase_set_version: 1.0.0
        scope:
          audience: patient
          section: global

  - profile_id: EMA_SMPC_FR_FR
    profile_version: 1.0.0
    authority: EMA
    region_family: EU
    doc_type: smpc
    locale: fr-FR
    effective_date: "2026-01-01"
    formatting:
      date_format: DD/MM/YYYY
      decimal_separator: ","
      thousands_separator: " "
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "1. DÉNOMINATION DU MÉDICAMENT"
        - "2. COMPOSITION QUALITATIVE ET QUANTITATIVE"
        - "3. FORME PHARMACEUTIQUE"
        - "4. DONNÉES CLINIQUES"
        - "5. PROPRIÉTÉS PHARMACOLOGIQUES"
        - "6. DONNÉES PHARMACEUTIQUES"
      strict_heading_match: true
      allow_heading_variants: false
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: EMA_QRD_FR_FR_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global

  - profile_id: EMA_SMPC_DE_DE
    profile_version: 1.0.0
    authority: EMA
    region_family: EU
    doc_type: smpc
    locale: de-DE
    effective_date: "2026-01-01"
    formatting:
      date_format: DD.MM.YYYY
      decimal_separator: ","
      thousands_separator: "."
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "1. BEZEICHNUNG DES ARZNEIMITTELS"
        - "2. QUALITATIVE UND QUANTITATIVE ZUSAMMENSETZUNG"
        - "3. DARREICHUNGSFORM"
        - "4. KLINISCHE ANGABEN"
        - "5. PHARMAKOLOGISCHE EIGENSCHAFTEN"
        - "6. PHARMAZEUTISCHE ANGABEN"
      strict_heading_match: true
      allow_heading_variants: false
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: EMA_QRD_DE_DE_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global

  - profile_id: MHRA_SMPC_EN_GB
    profile_version: 1.0.0
    authority: MHRA
    region_family: UK
    doc_type: smpc
    locale: en-GB
    effective_date: "2026-01-01"
    formatting:
      date_format: DD/MM/YYYY
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "1. NAME OF THE MEDICINAL PRODUCT"
        - "2. QUALITATIVE AND QUANTITATIVE COMPOSITION"
        - "3. PHARMACEUTICAL FORM"
        - "4. CLINICAL PARTICULARS"
        - "5. PHARMACOLOGICAL PROPERTIES"
        - "6. PHARMACEUTICAL PARTICULARS"
      strict_heading_match: true
      allow_heading_variants: false
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: MHRA_EN_GB_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global

  - profile_id: FDA_PI_EN_US
    profile_version: 1.0.0
    authority: FDA
    region_family: US
    doc_type: pi
    locale: en-US
    effective_date: "2026-01-01"
    formatting:
      date_format: MM/DD/YYYY
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_source
      unit_style: US
    templates:
      mandatory_headings:
        - "HIGHLIGHTS OF PRESCRIBING INFORMATION"
        - "FULL PRESCRIBING INFORMATION: CONTENTS"
        - "FULL PRESCRIBING INFORMATION"
        - "INDICATIONS AND USAGE"
        - "DOSAGE AND ADMINISTRATION"
        - "DOSAGE FORMS AND STRENGTHS"
        - "CONTRAINDICATIONS"
        - "WARNINGS AND PRECAUTIONS"
        - "ADVERSE REACTIONS"
      strict_heading_match: false
      allow_heading_variants: true
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: FDA_PI_EN_US_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global

  - profile_id: SFDA_PIL_AR_SA
    profile_version: 1.0.0
    authority: SFDA
    region_family: MIDDLE_EAST
    doc_type: pil
    locale: ar-SA
    effective_date: "2026-01-01"
    formatting:
      date_format: DD/MM/YYYY
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_western
      script_direction: rtl
    templates:
      mandatory_headings:
        - "نشرة داخلية"
        - "ما هو هذا الدواء وفيم يُستعمل"
        - "قبل استعمال هذا الدواء"
        - "كيفية استعمال هذا الدواء"
        - "الأعراض الجانبية المحتملة"
        - "كيفية حفظ هذا الدواء"
        - "محتويات العبوة ومعلومات أخرى"
      strict_heading_match: false
      allow_heading_variants: true
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: SFDA_AR_SA_PIL_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: patient
          section: global

  - profile_id: PMDA_PI_JA_JP
    profile_version: 1.0.0
    authority: PMDA
    region_family: JAPAN
    doc_type: package_insert
    locale: ja-JP
    effective_date: "2026-01-01"
    formatting:
      date_format: YYYY/MM/DD
      decimal_separator: "."
      thousands_separator: ","
      digit_policy: preserve_source
    templates:
      mandatory_headings:
        - "効能又は効果"
        - "用法及び用量"
        - "禁忌"
        - "警告"
        - "注意"
        - "副作用"
      strict_heading_match: false
      allow_heading_variants: true
    policy_defaults:
      risk_level: high
      auto_pass_allowed: false
      reflexion:
        enabled: true
        trigger_rules:
          - SAFETY_PATTERN
          - NO_TM_EXACT
          - REQUIRED_BY_PROFILE
    phrase_sets:
      - phrase_set_id: PMDA_JA_JP_CORE
        phrase_set_version: 1.0.0
        scope:
          audience: hcp
          section: global
