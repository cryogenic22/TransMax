# Security Policy

**Last updated**: 2026-05-01
**Owner**: TransMax Security & Compliance

---

## Reporting a vulnerability

If you believe you've found a security vulnerability in TransMax, **please do not open a public issue or pull request**.

Email **security@transmax.io** with:

- A description of the issue
- Steps to reproduce (or a proof-of-concept payload)
- The version / commit / deployment where you observed it
- Your name and how you'd like to be credited (or if you'd prefer to remain anonymous)

We acknowledge every report within **3 business days** and aim to provide a substantive triage within **10 business days**. Critical issues affecting data integrity, audit-trail tamper-evidence, access control, or PII confidentiality are treated as P0 and addressed within **24 hours of triage**.

We will not pursue legal action against good-faith security researchers who:

- Test only on systems they own or have explicit permission to test
- Avoid privacy violations, denial-of-service, or any disruption of TransMax production systems
- Respect the responsible-disclosure window agreed in our reply
- Comply with all applicable laws

---

## Supported versions

| Version | Status | Security fixes |
|---|---|---|
| `main` | Active development | Yes |
| `v3.x` | GA — pilot release | Yes — every release ships a Validation Bundle with a `security-summary.pdf` (see `research/v3_pilot_ready_release_plan.md` Track 4) |
| `v2.x` | Legacy | Critical fixes only, with a 90-day sunset on notice |
| < `v2.0` | End-of-life | No |

Customers on supported tiers receive notice of security advisories via the contact email registered to their tenant.

---

## Scope

In-scope assets for security disclosure:

- The TransMax SaaS at `*.transmax.io` (currently `app.transmax.io`, `api.transmax.io`, future: `review.transmax.io`, `verify.transmax.io`)
- The TransMax Python SDK on PyPI (`transmax-sdk`) once published
- The TransMax MCP server (`transmax_mcp/`) once published
- The `quality-gate/` and harness components in this repo
- Customer evidence bundles (`*.validation-bundle.tar.gz`)

Out of scope (unless the issue clearly affects in-scope assets):

- Vulnerabilities in third-party LLM providers (OpenAI, Anthropic, DeepL) — report directly to those vendors
- Vulnerabilities in Postgres, Redis, AWS S3, AWS KMS, etc. — upstream
- Social-engineering attacks on TransMax staff
- Denial-of-service via volumetric flooding (we have rate limits; testing them at scale is out of scope without prior agreement)
- Reports without a clear security impact (e.g. "missing X-Frame-Options on a docs page" without an exploitable consequence)

---

## What we promise

- We will read every report.
- We will tell you within 3 business days whether the issue is in scope and what we plan to do.
- For confirmed vulnerabilities, we will share a fix timeline and offer credit in a security advisory.
- We will not retaliate against good-faith research.

---

## What we ask

- **Don't access data that isn't yours.** If your testing reveals customer PHI / PII, stop and tell us. Do not download, retain, or share.
- **Don't degrade service.** A single proof-of-concept request is fine; load-testing or stress-testing requires explicit prior approval.
- **Give us a reasonable disclosure window.** Default 90 days from the date we acknowledge the report. We may agree to extend or shorten depending on severity.

---

## Cryptographic primitives we rely on

For transparency, the security-critical primitives in v3.0 are:

- **Audit chain hashing**: SHA-256 over canonical bytes, domain-separated (per `research/v3_pilot_ready_release_plan.md` §6.A). v3.0 ships v2 chain replacing the original concat-hash design (review C-04).
- **Trusted timestamps**: RFC 3161 tokens from FreeTSA. Daily Merkle anchor written to S3 Object Lock (compliance retention).
- **E-signatures**: TOTP 2FA challenge in v3.0; WebAuthn passkeys deferred to v3.1.
- **Password storage**: passlib + bcrypt, work factor 12.
- **JWTs**: HS256 in v3.0 with `SECRET_KEY` from a vault; the platform refuses to start in production with a default `SECRET_KEY` (see `app/core/config.py:assert_production_safe`).
- **Transport**: TLS 1.2+ enforced; HSTS preload; CSP, X-Frame-Options, Permissions-Policy on browser-facing surfaces (TMX-3615).

If you discover a flaw in any of these, please flag it as **Critical**.

---

## Out of scope but disclosed for awareness

- The `.env` file in this repo's history was committed with what appears to be a real OpenAI API key (review C-01). The key was rotated and the file purged from history on **<TODO: date Kapil completes TMX-3000>**. Any commits before that purge that reference `.env` may still appear in upstream forks; we cannot retroactively remove forks.
- Until v3.0 ships, the audit-chain primitives in `app/services/audit_service.py` use a string-concatenation hash that is vulnerable to collision attacks against expert review (review C-04). Do not rely on the chain for tamper-evidence claims until v3.0 ships the v2 ledger.

---

## Contact

- General security questions: **security@transmax.io**
- Press / coordinated disclosure: **press@transmax.io**
- PGP key for sensitive reports: published at `https://transmax.io/.well-known/security.txt` (in flight — see TMX-3007).

Thank you for helping keep TransMax safe.
