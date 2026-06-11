# TMX-ARTIFACTS — Untrack committed .pyc/.log build artifacts

**State**: `[Done — pending SHA record]`
**Owner**: Platform & Observability
**Sprint**: 2 (10-loop maturity batch)
**Reversibility**: `two-way` — `git rm --cached` only removes from the index; files stay on disk. `.gitignore` already covered both patterns (rules predate the stale commits). Revert = re-add.
**Pre-mortem**: none material — build artifacts (.pyc regenerate on import; .log are debug junk). No source code touched.
**Blast radius**: git index (160 files untracked: 143 `.pyc` + 17 `.log`); 17 junk debug logs deleted from disk. `transmax.db` deliberately NOT touched (Kapil-gated, TMX-3002).

**Gates**: G1 ✅ (stability — a fresh clone no longer ships 160 build artifacts; removes the `.pyc` churn that polluted every `git status`/diff). G2 N/A. G3 ✅ — 0 `.pyc`/`.log` tracked; `.gitignore` prevents re-adding; `committed_log_files` ratchet 18→1.

## Spec
- AC-1: no `*.pyc` or `*.log` files tracked by git (`git ls-files` returns none).
- AC-2: `.gitignore` covers `__pycache__/` + `*.log` (already true) so they cannot re-enter.
- AC-3: `transmax.db` untouched (Kapil-gated).

## Test
`git ls-files '*.pyc' '*.log'` → empty. Ratchet `committed_log_files` 18→1 (remaining 1 = a `.next` build artifact). Files confirmed still on disk after `--cached`.

## Deploy
- [x] Commit: `<pending>`
- [ ] Pushed to origin/main

## Status log
| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-11 | — | `[Done — pending SHA record]` | 160 artifacts untracked; 17 junk logs deleted; gitignore already covered |
