# TMX-UX-PROV-COPY — Copyable, screen-reader-accessible audit hash on ProvenanceChip

**State**: `[Done]`
**Owner**: Reviewer Frontend · **Sprint**: 2 · 2026-06-11
**Reversibility**: `two-way`.
**Pre-mortem**: if this fails, an auditor wanting to reference an audit hash must hover for a tooltip or screenshot it — the A1 trust signal is visible but not usable.
**Blast radius**: `frontend/components/ui/ProvenanceChip.tsx`, `frontend/components/ui/CopyButton.tsx` (added aria-label/size — backward compatible).

**Gates**: G1 PASS (reuses CopyButton; fixes its a11y gap too). G3 PASS (full hash is one-click copy + exposed to AT).

## 1. Task
ProvenanceChip rendered the hash truncated with the full value only in the `title` tooltip and no copy affordance. CopyButton had `title` but no `aria-label`. Make the audit hash copyable + accessible.

## 2. Spec
- AC-1: when `hash` present, a button labelled "Copy full audit hash" renders and copies the FULL hash.
- AC-2: the truncated `<code>` carries `aria-label="Audit hash <full>"` so AT reads the full value.
- AC-3: no `hash` → no copy button (unchanged chips).
- AC-4: CopyButton exposes an `aria-label` (default "Copy to clipboard").

## 3. Design
Reuse `CopyButton` (DRY) with a new optional `label` (drives title+aria-label) and `size`. Add it inside the `hash` branch of ProvenanceChip + `aria-label` on the code. Rejected: inlining a second clipboard handler (DRY violation).

## 4. Code
| File | Change |
|---|---|
| `frontend/components/ui/CopyButton.tsx` | `label`/`size` props + aria-label |
| `frontend/components/ui/ProvenanceChip.tsx` | CopyButton + aria-label on code |

## 5. Eval / Test
`frontend/__tests__/ProvenanceChip.test.tsx` +3; existing CopyButton tests still green. vitest 123 green.

## 6. Red team
Nested `<button>` inside the chip `<span>` — checked all usages: none place a hash-bearing chip inside an `<a>`/button (the only invalid-nesting case). Valid HTML; build clean.

## 7. Fix
No findings — clean.

## 8. Deploy
- [x] Commit: f4ad0b1 (on origin/main)

## Status log
| 2026-06-11 | — | `[Done]` | hash copyable + AT-accessible |
