# TMX-3704-ui — Surface directional move semantics in `<RevisionIndicator>`

**State**: `[Done]`
**Owner**: Reviewer Frontend pod (Antigravity / Pod B)
**Sprint**: 2
**Started**: 2026-05-09
**Closed**: 2026-05-09 (header backfilled by TMX-3060 drift audit on 2026-05-10; commit `c4b4eef` on origin/main)
**Reversibility**: `two-way` — single component change, additive label paths.
**Pre-mortem**: If this fails in production, the failure mode is — a reviewer reads "moved" on a segment that lost text and confuses it for one that gained text, signs off thinking the relocation is benign when in fact the original copy was relocated to a different SmPC section. The directional info from TMX-3704 is what protects against this; without UI, the wire-format change is dark.
**Blast radius**: `frontend/components/ui/RevisionIndicator.tsx` only + tests. Demo page on `/workspace/design-system` extends with 2 more fixtures (moveFrom-only, moveTo-only).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat**: extending an existing component, no new dependencies, single-file change, reuses lucide icons already shipped.
- [ ] **G2 Reproduce-failure**: write tests that assert directional labels render — RED before implementation, GREEN after.
- [ ] **G3 Completion**: a reviewer opening a segment with `has_moves_from=true, has_moves_to=false` sees a label distinct from one with `has_moves_to=true, has_moves_from=false`. Not just "tests pass" — the UI carries the distinction.

---

## 1. Task

TMX-3704 (`a1bc03d`) split the wire format's `has_moves` boolean into directional `has_moves_from` (text was relocated AWAY from here) and `has_moves_to` (text arrived HERE from elsewhere) — but kept `has_moves` as derived for backward compat. The frontend `<RevisionIndicator>` (TMX-3702-v1, `a48c2b6`) currently reads only `has_moves` and renders the generic `tracked` label, dropping the new directional info on the floor.

This loop surfaces the directional semantic in the pill label. Insertions / deletions paths stay unchanged.

**Addenda**: A1 (audit-by-default — directional move semantics belong in the visible audit chain).

## 2. Spec — acceptance criteria

- [ ] AC-1: When `revisions.has_moves` is true AND there are no insertions or deletions, the pill renders one of three directional labels:
  - `moved out` if `has_moves_from && !has_moves_to`
  - `moved in` if `!has_moves_from && has_moves_to`
  - `moved` if `has_moves_from && has_moves_to`
- [ ] AC-2: When the segment has insertions OR deletions (with or without moves), the label remains `tracked` (so the reviewer's eye lands on the editorial change first; the move detail lives in the title tooltip).
- [ ] AC-3: The icon stays as `ScrollText` for the ins/del path; switches to `ArrowRight` (moved out), `ArrowLeft` (moved in), or `ArrowLeftRight` (moved) for the move-only paths.
- [ ] AC-4: The title attribute (hover tooltip) carries the directional info via the existing `Has moves` line, plus `Has moves from` / `Has moves to` when the directional flags are true.
- [ ] AC-5: 4 new vitest cases written **first** (G2 reproduce-failure):
  - moveFrom-only renders `moved out` + ArrowRight
  - moveTo-only renders `moved in` + ArrowLeft
  - both directions render `moved` + ArrowLeftRight
  - moves combined with insertions still render `tracked` (unchanged)
- [ ] AC-6: `/workspace/design-system` page extends with 2 more fixtures (moveFrom-only, moveTo-only) so the directional variants are discoverable.
- [ ] AC-7: Existing 6 RevisionIndicator tests + the existing TMX-3702-demo fixtures continue to pass.

**Out of scope**:
- Move-pair linking (matching a `<w:moveFrom>` with its `<w:moveTo>` via `w:id`) — backend ticket TMX-3704-pairing.
- Per-revision accept/reject (TMX-3702-v2 is blocked on ADR-0004).

## 3. Design

Compute the move-direction label in a small helper that returns either `{label, Icon}` or `null`. The render logic chooses:
- has any ins/del → use the existing `tracked` + `ScrollText` path
- else has any moves → use the helper's directional output
- else → component returns null (defensive guard, unchanged from v1)

This keeps the existing code paths visible and lets future v3 (per-revision detail) compose on top without stretching the helper.

**Why "moved out" / "moved in" rather than the OOXML terms moveFrom / moveTo**: reviewers are pharma copy-editors, not OOXML spec readers. Plain English wins.

**Why ArrowRight for moveFrom**: text leaving the current location → arrow points away. Considered ArrowLeft (mirror) but the right-pointing variant reads "departure" more naturally in LTR scripts. The semantic survives in the title attribute regardless.

**Alternatives rejected**:
- Compose 2 pills (one for ins/del, one for moves): visually noisy on a segment row that already has StatusLifecycle + (in v2) a confidence dial + provenance chip.
- Drop "tracked" label entirely when moves are present, even with ins/del: loses the editorial-change cue. Compromise: when ins/del present, the label is "tracked" (covers the union); the title tooltip carries direction.

## 4. Code

| File | Change |
|---|---|
| `frontend/components/ui/RevisionIndicator.tsx` | Add directional helper; render variant icon + label for move-only paths; extend title tooltip with moves-from / moves-to lines |
| `frontend/__tests__/RevisionIndicator.test.tsx` | 4 new test cases (move-only variants + combined-with-ins) |
| `frontend/app/workspace/design-system/page.tsx` | 2 new fixtures (moveFrom-only, moveTo-only) |

## 5. Eval / Test

```
$ npm run test -- RevisionIndicator    # vitest, expect 10/10 (was 6)
$ npm run lint && npm run typecheck && npm run build
```

## 6. Red team

(filled at stage 6)

## 7. Fix

(filled at stage 7)

## 8. Deploy

- [x] Commit: `c4b4eef` — backfilled by TMX-3060 drift audit (2026-05-10) on `origin/main`

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-05-09T21:00Z | — | `[Spec]` | Loop opened — TMX-3704-ui via loop-driven-dev gates |
