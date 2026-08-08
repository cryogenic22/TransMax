# TMX-AUTH-AUDIT — audit access-control changes

**State**: `[Done]` · **Owner**: Auth & Tenancy · **Sprint**: Phase 0 (honesty)
**Reversibility**: `two-way`. **Pre-mortem**: a structured log is weaker than an immutable chain (chain follow-up tracked). **Blast radius**: `app/api/auth.py` `update_user_role` (+ logger).

**Gates**: G1 ✓ (closes a direct A1/A12 finding; minimal, additive) · G2 ✓ (audit found `update_user_role` emits nothing) · G3 ✓ (a role change now emits an audit record).

## 1–3. Task / Spec / Design
The audit (A12) found `update_user_role` mutates a role and commits with no audit event — violating "access changes audited" (A1/A12). The v1+v2 chains are job-scoped, so a job-less access change cannot use them yet (the same constraint `routing_policy_service` documents). Emit a structured `ACCESS_CHANGE` audit log with actor + target + old→new role. AC-1: a role change emits a structured audit record capturing actor/target/old/new. Out of scope: the immutable system-level chain → **TMX-AUTH-AUDIT-CHAIN** (needs a job-less audit trail); also login/register audit.

## 4. Code
`app/api/auth.py`: `+import logging` + module `logger`; `update_user_role` captures `old_role` and emits `ACCESS_CHANGE` after commit.

## 5. Test
Verified via import smoke + existing auth suites green; the structured log emits on a real role change (integration/manual — a logger-line assertion needs the full endpoint harness, tracked under the chain follow-up).

## 6–7. Red team / Fix
Risk: log without chain = not tamper-evident — honest interim matching codebase precedent; follow-up filed. Risk: logging the new role before commit success — emitted AFTER commit. No findings.

## 8. Deploy
- [x] Commit: `737993c` (batched: "TMX-MQM-5c/BB-STRICT/AUTH-AUDIT: profile resolution + enforce strict rules + audit access") · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | access changes now audited (structured log) |
