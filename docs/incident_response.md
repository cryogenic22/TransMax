# TransMax Incident Response Runbook

**Last updated**: 2026-05-01
**Owner**: TransMax Security & Compliance
**Status**: Stub — to be expanded as v3.0 lands real customers (TMX-3007)

---

## Purpose

A short, opinionated runbook covering the first 60 minutes of a security or production incident. It is intentionally *not* exhaustive — it is the script for the first responder. Detailed playbooks for specific incident classes (data breach, audit-chain tamper detection, LLM provider outage, etc.) will be added as the system grows.

This runbook lives alongside the SECURITY.md responsible-disclosure policy and the per-release Validation Summary Report.

---

## Severity levels

| Severity | Definition | First-response time | Communication cadence |
|---|---|---|---|
| **P0** | Customer data exposed, audit chain tampered, production fully down, regulator-relevant defect detected in production | ≤ 15 min | Every 30 min until contained |
| **P1** | Production degraded for some customers; security control bypassed without confirmed data exposure | ≤ 1 hr | Every 2 hrs until contained |
| **P2** | Internal or staging issue; no customer impact; potential vulnerability reported | ≤ 1 business day | End-of-day |
| **P3** | Cosmetic, low-severity, or hypothetical — file a ticket | n/a | n/a |

---

## First responder script (P0/P1)

When you become aware of a potential incident, execute these steps **in order**. Do not skip ahead.

### 1. Confirm — don't act on a panic

- Reproduce the issue.
- Identify the affected scope: tenant(s), surface(s), time window.
- Check `https://status.transmax.io` (when live; TMX-3902) and the Grafana dashboards.
- If you cannot confirm within 5 minutes, escalate as P0 anyway.

### 2. Declare

- Open an incident channel: `#inc-YYYYMMDD-<short-name>` in Slack.
- Page the on-call engineer (rota in `docs/oncall.md` — to be added).
- Page the security lead if the issue involves auth, audit, PII, PHI, or a regulator-relevant defect.
- Page the Programme Lead (Kapil) for any P0 or any incident with customer-visible impact.

### 3. Contain

For each incident class:

| Class | Containment action |
|---|---|
| Audit-chain tamper detection | Read-only mode for affected tenant; halt new audit appends until cause is known. Do **not** delete or rewrite the chain. |
| Suspected credential leak | Rotate the affected secret(s) via the vault. Revoke leaked tokens. Force re-auth on affected sessions. |
| LLM provider outage | Activate circuit breaker (already in `app/services/resilience.py` — verify). Route to the fallback provider per `app/agents/router.py` (v3.0). |
| PII / PHI exposure to logs | Stop the offending log shipper. Snapshot the logs for forensics. Begin redaction. |
| Mock-data fallback observed in production | Should not happen post-TMX-3004 — but if it does, halt the affected surface immediately. |
| RBAC bypass | Disable the offending role / scope. Force re-auth on all affected sessions. |
| EU AI Act / FDA-relevant defect detected post-shipment | Notify the customer compliance contact within 24 hrs. Do not silently fix. |

### 4. Communicate

- **Internal**: post in `#inc-...` every 30 min for P0, every 2 hr for P1. Time-stamped.
- **Customers**: if customer impact is confirmed, send first notice within **1 hour for P0**, **4 hours for P1**. Do not speculate; state what you know and what you don't.
- **Regulators**: GDPR Article 33 requires breach notification within **72 hours** for confirmed personal-data breaches. HIPAA 60 days for PHI. Loop in legal counsel before any regulator contact.

### 5. Mitigate

Permanent fix. Tested. Reviewed. Released via the normal change-control process unless the change is itself emergency-grade.

### 6. Verify

- Re-run the affected golden-suite eval cases.
- Run `python scripts/ratchet.py check` — no metric should have regressed.
- Run the full pre-release Validation Bundle if the fix touches core (audit, auth, gates).

### 7. Close + Post-mortem

Within 5 business days of P0 resolution. Within 10 business days of P1.

Post-mortem template:
- **Summary** (1 paragraph)
- **Timeline** (UTC, with sources for every entry)
- **Customer impact** (tenants, surfaces, duration, evidence quantified)
- **Root cause(s)** (5-whys, or fishbone for multi-cause)
- **Detection** (what caught it; what should have caught it earlier?)
- **Containment** (timeline + actions)
- **Resolution** (the fix)
- **What worked**
- **What didn't**
- **Action items** (owner, due date, ticket ID)
- **Sign-off** by Programme Lead + Security Lead

Post-mortems live under `docs/post_mortems/YYYY-MM-DD-<slug>.md`. They are blameless — focus on systems, not people.

---

## Specific runbooks (to be expanded)

These are stubs — flesh out as incidents teach us what they need.

- `docs/runbooks/audit_chain_tamper.md` — TBD
- `docs/runbooks/llm_provider_outage.md` — TBD
- `docs/runbooks/credential_leak.md` — TBD
- `docs/runbooks/pii_in_logs.md` — TBD
- `docs/runbooks/database_replica_lag.md` — TBD
- `docs/runbooks/cost_ceiling_breach.md` — TBD (per TMX-3903)

---

## Reference

- Responsible disclosure: `SECURITY.md`
- Privacy notice: `docs/privacy_notice.md`
- v3.0 release plan: `research/v3_pilot_ready_release_plan.md`
- Multi-agent collaboration protocol: `COLLABORATION.md`
- Active backlog / handoff log: `.context/active_tasks.md`, `.context/handoff_log.md`
