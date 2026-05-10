---
document_type: OQ
title: Operational Qualification - TransMax
release: $release
version: 1.0.0
generated_at: $generated_at
generator: regulatory_pack.generators.pack_builder (TMX-3500)
signed_by: []
traceability_keys:
  - test_file
  - test_function
  - fs_req
---

# Operational Qualification (OQ)

**Release:** $release
**Generated:** $generated_at
**Document type:** OQ (Operational Qualification)
**Standard:** GAMP 5 + EU Annex 11 + 21 CFR Part 11

> **STATUS:** Scaffold v0. Test plan is auto-pulled from `tests/`. Test
> RESULTS auto-population is deferred to TMX-3500e (pytest --json-report
> integration). Signatures are empty - the QA Lead signs after the OQ
> run completes.

## 1. Scope

Operational Qualification proves each function specified in the FS works
as designed. The OQ test plan is the test suite under `tests/`; the OQ
test results are the captured pass/fail outcomes of running that suite
against the qualified installation.

The release this OQ describes: **$release**.

## 2. Test plan

The OQ test plan corresponds to all `test_*.py` files under `tests/`,
mapped to FS requirements via the worksheet traceability matrix in the
FS document.

Total test files: **$test_file_count**
Total test functions: **$test_function_count**

The full per-FS-Req test mapping is captured in the FS document's
"Traceability matrix" section. This OQ document records the EXECUTION of
those tests for release $release.

## 3. Test results

> Auto-population of test results is deferred to **TMX-3500e**. For the
> SCAFFOLD v0 release this section is a placeholder.
>
> When TMX-3500e ships, this section will be populated by:
>   `python -m pytest --json-report --json-report-file=results.json tests/`
> followed by the pack builder embedding the per-test outcome (pass /
> fail / skip / xfail / error) in a markdown table.

| Test file | Functions | Pass | Fail | Skip | Run timestamp |
|---|---|---|---|---|---|
| _(auto-populated by TMX-3500e)_ | _-_ | _-_ | _-_ | _-_ | _-_ |

## 4. Test results summary

> Auto-populated by TMX-3500e. Manual sign-off below.

- **Pass rate**: TBD (TMX-3500e)
- **Fail rate**: TBD
- **Skip rate**: TBD
- **Total run time**: TBD

## 5. Traceability cross-reference

Per FS-Req-N traceability is in the FS document's traceability matrix.
The OQ document does not duplicate that matrix; it references it.

For the per-AC -> per-test mapping, see `FS.md` section 5.

## Signatures

- [ ] **QA Lead** ............................. Date: ............ Signature: ............

(QA Lead signs after running the test plan and reviewing the results.
The signature attests that the recorded results are the outputs of an
unmodified run against the qualified installation per IQ.md.)
