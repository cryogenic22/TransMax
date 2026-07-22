<!-- loop-driven-dev: this project follows the loop-driven-development discipline.
     Bootstrapped from kp-sdlc/harness on 2026-05-01; aligned with the
     loop-driven-dev skill (~/.claude/skills/loop-driven-dev/) on 2026-05-09.
     Loop infrastructure lives at .context/loops/ (per-ticket worksheets),
     .context/active_tasks.md (backlog), scripts/ratchet.py (anti-bloat
     enforcement), tests/evals/ (eval harness), docs/decisions/ (ADRs).
     Programme Operating Principles + Backend Integrity & Anti-Bloat are
     encoded below in §"Loop discipline (any-session contract)". -->

# TransMax — Claude Code instructions

Last bootstrapped from `kp-sdlc/harness` on `2026-05-01`. Aligned with `loop-driven-dev` skill on `2026-05-09`. Edit freely; mark project-specific sections with `<!-- project-specific -->`.

---

## Loop discipline (any-session contract)

**Read this first.** Any Claude Code session opening this repo MUST follow this contract. The loop-driven-dev skill (`~/.claude/skills/loop-driven-dev/`) is the authority; this section is the project-local mapping.

### The unit of work is the loop

Every non-trivial ticket runs through 8 stages, captured in a worksheet at `.context/loops/TMX-XXXX.md` (template at `.context/loops/_template.md`):

1. **Task** — restate the ticket; blast radius; addenda at play
2. **Spec** — falsifiable acceptance criteria (AC-1, AC-2, …)
3. **Design** — approach + alternatives considered + rejected; ADR if non-obvious
4. **Code** — surgical edits; file:line table
5. **Eval / Test** — captured run output for tests + ratchet
6. **Red team** — Tier 2 22-item checklist + A1-A10 audit; cross-pod review request when applicable
7. **Fix** — anything red-team surfaced
8. **Deploy** — commit (with Self-review block), push, update `.context/active_tasks.md`

A ticket is **done** only when stage 8 closes. Skipping stages is broken-window territory (Tier 0). Multi-agent coordination uses the worksheet's `Owner:` field as the lock.

### The three gates (skill-canonical; non-negotiable)

Before marking any ticket `[Done]`, the loop must clear three gates:

**Gate 1 — Anti-bloat / value gate.** Before adding ANY net-new code (endpoint, service, table, model, enum value, component, dependency), answer five questions:
1. **Functional depth** — does it deliver capability a real user will exercise?
2. **End-user value** — does it raise value: clearer task, faster path, safer outcome?
3. **Trust** — does it strengthen a visible audit signal, compliance gate, or provenance?
4. **Robustness** — does it remove a failure mode, defend an invariant, harden a boundary?
5. **Stability** — better tests of REAL behaviour, better observability, better recovery?

If the answer to ALL FIVE is no, **don't add the code**. Pick a smaller change OR escalate to `[Blocked]` with `human_decision_needed`. Anti-pattern signals that fail the gate: *"defensive abstraction"*, *"future-proofing"*, *"just in case"*, *"while I'm here"*.

**Gate 2 — Reproduce-the-failure gate.** For any ticket reporting a user-visible failure (500 error, broken button, wrong number, blank page, regression), the loop MUST reproduce that failure mode in code/test/curl BEFORE claiming a fix. Tests that document failure without changing the code that fixes it are NOT a completed ticket — they are at best `[Blocked]` need-more-info escalations.

The canonical anti-pattern this gate prevents: shipping CI smoke tests for an endpoint that returns 500, marking the ticket "Done", and leaving the user-visible 500 in production. **Never repeat this.**

**Gate 3 — Completion gate.** Before flipping a worksheet to `[Done]`:
1. Did this commit change source code that addresses the user-visible failure mode? (Adding tests is not changing source code.)
2. Would a curl/UI repro of the original failure now succeed?

If either is no, status MUST be `[Blocked]` with a runbook in the worksheet's status log, NOT `[Done]`. Duplicate-close paths must cite the canonical commit SHA AND verify the canonical fix actually resolves THIS ticket's failure mode, not just shares keywords.

### Periodic verification — 4-agent audit (run every ~10 cycles or weekly)

After ~10 closed worksheets, run the 4-agent verification audit. Spawn 4 parallel `Agent` tool calls:

1. **Code-quality + anti-bloat audit** — reviews the last N commits against the five-test rubric, modularity, file-size hygiene, test discipline, backend integrity. Output: `docs/audit-extracts/loop-quality-review-<DATE>.md`.
2. **Backend test + endpoint smoke** — runs pytest, captures pass/fail/skip, smokes endpoints. Output: `docs/audit-extracts/loop-pytest-report-<DATE>.md`.
3. **Frontend test + type health** — runs vitest + tsc --noEmit, surfaces TypeScript drift. Output: `docs/audit-extracts/loop-vitest-report-<DATE>.md`.
4. **Spec-vs-delivery audit** — for each shipped ticket, compares worksheet ACs vs commit content. Verdicts: Match / Partial / Drift / Tests-only (anti-pattern). Output: `docs/audit-extracts/loop-spec-compliance-<DATE>.md`.

Generate the prompts via `bash ~/.claude/skills/loop-driven-dev/scripts/verify-audit.sh`. Decisions:
- **Green across all four**: keep going, archive reports
- **Yellow on test runners**: file `audit-test-coverage-cleanup` ticket
- **Yellow on spec-vs-delivery**: tighten ticket schema or worksheet ACs
- **Red anywhere**: PAUSE the loop, investigate, fix root cause

### Ticket schema (worksheet `.context/loops/_template.md`)

Beyond the 8 stages above, every worksheet header carries:

- **Reversibility**: `one-way` (auto-routes to human approval — schema migrations, public-API shape changes, destructive ops) or `two-way` (the loop ships).
- **Pre-mortem** (1 line): *"if this fails in production, the failure mode is …"*
- **Blast radius** (1-2 lines): which files / surfaces / pods / users this touches.

These three lines are required before stage 4 (Code) starts. They turn the spec into a falsifiable contract with the reviewer.

### Structural-discipline principles (skill-canonical)

In addition to TransMax's A1-A10 addenda below:

- **Backend integrity is paramount.** Data-model and lifecycle invariants don't change casually. DB-schema changes need written justification in the worksheet stage 3 design. (Reinforces A4.)
- **Engine first, surface second.** Don't change the data model. Rebuild the surface. New work composes ON the engine, never replaces it.
- **Config not branching.** Hardcoded chains like `if domain == "X"` in handlers belong in a registry/config. Open-for-extension.
- **Single source of truth.** When two registries describe the same thing, pick one canonical and have others derive from it. Never fork. (Reinforces the TMX-3017 rationalisation imperative.)
- **Tests over coverage.** Don't add a test just to ratchet coverage. Add it because the behaviour is real, the failure matters, and a future regression is plausible. Synthetic / coverage-padding tests are bloat.
- **Coverage floor only ratchets up.** After a green run shows higher coverage, raise the floor. Never lower. (See `scripts/ratchet.py`.)
- **Backwards-compatible API additions only.** Frontend lifts onto new shapes; never break existing endpoints. Use `v2` routes when shape must change.
- **Per-tenant feature flags for any UI-altering change.** Pilot tenant on, others unchanged.
- **Trust signals are not optional chrome.** Render hash / policy snapshot / AI-budget posture / verified-state badges visible everywhere a regulator might look.

### Operate-mode menu (any session)

When opening a fresh session on this repo, ask the user one of:

| Intent | Action |
|---|---|
| Process the next ticket | Read `.context/active_tasks.md`; pick highest-priority `[READY]`; create worksheet from `.context/loops/_template.md`; run the 8 stages. |
| Triage / plan | Read backlog; propose a batch with dependency ordering; wait for "go". |
| Run verification audit | `bash ~/.claude/skills/loop-driven-dev/scripts/verify-audit.sh` — copy the 4 prompts into 4 parallel `Agent` tool calls. |
| Continue an in-flight worksheet | Read the worksheet's status log; resume at the last filled stage. |
| Status / dashboard | Summarise `.context/active_tasks.md` + recent `.context/loops/*.md` headers + `git log --oneline -10`. |

### End-of-loop and end-of-sprint push hygiene

Codified after the 2026-05-09 audit found ~30 worksheets stuck at `[Done, pending commit + push]`. Drift between worksheet claims and `origin/main` is a Tier 0 entropy hit (A10) — a fresh clone cannot reproduce the claimed state, CI never validates, and the audit chain becomes a paper exercise.

1. **Per loop**: stage 8 closes only when the commit SHA is on `origin/main`. `[Done]` requires the SHA to be pushed, not just committed locally. The deploy-stage table must record the SHA in a structured line (`Commit: <sha>`) so the drift audit can resolve it.
2. **End of sprint**: run `python scripts/audit_worksheet_drift.py` (read-only, exits non-zero on drift). Any `LOCAL-ONLY` / `MISSING-COMMIT` / `STALE-STATE` verdict blocks sprint close — fix or escalate before flipping the sprint.
3. **Stale work-in-progress**: any worksheet stuck at `[WIP]` / `[Verify]` for >7 days must either close, escalate to `[Blocked]` with a status-log reason, or move to `parking_lot/`. Indefinite WIP is invisible drift.

Drift script also runs as an advisory pre-commit hook (`drift-audit-advisory`) — warn-only, does not block local commits.

4. **Worktree-vs-`origin/main` drift**: a sister script `python scripts/audit_worktree_clean.py` flags the case where the local working tree silently reverts shipped code (e.g. a re-introduced `DEFAULT_ORG_ID` literal). Runs as the advisory pre-commit hook `worktree-clean-advisory`. Spawned by TMX-CORRECTIVE-20260511 after the 2026-05-11 verify-audit found 2 false-red regressions caused by a dirty worktree the audit's pytest couldn't distinguish from a real regression.

### Where to look first

| What | Where |
|---|---|
| Backlog | `.context/active_tasks.md` |
| Per-ticket worksheets | `.context/loops/TMX-XXXX.md` |
| Worksheet template | `.context/loops/_template.md` |
| Loop board protocol | `.context/loops/README.md` |
| ADR template | `docs/decisions/_template.md` |
| Verification audit reports | `docs/audit-extracts/loop-*-<DATE>.md` |
| Ratchet metrics | `ratchet/baseline.json`, `scripts/ratchet.py` |
| Eval harness | `tests/evals/` |
| Quality gate | `quality-gate/`, `.pre-commit-config.yaml` |
| Skill source | `~/.claude/skills/loop-driven-dev/SKILL.md` (+ `docs/`) |

---

## Tier 0 — The meta-principle

> Every change either fights entropy or feeds it. Default is feeding. Choose.

Codebases drift toward incoherence unless an active force pushes the other way. Before every commit ask: *am I leaving a broken window?* If yes, fix it now or open an explicit ticket.

For TransMax specifically, "entropy" is the gap between what the code claims (audit chains, regulatory profiles, quality gates) and what it can actually defend in front of a pharma CSV team. Closing that gap is the entire job of v3.0.

---

## Tier 1 — Always-on principles

The full skill is at `.claude/skills/design-philosophy/SKILL.md` — read it once per session. The condensed list:

**Design (Ousterhout):** deep modules · information hiding (no leakage) · pull complexity downward · define errors out of existence · different layer different abstraction.

**Process (Pragmatic):** don't live with broken windows · tracer bullets · reversibility · crash early · DRY · good enough software.

**Discipline (Karpathy):** think before coding · simplicity first · surgical changes · goal-driven execution.

**Cross-cutting:** design twice · refactor mercilessly · design by contract (types/asserts/schemas) · test ruthlessly · code is read 10× more than written.

---

## Tier 2 — Pre-commit self-review

Run the 22-item red-flag checklist (in `design-philosophy/SKILL.md`) before every commit. If any flag applies, fix it or document why it doesn't.

The pre-commit hook `red-flag-attestation` will prompt for this. The CI `second-pass-reviewer` job runs the checklist independently against the diff.

---

## Mechanical gates (already in pipeline)

The `kp-sdlc` quality platform plus the transmax-specific ratchet runs at three points:

| When | What | Where it lives |
|---|---|---|
| `PreToolUse` (Edit/Write) | JIT inject relevant principle subset | `.claude/settings.json` |
| Pre-commit | ruff, format, mypy, QG (PRS ≥ 85), red-flag attestation, **ratchet check** | `.pre-commit-config.yaml` |
| CI on PR | All of the above + tests + coverage + bundle size + second-pass reviewer + **eval harness** + **ratchet** | `.github/workflows/` |

Mechanical rules don't need agent attention to enforce — they survive any context state.

---

## Tooling commands

```bash
# One-command setup / smoke
./scripts/setup.sh        # install deps, hooks, migrations
./scripts/check.sh        # lint + typecheck + test + build (smoke)

# Quality gate (PRS scoring, static rules, AI/LLM/prompt packs)
python quality-gate/quality_gate.py --root .

# Quality gate, scoped to staged files (used by pre-commit)
python quality-gate/quality_gate.py --staged

# Ratchet — measure + compare against baseline (CI gate)
python scripts/ratchet.py check
python scripts/ratchet.py update     # writes a new baseline (PR-reviewed)

# AI eval harness (golden translation cases through LangGraph)
pytest tests/evals/ -v
python -m tests.evals.runner --report-json eval_results/latest.json

# Backend tests
pytest tests/

# Frontend
cd frontend && npm test               # vitest unit
cd frontend && npm run e2e            # playwright e2e
cd frontend && npm run typecheck
cd frontend && npm run lint
```

---

## Slash commands available

- `/principles` — print Tier 0 + Tier 1 reminder
- `/review` — run Tier 2 red-flag checklist on the current diff
- `/entropy-check` — explicit broken-window scan
- `/before-i-commit` — full pre-commit attestation walkthrough

---

<!-- project-specific -->
## TransMax-specific addenda

These addenda layer ON TOP of the always-on principles above and never replace them. They are referenced by ID (`A1`, `A2`, …) in code review.

### A1. Audit-by-default

Every state change in the translation pipeline emits a chained audit event before any external side effect (DB write, file write, LLM call). If you find code that mutates state without an audit event, that is a Tier 2 red flag.

The audit chain is the strongest single asset in TransMax. It is also cryptographically weak today (see `tech_debt.md` C-04, C-05). Until v3.0 ships the audit ledger v2 (domain-separated chained hashing + S3 Object Lock anchor + per-event UTC timestamps), assume the chain is *evidence-only*, not yet *defensible*. Don't claim Part 11 compliance.

**Why:** This is what differentiates us from Phrase / Smartling / DeepL. It is also the thing a pharma reviewer will scrutinise hardest.

**How to apply:** when adding a new state transition, write the audit event first, then the side effect. If you can't write the audit event, you don't yet understand the change.

### A2. Quality is enforced at gates, not in translate

The LangGraph design separates **translation** (creative, LLM-driven) from **quality gates** (deterministic, rule-driven). Never push quality logic into translator prompts. Never push translation creativity into the gates.

**Why:** PRD §5 — "Deterministic checks + controlled LLM drafting." If a critical defect class isn't caught by a deterministic gate, the system has no defence against the LLM hallucinating it.

**How to apply:** every new defect class lives in `app/services/quality_gate.py` (or a sibling), with a typed entry in `app/core/defect_taxonomy.py`. Add a test case in `tests/evals/data/<lang_pair>/critical_safety.jsonl` that proves it fires.

### A3. No silent fallbacks in regulated paths

The reviewer surface used to silently substitute mock translations on backend errors. That is a safety hazard, not a UX nicety. The same rule applies anywhere a regulator-facing artefact is produced: if upstream data is missing or stale, fail loud — never substitute, never default.

**Why:** A reviewer signing off mock content as real is the worst-case failure mode for a translation system in pharma. Anything that even risks this is a hard reject at review.

**How to apply:** if you reach for a default value in code that touches an audit event, a translation segment, a defect, an evidence bundle, or a signed manifest — stop. Either fail explicitly or change the design so the default isn't needed.

### A4. Two model layers exist; do not deepen the divergence

`app/models/database.py` (operational; String IDs; SQLite-friendly) and `app/models/translation.py` (regulatory; UUID + Vector(1536); Postgres-only) are two parallel schemas for overlapping concepts. v3.0 ticket TMX-3017 will rationalise them. Until then, every new model addition should justify why it doesn't add to the debt.

**Why:** Mixing the two layers in queries crashes on SQLite. Test runs that depend on the SQLite default will silently miss bugs the Postgres CI catches.

**How to apply:** new tables go in `database.py` (the simpler layer) unless they need pgvector. If you need both, raise it at design review.

### A5. Documents and segments carry stable IDs end-to-end

`segment_id`, `doc_id`, and `audit_event_id` are stable across all surfaces (UI, REST, MCP, SDK, webhooks). Never re-derive them from order or content. The DOCX export (in-flight) currently uses content-map matching with sequential-index fallback — this is fragile and will be fixed in v3.0 (TMX-3701).

**Why:** Reproducibility under GxP. A reviewer's edit to segment X must land on segment X, not "the segment at offset 47 today".

**How to apply:** if you write code that maps positions to IDs, the IDs are the source of truth. If you need positional information, derive it from the ID, not the other way around.

### A6. Every external sourcing of LLM output is a "qualified supplier" call

When you call an LLM via `app/services/llm.py`, you are engaging a qualified supplier per Annex 11 §3. The call must record the provider, model, model version, prompt version, and response token usage in the JobConfigSnapshot. No call may proceed without this telemetry.

**Why:** EU AI Act technical-documentation obligations (live 2026-08-02) require this. So does any GAMP 5 review.

**How to apply:** never call an LLM directly. Always go through the LLM service. If you need a new model, register it in the routing config and the model-pricing table; never hard-code a model name in business logic.

### A7. The frontend has one canonical IA: `/workspace/*`

There is currently a parallel top-level set of routes (`/document/[id]`, `/translate/[id]`, `/review/[id]`, `/new`, `/knowledge`, `/design-system`). v3.0 ticket TMX-3600 retires them in favour of `/workspace/*`. Don't add new top-level routes. Don't take dependencies on the old paths.

**Why:** Two IAs is two surfaces to validate, two themes to maintain, two ways for a reviewer to get lost. One canonical IA is a precondition for the design system v1.

**How to apply:** new pages go under `/workspace/`. If you need the design-system showcase, it lives at `/workspace/design-system`.

### A8. Pin every prompt to a version

Prompts in `app/agents/prompts.py` are inline string constants today. v3.0 ticket TMX-3200 moves them to `app/agents/prompts/<agent>/<version>.yaml`. Until that ships, treat any prompt edit as a `prompt_version` bump and record it manually in the JobConfigSnapshot description.

**Why:** Reproducibility, model cards, EU AI Act technical documentation. A regulator looking at audit event from 2026-04-01 must be able to ask "which exact prompt produced this output?" and get an unambiguous answer.

**How to apply:** when you edit a prompt, even a typo fix, increment the version. Don't share prompts across agents. Don't compose prompts from runtime variables — interpolate, don't concatenate.

### A9. Soft-delete only

There is no `DELETE FROM` in our domain code. There won't be in v3.0 — see `app/models/database.py:DeletionRecord` and the planned `is_deleted` columns on every table (TMX-3015). If you need to remove a record, write a tombstone that preserves the audit chain.

**Why:** Audit references must outlive the records they describe. Hard deletes break this.

**How to apply:** if you find yourself writing `db.delete(obj)`, stop and refactor. The domain has soft-delete primitives; use them.

### A10. The `.context/` directory is the program brain

`.context/active_tasks.md` is the canonical backlog. `.context/status.md` is the current phase. `.context/lead_decisions.md` is the answered-questions log. `.context/handoff_log.md` is the session-end audit. **Read these at session start.** Update them at session end.

**Why:** Multiple agents and humans run this program; the context-of-record cannot live in chat history.

**How to apply:** when picking up work, read `.context/status.md` and `.context/active_tasks.md` first. When closing work, append to `.context/handoff_log.md`.

| ID | Addendum | Why |
|---|---|---|
| A1 | Audit-by-default | Differentiator + pharma scrutiny |
| A2 | Quality at gates, not in translate | PRD §5 deterministic-vs-LLM separation |
| A3 | No silent fallbacks in regulated paths | Reviewer-signs-mock-as-real is the worst case |
| A4 | Don't deepen dual-model-layer divergence | SQLite vs Postgres schema crashes |
| A5 | Stable IDs end-to-end | Reproducibility under GxP |
| A6 | LLMs are qualified suppliers | Annex 11 §3 + EU AI Act |
| A7 | One canonical IA: `/workspace/*` | Two IAs = two surfaces to validate |
| A8 | Pin every prompt to a version | EU AI Act technical documentation |
| A9 | Soft-delete only | Audit references outlive records |
| A10 | `.context/` is the program brain | Multi-agent coordination |

Project-specific addenda also live in `.claude/skills/transmax-coding-discipline/` (to be added when an A11 emerges that's worth a full skill page).

---

## Where things live

- **Specs / PRD**: `research/draft_PRD.md` (PRD v1.1, 17 Jan 2026 — authoritative)
- **Design docs**: `research/design_v1.md`, `research/design_ext.md`, `research/pipeline_architecture.md`
- **Code review (May 2026)**: `Transmax_Review_and_Upgrade_Path.docx`
- **v3.0 release plan**: `research/v3_pilot_ready_release_plan.md` (Part I + Part II, integrates the headless agent spec)
- **Headless agent spec**: `TRANSMAX_HEADLESS_AGENT_SPEC.md`
- **Active program state**: `.context/{status,active_tasks,lead_decisions,questions_to_lead,handoff_log}.md`
- **Multi-agent protocol**: `COLLABORATION.md`
- **Quality-gate kit**: `quality-gate/` (PRS scoring, static rules, AI/LLM/prompt/security packs)
- **Ratchet**: `ratchet/baseline.json` + `scripts/ratchet.py`
- **AI eval harness**: `tests/evals/`

---

## Known issues you must not silently work around

These are real bugs the May 2026 review identified. Fix them only with an explicit ticket; do not paper over them.

**✅ Resolved since the May 2026 review** (kept for legible history — do NOT re-open as if broken; verify before re-touching):

- ~~`graph.py:141` model hard-coded `"gpt-4o"`~~ — **RESOLVED** (TMX-3202): audit snapshot captures the real model via `resolve_model(...)`.
- ~~`graph.py:149,438` meaningless `Formatter.formatTime` timestamp~~ — **RESOLVED** (TMX-3212): now `datetime.now(timezone.utc).isoformat()`.
- ~~`graph.py:432` `state['iteration_count'] = 999` hack~~ — **RESOLVED** (TMX-3211, `7602de8`): explicit `force_finalize` flag read by `decide_next_step`.
- ~~`graph.py:615` final audit `output_hash: "placeholder_hash"`~~ — **RESOLVED** (TMX-3213, `5f04b44`): real deterministic sha256 over the ordered output, on legacy + v2 sinks.
- ~~Auto-approval `0.90` in `learning_service.py` (C-13)~~ — **RESOLVED** (TMX-3405): no threshold logic; entries persist PROPOSED, no auto-promote.
- ~~`text.split('.')` segmentation in `translations.py` (C-11)~~ — **RESOLVED** (TMX-3800): abbreviation-aware segmenter at `app/services/segmenter.py`.
- ~~`print()` in `app/` (no structured logging)~~ — **RESOLVED** (TMX-PRINT-SWEEP): all `app/` prints converted to `logger`; the `DATABASE_URL` debug print is now `logger.debug` (no credential leak at default level).

**⚠️ Still open** (the context you need before changing behaviour in these files):

- `app/services/audit_service.py` — chained-hashing uses string concatenation, no domain separator (review C-04). v3.0 epic E2 rebuilds the ledger. The terminal `output_hash` is now real (TMX-3213), but the *chain* hashing redesign is still pending.
- `transmax.db` — SQLite file committed in git, recently grew 266KB → 5.6MB. v3.0 ticket TMX-3002 removes from history. **Recurring schema-staleness:** the committed file lags behind every Alembic migration (TMX-3015 soft-delete columns, TMX-3045 approval columns) and causes ~40 false-red test failures whenever a test falls through to it instead of using `tests/conftest.py`'s `fresh_engine_for_db` fixture. To rebuild locally so tests stop tripping on schema drift: `python -c "import os; os.remove('transmax.db') if os.path.exists('transmax.db') else None; from app.core.database import init_db; init_db()"` — DO NOT commit the rebuilt file (TMX-3002 is Kapil-gated for the `git rm --cached` step). Follow-up TMX-AUDIT-DB-3002a audits test-fixture usage.
- `.env` — committed with what appears to be a real OpenAI key (review C-01). **Do not edit until the key has been rotated and the file purged from history (TMX-3000).**
- Single Alembic mega-migration (review C-06). v3.0 ticket TMX-3017 unwinds it.
- `app/services/quality_gate.py` is a thread-unsafe lazy singleton (review C-08). v3.0 ticket TMX-3400 makes it instance-based.
- `app/services/resilience.py` circuit breaker stores state in class-level globals (review C-07). v3.0 ticket TMX-3018 backs it with Redis.
- Auto-approval threshold of 0.90 in `app/services/learning_service.py` (review C-13). v3.0 ticket TMX-3405 removes it.
- `text.split('.')` segmentation in `app/api/v1/translations.py:54` (review C-11). v3.0 epic E5 replaces with a real segmenter.
- Regex-only PII service in `app/services/pii_service.py` (review C-12). v3.0 ticket TMX-3805 replaces with Presidio.

If you find yourself working in any of these files, this is the context you need before you change behaviour.

---

## Conventions

- **Python**: ruff for lint and format; mypy for types; type hints everywhere; dataclasses or pydantic for value objects, not raw dicts. No `Any`, no bare `except`, no `print()` in app/. Use `logger`.
- **TypeScript**: strict mode; no `as any`; no `// @ts-ignore`; explicit return types on exported functions; tailwind for styling.
- **Tests**: `tests/<area>/test_<thing>.py` for backend; `frontend/__tests__/` for unit (vitest); `frontend/e2e/` for end-to-end (playwright). Every PR carries new or updated tests. Eval suites live under `tests/evals/<lang_pair>/`.
- **Migrations**: every schema change is its own Alembic revision. No mega-migrations.
- **Commits**: imperative mood, ≤ 70 char subject; body explains *why* not *what*. Reference ticket ID when applicable. The pre-commit hook `red-flag-attestation` will append a Self-review block — fill it in.
- **PR**: use the template in `.github/PULL_REQUEST_TEMPLATE.md`. Spec / Summary / Verification / Self-review are all required. CI enforces.

---

## Pod / Lane structure (v3.0 release)

The 11 epics in `research/v3_pilot_ready_release_plan.md` are owned by 8 pods. When picking up work, identify the owning pod and read its Lane brief in `.context/active_tasks.md`. Don't reach across pod boundaries without coordinating in the weekly cross-pod sync.

| Pod | Owns |
|---|---|
| Auth & Tenancy | E1 |
| Audit & Validation | E2, E3 |
| Document Pipeline | E4, E5 |
| Quality & Regulatory | E6, parts of E10 |
| Agent & AI | E7 |
| Reviewer Frontend | E8 |
| Platform & Observability | E9, parts of E11 |
| Pilot/GTM | E10 |

E11 (Headless Foundation) is shared between Platform and Agent & AI.

<!-- ctxpack:session-memory:v5.L1 -->
## Session memory (ctxpack ledger)

This repo uses CtxPack Checkpoint: hooks pack every compaction and
session end into `.claude/ctx/` (a deterministic ledger — the raw
transcript is never deleted), and each session start re-injects the
previous session's gist. Trust the gist's constraints and decisions.

**Resuming or recalling past-session detail — use the ledger read path
FIRST**; fall back to grepping the raw transcript only if it fails
(fallbacks are tracked):

- One-call resume: `ctx/resume` (MCP) or `ctxpack session resume` —
  gist + decisions + constraints + failed approaches + exact identifiers
- MCP (if connected): `ctx/session_recall`, `ctx/session_timeline`,
  `ctx/session_decisions`, `ctx/session_literals`, `ctx/why`,
  `ctx/graph_query`
- CLI twins: `ctxpack session decisions | timeline | recall | literals |
  why | graph | resume` (`--session <id>` targets older sessions;
  `ctxpack session stats` shows adoption + capture metrics)
- Bank the session BEFORE `/clear` or risky context loss: `ctx/checkpoint`
  (MCP) or bare `ctxpack checkpoint` (both auto-resolve the live
  transcript)

**Decision convention (load-bearing):** state every nontrivial decision
(design choice, root cause, chosen fix, abandoned approach) in your reply
on its own sentence starting with `Decision:` — e.g. `Decision: use
exponential backoff with base 750ms because the vendor limit is 40
req/min.` The deterministic parser extracts these; unmarked decisions in
free prose are often missed. State marker lines in the turn-FINAL
message (the reply that ends your turn): Claude Code 2.1.x does not
reliably persist mid-turn assistant text to the transcript, and what
never reaches the transcript can never reach the ledger — restate
mid-work decisions in your closing summary. Dead ends the same way:
"The X approach didn't work because ...". Operating rules you set
yourself the same way, sentence-leading: `Constraint: eval results are
immutable — write new versioned files, never overwrite.`

**Override convention (conflict lint):** when a new decision knowingly
changes a banked decision or constraint, follow the `Decision:` line
with its own line: `Supersedes: <fact_id> — <reason>` (recover the
fact_id via `ctxpack session why "<value>"`). The checkpoint lint
surfaces unresolved collisions at the top of the next gist; a declared
supersession resolves the row and demotes the old fact in rank. The
goal is "never change decisions silently", not "never change
decisions". Malformed overrides are ignored — the conflict stays
visible rather than being silently waved through.

**Incident convention (memory telemetry):** when the ledger visibly helps
or fails you, record it on its own line, sentence-leading:
`ctx-incident: <type> | fact="<the fact involved>" | expected="..." |
got="..." | evidence="..."` — types: saved, missed, stale, wrong,
conflicting, native-better, user-corrected. Only type and fact are
required; include the concrete value so the row is auditable. Examples:
`ctx-incident: stale | fact="CACHE-TTL-S current value" | expected="25"
| got="50"` or `ctx-incident: saved | fact="commit 66cdded scope" |
evidence="session why returned turn 408"`. Report failures as readily as
saves — a missed/stale row is worth more than a flattering one.

**Cross-repo lessons (v1 — `ctxpack lessons` for receipts):** hard-won rules from reviewed incidents across the cohort; treat them as constraints on quality of work:

- `L-001` [eval-harness] Grade evidence is the complete verbatim output plus its sha256 — never store a truncated prefix of what was graded. A gate whose evidence cannot be independently reproduced from the artifact is a failed gate, even when the underlying result is real.
- `L-002` [privacy-release] Every committed artifact is a release surface: no machine-local absolute paths, no real usernames. Reference companion files by sibling-relative name plus SHA-256, and audit the artifact BEFORE writing it, not after committing it.
- `L-003` [privacy-release] Committed fixtures never carry real user or session data. Replace with synthetic data from a committed deterministic generator (or mechanically verifiable pseudonymization), and enforce with a standing repo-wide gate with a named fictional-user allowlist.
- `L-004` [eval-harness] Eval results are immutable and error rows are never graded: each run writes a NEW versioned artifact, and a failed, empty, or over-budget call aborts the scored run instead of scoring as a miss.
- `L-005` [eval-harness] Text graders must be polarity-aware, with adversarial cases pinned as tests BEFORE scoring: a negated mention is a dismissal, not a detection, and contrast markers can restore polarity mid-clause.
- `L-006` [eval-harness] Paid API runs are interlocked in code, not convention: pinned model, preflight worst-case bound with tokenizer headroom, a ceiling guard before EVERY attempt, and a durable fsync'd per-invocation ledger.

When a lesson visibly applies (or fails), bank a `ctx-incident:` row naming its id — cross-repo incident evidence is what promotes and retires lessons.
<!-- /ctxpack:session-memory -->
