# Ratchet

Monotonic-improvement quality gate for TransMax.

## What it is

A list of measurable code-quality metrics, each tagged as either:

- **bad** (`direction: down`) — current must be `<=` baseline
- **good** (`direction: up`) — current must be `>=` baseline

Pre-commit and CI re-measure every metric on every change and **fail if any metric got worse**. Baselines are tightened by deliberate PR (`scripts/ratchet.py update`), never loosened by accident.

This is the Karpathy "broken-window" principle, encoded as code: once you fix a class of debt, the ratchet prevents it from coming back. Once a metric drops, it can't silently rise.

## Why we have one

- The **quality-gate** at `quality-gate/` enforces *file-level* quality (PRS scoring + static rules). It blocks commits where individual files fall below threshold, but it doesn't track *aggregate* state over time.
- **Linters and type-checkers** catch things they're configured to catch. They can't track "we used to have 40 `Any` annotations and now have 41" — they only fail on absolute thresholds.
- The ratchet sits between the two. It tracks counts that are too high to fail-on-zero today but must monotonically decrease.

## What it tracks (today)

See `ratchet/baseline.json` for the current values. Categories:

**Backend** (`*.py` under `app/`, `scripts/`, `tests/`, `transmax_sdk/`, `transmax_mcp/`):
- `# type: ignore` count
- bare `except:` count
- `print(` calls in `app/` (logger preferred)
- `Any` annotations
- TODO/FIXME without an issue link
- placeholder strings (`placeholder_hash`, `change-me-in-production`, `change_this_unsafe_secret`)
- files >= 800 lines

**Frontend** (`*.ts`, `*.tsx` under `frontend/app/`, `components/`, `hooks/`, `lib/`):
- `as any` casts
- `// @ts-ignore` directives
- `// @ts-nocheck` directives
- `console.log/debug/trace` calls
- `: any` annotations

**Repo hygiene** (whole repo):
- `*.db` files committed
- `*.log` files committed
- `*.pyc` files committed

**Test coverage proxies** (these ratchet UP):
- total `test_*` function count
- total `test_*.py` file count

## How to use it

```bash
# Show current vs baseline as a table
python scripts/ratchet.py status

# Pre-commit / CI mode — exits 1 on any regression
python scripts/ratchet.py check

# Print current measurements as JSON (for scripting)
python scripts/ratchet.py measure

# Write a new baseline (PR-reviewed; refuses to loosen without --force + --note)
python scripts/ratchet.py update --note "Closed TMX-3211 — iteration_count=999 hack removed."
```

## When to update the baseline

- **After landing a fix** that improves a metric. Run `update` so the new lower bound is locked in. Forgetting this means the next person can let the metric creep back up to where it was.
- **After adding a new metric.** Add the metric to `METRICS` in `scripts/ratchet.py`, run `update`.
- **After a refactor that legitimately raises a count** (e.g. moving generated code into the source tree, splitting a large file in a way that bumps `mega_files_800` count). Use `--force --note "..."` and call it out in PR review.

## What to do when CI fails on a ratchet regression

1. Run `python scripts/ratchet.py status` locally.
2. Find the red row. The `description` field tells you what the metric measures.
3. Either fix the regression (preferred) or, if intentional, justify with `update --force --note "..."` and document in the PR.

## Adding a new metric

Edit `scripts/ratchet.py`:

1. Add a regex constant near the existing `RX_*` constants if needed.
2. Add a `Metric(...)` entry to the `METRICS` list with `name`, `direction`, `description`, and `measure` callable.
3. Run `python scripts/ratchet.py update --note "Added <metric_name>."` so the new metric has a baseline.
4. Submit a PR explaining what the metric is and why it's worth tracking.

The bar to add a metric: it must be (a) measurable in pure stdlib without false positives, (b) representative of code-quality movement, (c) not already covered by ruff/mypy/eslint/quality-gate.

## What it deliberately does NOT track

- **Test coverage %** — that needs `pytest-cov` and a coverage XML; the May 2026 review puts coverage measurement in v3.0 epic E9. Once it lands, add a `coverage.line` metric here.
- **Bundle size** — frontend bundle size is in the v3.0 plan as a CI gate (TMX-3614 area). Once measured, add it.
- **Mypy/ruff error counts** — these should be 0 absolutely; failing on any is a hard CI fail, not a ratchet metric.
- **Lighthouse / a11y scores** — Track 5 of the headless-spec validation strategy. Add when those tracks ship.

## Philosophy

> *Per Karpathy on robust software: the bar only moves up. Once you fix something, you add a check that prevents the regression. The ratchet only goes one direction.*

The fewer special cases the better. Every `--force` use is a code smell — if you find yourself doing it more than once a quarter, the metric needs to be redesigned, not the codebase loosened.

## Initial baseline (2026-05-01)

The starting position. Each entry is a debt to be paid down through v3.0:

| Metric | Direction | Baseline | Where it goes wrong |
|---|---|---|---|
| `backend.type_ignore` | down | 3 | Type system bypasses |
| `backend.bare_except` | down | 4 | Silent error swallow |
| `backend.print_in_app` | down | 41 | Use `logger` |
| `backend.any_annotations` | down | 252 | Defeats the type system |
| `backend.todo_without_issue` | down | 16 | Orphan TODOs never get done |
| `backend.placeholder_strings` | down | 2 | Reach 0 in v3.0 (TMX-3001 + TMX-3213) |
| `backend.mega_files_800` | down | 2 | Refactor into smaller modules |
| `frontend.as_any` | down | 2 | TypeScript bypass |
| `frontend.ts_ignore` | down | 0 | Already perfect — keep at 0 |
| `frontend.ts_nocheck` | down | 0 | Already perfect — keep at 0 |
| `frontend.console_log` | down | 10 | Use sonner toasts or structured logger |
| `frontend.any_annotations` | down | 72 | Tighten TS strictness |
| `hygiene.committed_db_files` | down | 3 | Reach 0 in Sprint 0 (TMX-3002) |
| `hygiene.committed_log_files` | down | 22 | Reach 0 in Sprint 0 (TMX-3002) |
| `hygiene.committed_pyc_files` | down | 3 | Reach 0 in Sprint 0 (TMX-3002) |
| `tests.functions` | up | 549 | Grow this — every PR adds tests |
| `tests.files` | up | 94 | Grow this — every PR adds tests |

The ratchet does not prescribe a target — it only enforces that the next measurement is at-or-better than this one. Set targets in `.context/active_tasks.md` per ticket.
