# TransMax — Agent instructions

This file is the AGENTS.md convention used by Cursor, OpenAI Codex, and other autonomous coding agents. The content mirrors `CLAUDE.md`; refer to that file as the single source of truth.

If your agent reads `AGENTS.md` but not `CLAUDE.md`, the binding content is below.

---

## Tier 0 — Entropy

> Every change either fights entropy or feeds it. Default is feeding. Choose.

Before every commit: *am I leaving a broken window?* If yes, fix it now or open an explicit ticket.

For TransMax, "entropy" is the gap between what the code claims (audit chains, regulatory profiles, quality gates) and what survives a pharma CSV review. Closing that gap is v3.0.

---

## Tier 1 — Always-on principles

Full skill at `.claude/skills/design-philosophy/SKILL.md`. Condensed:

**Design:** deep modules · information hiding · pull complexity downward · define errors out · different layer different abstraction.
**Process:** don't live with broken windows · tracer bullets · reversibility · crash early · DRY · good enough.
**Discipline:** think before coding · simplicity first · surgical changes · goal-driven execution.
**Cross-cutting:** design twice · refactor mercilessly · design by contract · test ruthlessly · code is read 10× more than written.

---

## Tier 2 — Pre-commit self-review

Run the 22-item red-flag checklist in `design-philosophy/SKILL.md` before every commit.

---

## Mechanical gates

`kp-sdlc` quality-gate + transmax ratchet run at PreToolUse, pre-commit, and CI. See `CLAUDE.md` for the full pipeline diagram.

---

<!-- project-specific -->
## TransMax-specific addenda

The 10 addenda (A1–A10) live in `CLAUDE.md`. They are normative; both agent runtimes must apply them identically. In summary:

- **A1** Audit-by-default — every state change emits an audit event before side effects.
- **A2** Quality at gates, not in translate — deterministic gates catch defects, LLMs only translate.
- **A3** No silent fallbacks in regulated paths — fail loud; never substitute mocks for real data.
- **A4** Don't deepen the dual-model-layer divergence — `database.py` vs `translation.py`.
- **A5** Stable IDs end-to-end — `segment_id` / `doc_id` / `audit_event_id` are sources of truth.
- **A6** LLMs are qualified suppliers — every call records provider/model/version/prompt-version.
- **A7** One canonical IA: `/workspace/*` — don't add top-level routes.
- **A8** Pin every prompt to a version — versioned YAML registry.
- **A9** Soft-delete only — no `DELETE FROM`; tombstones preserve the chain.
- **A10** `.context/` is the program brain — read at session start, update at session end.

Read `CLAUDE.md` for the full text and the "known issues you must not silently work around" list.

---

## Loop discipline — the three gates

Every non-trivial ticket runs 8 stages in a worksheet at `.context/loops/TMX-XXXX.md`
(template: `_template.md`): Task → Spec → Design → Code → Eval/Test → Red team → Fix → Deploy.
The worksheet header carries **reversibility** (`one-way` routes to human approval before stage 4),
a one-line pre-mortem, and blast radius. All three are required before any code is written.

Three gates are non-negotiable:

- **G1 anti-bloat** — before ANY net-new code path, answer five questions: functional depth,
  end-user value, trust, robustness, stability. If all five are "no", don't write it. Prefer
  extending an existing module over adding one. *"Defensive abstraction", "future-proofing",
  "just in case", "while I'm here"* all fail this gate.
- **G2 reproduce-the-failure** — for any ticket reporting a user-visible failure, reproduce it as a
  **red test before the fix lands**. A test that documents a bug without changing the code that
  fixes it is `[Blocked]`, never `[Done]`.
- **G3 completion** — did this commit change source that addresses the failure, and would a repro
  now pass? If either is no, the status is `[Blocked]` with a runbook.

**Push hygiene:** a ticket is `DONE` only when its SHA is on `origin/main`. "Done pending push" is
not a state. Run `python scripts/audit_worksheet_drift.py` before closing a sprint.

**Cross-repo work** (anything touching `Scriptiva_SCA`/reSCApe) additionally follows
`.context/loops/CROSS-REPO-PROTOCOL.md` and ADR-0009. Both repos' locks apply, strictest wins.

---

## Reviewer mode

If you are invoked to **review** rather than to write, this section is your brief. Review against
what this program actually promises, not against generic style.

**What you are looking for, in priority order:**

1. **Unearned claims (A3 / "no vacuous green").** This is the house defect and it has recurred four
   times. A provenance, quality or compliance value must be *derived from the artefact that produced
   it* — a prompt hash, a chain entry, a signature record, a live posture read. Flag anything
   stored as a string, defaulted, hardcoded, or surviving a fallback path while still being
   presented as real. Known instances to pattern-match against: a compliance panel rendering
   fabricated posture; a timestamp advanced without the work being redone; a `mode` label kept
   across a degraded fallback; a placeholder emitted when no provider is configured.
2. **Silent failure.** A field accepted and never acted on. An exception swallowed into a default.
   A gate that passes because it was skipped. In regulated paths, fail loud or fail closed — never
   substitute.
3. **Gate violations.** Net-new code that fails G1. A bug fix with no red test (G2). A `[Done]`
   whose diff contains only tests (G3).
4. **Addenda violations** — A1–A10 above, cited by ID.
5. **Single-source-of-truth forks.** Two registries describing the same thing. Six are already known;
   do not add a seventh.
6. **Tier-2 red flags** — the 22-item checklist.

**How to report:** one finding per row, each with a `file:line` anchor, a concrete failure scenario
(inputs → wrong output), and a severity. Distinguish **CONFIRMED** (you traced it) from
**PLAUSIBLE** (it looks wrong but you did not verify). State explicitly when you checked a claim and
found it *correct* — a refuted finding is as valuable as a confirmed one, and this program records
corrections rather than silently rewriting them.

**Do not:** propose refactors that fail G1, restate style preferences the linters already enforce,
or mark something a defect without a failure scenario.
