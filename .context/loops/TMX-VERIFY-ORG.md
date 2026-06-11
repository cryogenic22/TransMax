# TMX-VERIFY-ORG — Org-wide v2 audit verification endpoint

**State**: `[Done]`
**Owner**: Audit & Validation · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way` — new read-only route + schema.
**Pre-mortem**: if this fails, a regulator can only verify chains one job at a time; an org-wide "is everything intact?" answer requires N calls + client-side aggregation.
**Blast radius**: new `GET /api/v1/audit/verify_v2/org`; `OrgAuditVerificationResponse`/`OrgChainSummary` schemas. Read-only.

**Gates**: G1 PASS (thin adapter over the existing `verify_org_chain`; real value: single org-wide integrity gate; ships with tests). G3 PASS (endpoint returns `all_ok` + per-job verdicts).

## 1. Task
The verifier already exposes `verify_org_chain()` (auto-scoped to `current_org_id()`) but had no HTTP surface. Add a tenant-scoped endpoint returning every chain's verdict + an `all_ok` rollup.

## 2. Spec
- AC-1: two jobs (one clean, one tampered) → `total_chains=2`, `ok_chains=1`, `all_ok=false`, tampered job headlined TAMPERED.
- AC-2: another org's chains excluded from the sweep (tenant scoping).
- AC-3: route registered before `/{audit_id}` so the static path isn't captured.

Out of scope: pagination for very large orgs (noted as a follow-up).

## 3. Design
Wrap `verify_org_chain()`; map each `VerificationReport` to `OrgChainSummary` via the shared `_derive_status` (TMX-3105a). `all_ok = ok_chains == total_chains`. Registered at the top of the router; `/verify_v2/org` (two segments, last="org") cannot match `/{audit_id}` (one segment) or `/{job_id}/verify_v2` (last="verify_v2").

## 4. Code
| File | Change |
|---|---|
| `app/schemas/api_v1.py` | `OrgChainSummary` + `OrgAuditVerificationResponse` |
| `app/api/v1/audit.py` | `verify_v2_org_chains` route |

## 5. Eval / Test
`tests/test_audit_verify_endpoint.py` +2 (rollup+itemise tamper; cross-tenant exclusion) — green.

## 6. Red team
No event-count cap: a very large org verifies all chains in one call (latency). Acceptable for an on-demand regulator action; **spawn TMX-VERIFY-ORG-PAGINATE** if an org crosses ~1k jobs. Route-ordering reasoned through + tested.

## 7. Fix
No findings — clean. Follow-up spawned (pagination).

## 8. Deploy
- [ ] Commit: <SHA> (batch A) · [x] active_tasks updated

## Status log
| 2026-06-11 | — | `[Done]` | new org-wide verify surface |
