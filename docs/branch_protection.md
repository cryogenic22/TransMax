# Branch Protection Settings

**Last updated**: 2026-05-01
**Owner**: Programme Lead
**Status**: Reference doc — apply settings in GitHub repo Settings → Branches → Branch protection rules.

---

## Why this exists

Per v3.0 plan TMX-3009 / review §10.2: "trunk-based development with signed releases; every PR carries a ticket ID and an AC checklist; mechanical guardrails gate the merge." This file specifies the exact GitHub branch-protection rules that enforce that mechanically.

GitHub branch protection isn't checked into git, so this doc is the source of truth. When applying or auditing the settings, walk this list in the GitHub UI.

---

## `main` branch — required settings

### Restrict who can push

- ✅ **Require a pull request before merging**
  - ✅ Require approvals: **1** (Phase 1) → 2 (Phase 2 once team grows)
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (uses `.github/CODEOWNERS`)
  - ✅ Require approval of the most recent reviewable push
  - ❌ Allow specified actors to bypass required pull requests (no bypasses)

### Required status checks (must pass before merge)

All workflows in `.github/workflows/` must be green. Required:

- ✅ `TransMax CI / Unit Tests` (`ci.yml`)
- ✅ `Quality Gate / Code Quality` (`quality.yml`)
- ✅ `ratchet / Ratchet check (no metric may regress)` (`ratchet.yml`)
- ✅ `eval / Golden eval suite` (`eval.yml`)
- ✅ `secret-scan / gitleaks` (`secret-scan.yml`)
- ✅ `second-pass-reviewer / second-pass-reviewer` (`second-pass-reviewer.yml`) — once a Claude API key is added to the repo secrets

Mark **Require branches to be up to date before merging** as well, so a PR that's been queued past a base-branch change has to re-run before merge.

### Other gates

- ✅ Require signed commits (Phase 2; defer until pilot signs and SLSA work lands TMX-3505)
- ✅ Require linear history
- ✅ Include administrators (no bypasses, even for the Programme Lead)
- ✅ Restrict force pushes (`Restrict who can push to matching branches` — keep empty)
- ✅ Restrict deletions
- ❌ Allow force pushes (off; the only legitimate force push is during the one-time TMX-3000 history purge, gated on Programme Lead approval)
- ❌ Allow deletions (off)

### Auto-cancel stale workflow runs

Configured in each workflow file via the `concurrency:` block; no GitHub-level setting needed.

---

## Tag protection

Apply the rule "Require admin to push tags matching `v*`" so only the Programme Lead (or a release-bot) can publish a release tag.

---

## Repository-level settings

### Issues / Pull requests

- ✅ Allow squash merge (default)
- ✅ Require linear history
- ❌ Allow merge commits (keeps history clean for the validation pack)
- ❌ Allow rebase merging (can be turned on later)
- ✅ Auto-delete head branches after merge

### Security & analysis

- ✅ Dependency graph: enabled
- ✅ Dependabot alerts: enabled
- ✅ Dependabot security updates: enabled
- ✅ Code scanning: GitHub Advanced Security (when Org plan supports it) + the SARIF uploaded by `secret-scan.yml`
- ✅ Secret scanning: enabled
- ✅ Push protection: enabled (rejects pushes containing detected secrets at the server)

---

## Enforcement check

The Programme Lead reviews these settings monthly. The audit lives in `.context/handoff_log.md` with a line like:

```
2026-05-01: Branch-protection audit — all settings in docs/branch_protection.md verified. Pending: signed-commit requirement (TMX-3505).
```

---

## Why some checks are deferred

- **Signed commits**: requires every contributor to set up GPG / SSH signing. Phase 1 has 8 engineers; we'll burn time fighting tooling. Cosign-signed *releases* (TMX-3505 → v3.1) ship the tamper-evidence story without forcing per-commit signing.
- **Required reviewers = 2**: Phase 1 is one Programme Lead + a handful of pod owners. Two reviewers is a Phase 2 expectation.
- **Second-pass-reviewer**: requires `ANTHROPIC_API_KEY` in repo secrets. Set up when you're ready to enable that workflow (TMX-3009 follow-up).
