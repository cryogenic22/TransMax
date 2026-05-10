---
document_type: IQ
title: Installation Qualification - TransMax
release: $release
version: 1.0.0
generated_at: $generated_at
generator: regulatory_pack.generators.pack_builder (TMX-3500)
signed_by: []
traceability_keys:
  - environment
  - ratchet_metric
---

# Installation Qualification (IQ)

**Release:** $release
**Generated:** $generated_at
**Document type:** IQ (Installation Qualification)
**Standard:** GAMP 5 + EU Annex 11 + 21 CFR Part 11

> **STATUS:** Scaffold v0. The environment matrix and ratchet metrics are
> auto-pulled from `ratchet/baseline.json` and the running Python.
> Signatures are empty - the Platform Lead signs at deployment.

## 1. Scope

Installation Qualification proves the TransMax system installs into its
target environment correctly and matches the documented configuration. IQ
is performed once per release per environment (dev, staging, pilot,
production). This document captures the IQ for release **$release**.

## 2. Environment matrix

The reference environment for this release:

$environment_matrix

## 3. Code-quality posture (ratchet metrics)

The ratchet system (TMX-2026-05-01) enforces monotonic improvement on 17
metrics. The IQ-relevant snapshot for this release:

$ratchet_metrics

These metrics are the IQ-side guarantee that the build artefact has not
regressed against the documented baseline. Any IQ run with a regression
fails the "Code-quality posture" criterion.

## 4. Installation verification steps

For each environment in section 2, the following steps must execute
cleanly with documented outputs:

1. **Backend dependencies installed** - `pip install -r requirements.txt`
   exits 0; no version resolution warnings beyond the documented set.
2. **Frontend dependencies installed** - `cd frontend && npm install`
   exits 0; lockfile unchanged.
3. **Database migrations applied** - `alembic upgrade head` exits 0;
   schema state matches `alembic/versions/` head SHA.
4. **Smoke test passes** - `./scripts/check.sh` exits 0 (lint +
   typecheck + test + build).
5. **Foundation suite passes** - `pytest tests/test_organizations_model.py
   tests/test_organization_fk.py tests/test_soft_delete.py
   tests/test_audit_events_v2_schema.py tests/test_tenant_session.py` -
   43/43 green.
6. **Ratchet check passes** - `python scripts/ratchet.py check` - exits 0.
7. **Worksheet drift check passes** - `python scripts/audit_worksheet_drift.py`
   - exits 0.

## 5. Signatures

- [ ] **Platform Lead** ........................ Date: ............ Signature: ............

(Platform Lead signs because IQ is an environment / deployment
qualification, owned by the Platform & Observability pod.)
