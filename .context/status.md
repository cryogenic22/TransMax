# TransMax Project Status

**Current Phase**: v3.0 pilot-readiness — seam programme (ADR-0009) integration
**Date**: 2026-08-08
**Active Agent**: Claude (orchestrator) — seam reapply + PR #22 stabilization

> This file is the canonical program state (A10). It was ~7 months stale
> (last real edit 2026-01-17, "Phase 2.5 / no blockers") until 2026-08-08.
> Keep it current: a fresh agent loads this to learn the true state.

## Overall Goal
An auditable, regulatory-grade AI translation engine for pharma — now positioned
as the **language engine behind reSCApe's versioned contract** (ADR-0009), not a
standalone product. See `.context/loops/SEAM-ORCH-2026-07-22.md` for the live
seam-programme state and `docs/decisions/0009-*.md` for the boundary.

## Where things stand
- **origin/main was security-rewritten** on 2026-08-05 (STAB-1 `41fdcc9`) to purge
  a leaked `.env` key from all history. New root; no `.env` blob anywhere in main.
- The **seam programme** (contract v1.1.0, ~14 truth/honesty loops) was reapplied
  onto the purged main as **`feat/seam-clean`** → **PR #22**. It is fast-forwardable
  and key-free.
- **PR #22 is NOT mergeable yet** — a code review (2026-08-08) found the branch's
  local green was non-hermetic. Stabilization is in progress (below).

## Current Focus — PR #22 stabilization (before merge)
Tracked in `.context/loops/SEAM-STABILIZE-2026-08-08.md`.

## Known Issues / Blockers
- **[in progress] Non-hermetic tests** — the suite required a private `.env` key and
  made real (paid) OpenAI calls. Fix: autouse offline-fake fixture + embeddings gated
  on `enable_live_llm_inference`. Verifying full suite green on a clean clone.
- **[fix ready] Unearned QUALIFIED tier** — `language_tiers.resolve_language_tier`
  awarded QUALIFIED on mere corpus-file existence, not a passing measured run (C-9).
- **[fix ready] ValidationSummary honesty** — `decision` read `Document.status` not the
  real scorecard verdict, and a scorecard-lookup failure was reported as zero defects
  (A3 fail-open). `/{job_id}/result` in `app/api/v1/translations.py`.
- **[workflow] Code Quality gate** — all three axes (ruff-format ~400, ruff-lint 269, mypy
  374) are legacy debt that never passed (masked by the old unpinned `black` step). Now
  aligned with pre-commit (ruff pinned `0.7.4`) + advisory; sweep = TMX-QUALITY-GATE-BASELINE.
- **[workflow] gitleaks** — shallow PR checkout scanned ~0 bytes; fixed to `fetch-depth: 0`.
- **[open] Playwright Linux visual baseline** — `design-system-page-chromium-linux.png`
  never committed; must be generated in a Linux/CI runner.
- **[open, Kapil-gated] Audit-v2 FK rejection (TMX-3221)** — Document-backed job IDs have
  no `translation_jobs` row, so v2 audit inserts are FK-rejected and the emitter swallows
  it (A1/A3). Identity reconciliation is one-way; needs Kapil.
- **[open, governance] History-rewrite evidence** — the purge invalidated ~86 historical
  worksheet SHAs (drift audit exit 1). Needs a SUPERSEDED_BY_SECURITY_REWRITE mapping/ADR.

## Not blockers (correctly parked)
- Batch D (reSCApe-side, waits on our contract signal); RFC-0005 (Kapil's signature);
  TMX-MQM-5b cutover; TMX-3000/3002 (key rotation / db removal from history).
