# ADR-0002: Secrets management — phase-tiered vault strategy

**Date:** 2026-05-09
**Status:** accepted

## Context

TMX-3001 asked: pick a secrets vault. Live secrets today: `OPENAI_API_KEY`, `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` extras. The OpenAI key was rotated 2026-05-09 (post-TMX-3000 cleanup) and the prior key purged from history.

Constraints:
- **Pilot scale**: 1-3 ICs, single product team, single Railway runtime, single GitHub org.
- **Pharma posture**: secrets-handling must be defensible to a regulator audit, but the bar at pilot scale is "documented + access-controlled + rotated", not "FedRAMP HSM with offline shamir-shared root key".
- **Descope note posture**: managed-service-first means few human consumers of secrets in Phase 1. Self-service onboarding is Phase 2+.

## Decision

**Phase 1 (now): GitHub Actions environments + Railway env vars.** Both already exist in our pipeline. Rotation works. CI uses GitHub Actions secrets; runtime uses Railway env vars. No new tooling.

**Phase 2 trigger**: when *either* (a) the team grows past 3 ICs who need shared local-dev secrets, or (b) a non-Railway environment is added (e.g. an EU data-residency region on AWS or Hetzner), graduate to **1Password Business** (~$8/user/mo) for human consumers.

**Phase 3 trigger**: only if backend moves to AWS for residency, evaluate **AWS Secrets Manager** alongside 1Password (different roles: Secrets Manager for runtime IAM-bound rotation, 1Password for human-consumed credentials).

This decision is small-now-fixed-later by design.

## Consequences

**Better**:
- Zero new ops surface in Phase 1.
- Zero new vendor cost.
- The Phase 2 / Phase 3 triggers are clearly defined, so the upgrade is a one-day decision when the trigger fires, not a months-long debate.

**Worse**:
- Local-dev secret sharing is ad-hoc (whoever needs `OPENAI_API_KEY` locally gets it from Kapil over a secure channel). Acceptable at <3 ICs.
- No automatic rotation. We rotate manually when needed (as we just did with OpenAI).
- No central audit log of "who accessed which secret when". Phase 2 (1Password) gets us this.

**Becomes possible**: re-evaluating in 3-6 months at the Phase 2 trigger without lock-in cost.

**Becomes hard**: nothing currently — the move from env-vars-only to a vault is straightforward.

## Alternatives considered

- **1Password Business in Phase 1**: real value but adds a vendor + monthly cost without a corresponding need today. Defer until trigger fires.
- **AWS Secrets Manager in Phase 1**: would couple us to AWS prematurely. Railway is our runtime today; pulling in AWS just for secrets is over-engineering.
- **Doppler / Infisical / 1Password CLI integrated with Railway**: viable Phase 2 alternatives. Will revisit at trigger time. No reason to pick a Phase 2 winner today.
- **HashiCorp Vault**: industry-grade but operationally heavy. Not Phase 1 sized.

## Affected teams / surfaces

- `.github/workflows/*.yml` — already use `${{ secrets.* }}`; unchanged.
- `app/core/config.py` — already uses `os.getenv`; unchanged.
- Railway service env-vars dashboard — operational owner: Kapil.
- `parking_lot/deferred_features.md` — adds the Phase 2 / Phase 3 trigger record so the upgrade decision isn't forgotten.
