# ADR-0003: Auth provider — Auth0 for Phase 1

**Date:** 2026-05-09
**Status:** accepted

## Context

D-3 asked: Auth0 vs Keycloak vs Descope. The descope note (`TRANSMAX_DESCOPE_NOTE.md`, May 2026) sets the posture for Phase 1:

- **Managed-service-first** (§4.1): 2-4 large pharma engagements per year, ZS-mediated.
- **Embedded-first** (§4.2): UI is the demo, not the product. UI investment = consistency + reliability, not novel UX.
- **§5.1 #1** non-negotiable: "Auth on by default; SECRET_KEY enforced; OpenAI key rotated and removed from git history".
- Customer auth surface is the customer's corporate IdP — Azure AD, Okta, Ping, ADFS. We need SAML + OIDC, not username/password.
- Pilot fees are €25-75k each; auth provider monthly cost is rounding error.

Time-to-pilot dominates over total cost.

## Decision

**Auth0 (B2B tier) for Phase 1 of TransMax.** Customer-facing auth is OIDC + SAML against the customer's corporate IdP. Auth0 is the broker. We expose only OIDC standards downstream so we can swap the broker later without re-integrating customers.

Phase 1 surfaces:
- Auth0 tenant: `transmax-pilot.us.auth0.com` (tenant name TBD)
- Login page: hosted Auth0 universal login, branded to TransMax (Loop 17 supplies the brand mark)
- Backend: `app/api/auth.py` validates Auth0-issued JWTs against the JWKS endpoint; existing `auth_mode` config switches between `none` (dev) and `oidc` (production)
- SCIM v2 for user provisioning from customer IdP (Phase 1.5 — not first pilot)
- HIPAA BAA available out of the box for the regulated customer subset.

## Consequences

**Better**:
- Time-to-pilot < 1 week vs 4-6 weeks for Keycloak.
- Pre-built corporate IdP connectors: Azure AD, Okta, Ping, ADFS, Google Workspace.
- SOC 2 Type II + ISO 27001 + HIPAA BAA + GDPR DPA documents pre-existing — we point at supplier compliance instead of building our own.
- MFA, anomaly detection, breach passwords detection, brute-force protection, audit logs — all included.
- Customer can SSO from their existing IdP without us writing SAML XML wrangling.

**Worse**:
- Vendor lock-in (mitigated: we expose only OIDC standards, never Auth0-specific APIs in our code).
- ~$240/mo for B2B at 1k MAU (rounds to nothing against pilot fees).
- One more SaaS vendor in the supplier register; one more compliance attestation (Auth0 SOC 2) to keep current.

**Becomes possible**:
- Pilot customer SSO live in days.
- Reviewer accounts gated behind customer IdP — their security team is comfortable.
- Custom domain (`auth.transmax.io`) after pilot to reduce Auth0 brand exposure.

**Becomes hard**:
- "Self-host everything" pharma customer (rare in pilot phase) needs us to point at a Keycloak fallback. Sister ADR if this comes up.

## Alternatives considered

- **Keycloak (self-hosted)**: free; full customisation; preferred by pharma customers asking for residency or zero-vendor-dependency. Rejected for Phase 1 because: (a) 4-6 weeks ops setup, (b) we run it (one more uptime surface), (c) compliance attestations are now ours to write. Re-evaluate in Phase 2 if a pilot specifically asks for self-hosted.
- **Descope**: dev-friendly, generous free tier, B2B SSO. Rejected for Phase 1 because: (a) smaller company, less enterprise track record, (b) pharma security review tends to scrutinise vendor age + customer list — Auth0 wins here. Re-evaluate in Phase 2.
- **Build it ourselves on FastAPI + python-jose**: existing `app/api/auth.py` already does JWT issuance. Rejected because we then own SAML, MFA, breach detection, audit logging, brute-force protection. Months of work. Not Phase-1 sized.
- **AWS Cognito**: viable but couples us to AWS prematurely (see ADR-0002). Re-evaluate if we move to AWS.

## Affected teams / surfaces

- `app/api/auth.py` — JWT validation now points at Auth0 JWKS in production
- `app/core/config.py` — `auth_mode` config; Auth0 tenant/audience env vars
- `frontend/lib/auth.tsx` — login flow uses Auth0 universal login redirect
- `frontend/middleware.ts` — already checks `transmax_token` cookie; cookie source becomes Auth0
- `.github/workflows/ci.yml` — Auth0 tenant configured per environment
- Loop 17 (TMX-3601): brand mark + colour palette flow through to Auth0 universal login customisation
- TMX-3013 (Pod A): unblocked by this ADR — they can now wire Auth0 in the backend and lib/auth.tsx
- Customer onboarding playbook (managed-service-first): SSO setup is part of Day-1 customer enablement
