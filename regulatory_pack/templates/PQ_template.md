---
document_type: PQ
title: Performance Qualification - TransMax
release: $release
version: 1.0.0
generated_at: $generated_at
generator: regulatory_pack.generators.pack_builder (TMX-3500)
signed_by: []
traceability_keys:
  - eval_case_id
  - prompt_version
  - performance_criterion
---

# Performance Qualification (PQ)

**Release:** $release
**Generated:** $generated_at
**Document type:** PQ (Performance Qualification)
**Standard:** GAMP 5 + EU Annex 11 + 21 CFR Part 11

> **STATUS:** Scaffold v0. Eval-harness output and real-world load test
> results are placeholders pending TMX-3500e and pilot signing.
> Signatures are empty - the Reg Affairs Lead signs after performance
> data is captured against the production installation.

## 1. Scope

Performance Qualification proves the system performs as required in real
operating conditions. PQ is the most release-specific of the five
documents - it captures behaviour under representative load with
production data shapes.

The release this PQ describes: **$release**.

## 2. Performance criteria

PQ is judged against the four Capability Pillars from the v3.0 Programme
Capabilities Spec (`research/v3_pilot_ready_release_plan.md`):

- **Pillar 1 - Verifiable signature on every active rule**: every rule
  in `ACTIVE` status has a non-null `approved_by` AND a `RULE_PROMOTED`
  audit event. Threshold: 100% of `ACTIVE` rows. Closed by TMX-3045.
- **Pillar 2 - Defensible audit chain**: hashed-chain integrity
  preserved across an end-to-end translation job, verifiable via
  `scripts/verify_audit_chain.py`. Threshold: 100% of audit events
  verify. Currently evidence-only pending TMX-3101 (Audit Ledger v2).
- **Pillar 3 - Deterministic regulatory-pack quality gates**: every
  defect class fires deterministically on its golden-eval case.
  Threshold: 100% on the eval suite under `tests/evals/`.
- **Pillar 4 - Reproducibility under qualified-supplier inputs**: every
  LLM call records provider, model, model version, prompt version, and
  token usage. Threshold: 100% of LLM calls have a populated
  JobConfigSnapshot. Per addendum A6.

## 3. Eval-harness results

> Auto-population is deferred to **TMX-3500e**. For SCAFFOLD v0 this is
> a placeholder.
>
> When TMX-3500e ships, the harness will run:
>   `python -m tests.evals.runner --report-json eval_results/$release.json`
> and the pack builder will embed the per-case outcome here.

| Eval case | Lang pair | Defect class | Outcome | Notes |
|---|---|---|---|---|
| _(auto-populated by TMX-3500e)_ | _-_ | _-_ | _-_ | _-_ |

## 4. Prompt version inventory

PQ is sensitive to prompt version because the same release with a
different prompt produces different outputs. Per addendum A8, every
prompt is pinned to a versioned YAML.

Pinned prompts present in this release:

$prompt_versions

## 5. Real-world load test

> The first PQ for a pilot tenant must include a representative load
> test against an isolated stage of production: typical document mix,
> typical reviewer concurrency, typical translation volume per day. The
> test plan and result thresholds are captured per-pilot in the pilot
> SOW (TMX-4001 family).
>
> For the SCAFFOLD v0 release this section is a placeholder.

| Metric | Threshold | Observed | Verdict |
|---|---|---|---|
| _(auto-populated per pilot)_ | _-_ | _-_ | _-_ |

## Signatures

- [ ] **Reg Affairs Lead** ..................... Date: ............ Signature: ............

(Reg Affairs Lead signs because PQ is the regulator-facing
performance attestation. The signature attests that the recorded
results are the outputs of representative-load runs against the
production installation per IQ.md.)
