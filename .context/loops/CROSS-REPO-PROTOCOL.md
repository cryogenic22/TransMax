# Cross-repo loop protocol — TransMax ↔ reSCApe

**Owner**: Programme Lead (Kapil)
**Status**: Active 2026-07-22 onwards
**Governs**: any loop whose blast radius crosses the `Scriptiva_SCA` (reSCApe) boundary
**Authority**: extends `.context/loops/README.md`; does not replace it. ADR-0009 is the decision this
protocol operationalises.

---

## Why this exists

The 8-stage loop assumes one repo, one board, one lock, one CI. The seam work breaks all four
assumptions:

| Assumption | Reality across the seam |
|---|---|
| One board | TransMax: `.context/loops/*.md` + `active_tasks.md`. reSCApe: `delivery/backlog.jsonl` + `delivery/runs/*.md` |
| One ID namespace | `TMX-*` here; `E<n>.<m>` / `ARC*` / `ENG-CORE-*` / domain-singletons there |
| One lock | Reversibility tag here; **Backend Lock** + G1–G7 there |
| One CI | Independent suites that can both be green while the seam is broken |

That last row is not hypothetical. It is the current production defect: `transmax_bridge.py` fails open
to glossary mode, both test suites stay green, and the product reports `mode: "transmax_ai"` over
output the engine never touched. **Independent green is how we got here.**

---

## Rule 1 — Two worksheets, one contract version

A seam loop files a worksheet in **each** repo. Neither closes alone.

- TransMax side: `.context/loops/TMX-XXXX.md`, normal template.
- reSCApe side: a `delivery/backlog.jsonl` row in their own convention, filed in their coordinated
  quiet window (never a drive-by edit — `backlog.jsonl` is shared state with their runner).
- Both carry the header line `**Seam**: contract vN.N — paired with <other repo's id>`.

The **contract version is the join key.** The drift auditor cannot resolve a commit in the other repo,
so the contract version is what makes the pair auditable.

Stage 8 closes when **both** SHAs are pushed **and** the conformance suite is green. A one-sided
`[Done]` is a lying-backlog entry.

---

## Rule 2 — Both locks apply, strictest wins

A seam loop clears TransMax reversibility **and** reSCApe's Backend Lock.

- Anything touching `apps/api` that adds a **route module, service module, or SQLAlchemy model**
  is one-way-equivalent: it needs an RFC and human approval before stage 4, regardless of what our
  reversibility tag says.
- Extending an existing reSCApe module is lock-safe. Prefer it always — this is why
  `transmax_bridge.py` is **rewritten in place** rather than replaced by a new client module.
- reSCApe's G1–G7 apply to their side of the diff. Their **G3 "no vacuous green"** (test must fail
  without the change, cite verbatim red/green) is the same rule as our G2 and is satisfied once.

---

## Rule 3 — The contract is versioned, additive, and owned by TransMax

TransMax publishes the contract because it owns the engine. reSCApe consumes generated types into
`packages/contracts`, matching the pattern ADR-0004 already established for its two frontends.

- Backwards-compatible additions only. A shape change goes to a `v2` route.
- The counterpart's generated client is regenerated **in the same loop**. A contract change that
  leaves the other side's client stale is an incomplete loop, not a follow-up.
- The contract version is stamped in every response so a stored result can be traced to the shape
  that produced it.

---

## Rule 4 — The seam conformance suite, and what it forbids

One suite, run by **both** CIs: TransMax against its own live service, reSCApe against a pinned
TransMax container. **Mocking the counterpart is prohibited inside this suite.** Mocks belong in unit
tests; the whole purpose here is to test the middle.

These are the standing invariants. They are the AC set any seam loop inherits.

| # | Invariant |
|---|---|
| **C-1** | Engine unreachable ⇒ caller receives a **typed error**. Never a glossary substitution, never a partial result presented as complete. |
| **C-2** | No provider / invalid model response ⇒ typed `PROVIDER_UNAVAILABLE` / `INVALID_MODEL_RESPONSE`. Never `[target] source`. |
| **C-3** | Low-confidence source-language detection ⇒ typed hold. Never a silent `en` default. |
| **C-4** | **No response carries a provenance value the engine did not earn.** `mode`, model, prompt version, match type and quality tier are derived from the artefact that produced them — never defaults, never survivors of a fallback path. |
| **C-5** | A bound (TM-matched) segment still runs the deterministic gates. Binding skips the model, never the checks. |
| **C-6** | A submission-bound segment cannot be marked lockable without a resolvable signature reference. |
| **C-7** | Same `request_id` twice ⇒ one job, one set of side effects, one chain entry. |
| **C-8** | Every result carries `audit.chain_head_hash` and a verification URL that independently verifies. |
| **C-9** | A declared target locale below **Qualified** tier is labelled as such in the response. An unmeasured language can never be reported as a supported capability. |

**C-1 is the regression test for today's defect.** Write it red first: stop the engine, assert the
caller surfaces a typed error and no `transmax_ai` label appears anywhere in the response.

---

## Rule 5 — Board vocabulary

Two vocabularies, deliberately distinct. Do not merge them.

- **Worksheet header** = loop stage. Unchanged, 7 values, per `README.md`:
  `[Spec] [Design] [WIP] [Verify] [Fix] [Done] [Blocked]`.
- **Board row** (`active_tasks.md`) = ticket state. **Five values, closed set:**
  `READY · WIP · BLOCKED · DONE · DROPPED`.

`[Done, pending push]` is not a state — it is `WIP`. A ticket is `DONE` when its SHA is on
`origin/main`, per the push-hygiene rule in `CLAUDE.md`.

Every ticket ID referenced anywhere must have a board row. An ID that appears only in another
ticket's prose is untracked debt, not a plan — there are currently 95 of them, and the hygiene sweep
(`TMX-BOARD-HYGIENE`) clears them before the seam loops start, so the cross-repo work does not
inherit the leak.

---

## Rule 6 — Reviewer independence

Seam loops get a **second-pass review from a different model family** than the one that wrote the
code. Claude reviewing Claude shares blind spots; the same reasoning already led us to a model-agnostic
judge in ADR-0007. Codex is the second family — see the "Reviewer mode" section of `AGENTS.md`.

The reviewer sees the diff, this protocol, and the invariants above. Its findings land in stage 6 of
the worksheet with a verdict, exactly like an internal red team.

---

## What a seam loop looks like end to end

1. **Task** — restate; name both repos in blast radius.
2. **Spec** — ACs, plus the C-invariants this loop touches.
3. **Design** — contract delta first. If the shape changes, say why it is additive or why it needs `v2`.
4. **Code** — TransMax side and reSCApe side, each in its own commit, each referencing the pair.
5. **Eval/Test** — unit tests per side **plus** the conformance suite against a live pair. Captured output.
6. **Red team** — internal Tier-2 + cross-family second pass.
7. **Fix**.
8. **Deploy** — both SHAs pushed, conformance green, both boards updated.
