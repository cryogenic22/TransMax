<!--
Bootstrapped from kp-sdlc/harness on 2026-05-01. Edit freely.

Required sections: Spec, Summary, Verification, Self-review.
The CI quality job's `process guardrails` step will fail if any are missing.
-->

## Spec

Implements `TMX-NNNN` from `.context/active_tasks.md` (or link to issue / ADR / `research/v3_pilot_ready_release_plan.md` epic). One sentence on which acceptance criteria this PR satisfies; cite specific AC numbers if relevant.

## Summary

Two to four bullets describing what changed and why. Avoid restating the diff. Focus on motivation and the resulting behaviour.

- ...
- ...

## Assumptions

What did this PR take for granted that a reviewer might want to challenge? Be honest about uncertain calls. If none, write "None".

## Non-goals

What this PR explicitly does not do. Useful when the change is part of a larger sequence (e.g. v3.0 sprint slice 3 of 6).

## TransMax-specific addenda check

Walk the addenda from `CLAUDE.md` (A1–A10). Tick those this PR touches:

- [ ] A1 — Audit-by-default (every state change emits an audit event)
- [ ] A2 — Quality at gates, not in translate
- [ ] A3 — No silent fallbacks in regulated paths
- [ ] A4 — Doesn't deepen dual-model-layer divergence
- [ ] A5 — Stable IDs end-to-end
- [ ] A6 — LLMs are qualified suppliers (provider/model/version recorded)
- [ ] A7 — One canonical IA `/workspace/*`
- [ ] A8 — Prompt versions pinned
- [ ] A9 — Soft-delete only
- [ ] A10 — `.context/` updated where relevant

## Validation pack delta (v3.0+)

Once E3 lands, every PR records its validation-pack delta:
- URS / FS / DS / RA / OQ entries created or modified: …
- RTM update needed: yes / no
- Affects audit ledger / e-signature / regulatory profile / language pack: …

Until E3 lands, this section is informational.

## Verification

How can a reviewer convince themselves this works?

- [ ] Tests added or updated (cite paths)
- [ ] Manual check (describe steps)
- [ ] CI passes (link the run when available)
- [ ] Ratchet stays green (`python scripts/ratchet.py check`)
- [ ] Quality gate stays green (`python quality-gate/quality_gate.py --staged`)
- [ ] Eval harness updated if defect taxonomy or QRD validators changed (`pytest tests/evals/`)

## Self-review (Tier 2 red flags)

Walked the 22-item checklist in `.claude/skills/design-philosophy/SKILL.md` Tier 2. Summary:

- **PASS:** ... (count or list)
- **N/A:** ... (structurally inapplicable)
- **FIXED:** ... (caught and fixed during review — list each)
- **JUSTIFIED:** ... (applies but deliberate — one line per)

If you skipped Self-review (e.g. typo PR), say so and why in one line.

## Linked dependencies / DEPs

`.context/active_tasks.md` rows opened, advanced, or closed by this PR (if any). Or "None".
