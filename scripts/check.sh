#!/usr/bin/env bash
# TransMax — one-command smoke check. Bootstrapped from kp-sdlc/harness on 2026-05-01.
#
# Adapted for transmax: pip + npm (no uv/pnpm).
# Mirrors CI gates locally; if this passes, CI should too.
set -uo pipefail

cd "$(dirname "$0")/.."  # project root

failed=()
ok() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; failed+=("$1"); }
step() { echo; echo "── $1 ──"; }

# ── Python ──────────────────────────────────────────────────────────────
if [[ -f pyproject.toml ]]; then
  step "Python: ruff check"
  if python -m ruff check app tests scripts 2>&1 | tail -3; then ok "ruff check"; else fail "ruff check"; fi

  step "Python: ruff format --check"
  if python -m ruff format --check app tests scripts 2>&1 | tail -3; then ok "ruff format"; else fail "ruff format"; fi

  step "Python: mypy (app only — strict; tests are exempt for now)"
  if python -m mypy app 2>&1 | tail -3; then ok "mypy"; else fail "mypy"; fi

  step "Python: pytest (excluding evals — those need an LLM key)"
  if python -m pytest tests/ --ignore=tests/evals -q 2>&1 | tail -5; then ok "pytest"; else fail "pytest"; fi
fi

# ── Frontend (npm) ──────────────────────────────────────────────────────
if [[ -f frontend/package.json ]]; then
  step "Frontend: typecheck (tsc --noEmit)"
  if (cd frontend && npx tsc --noEmit 2>&1 | tail -3); then ok "typecheck"; else fail "typecheck"; fi

  step "Frontend: lint"
  if (cd frontend && npm run lint 2>&1 | tail -3); then ok "lint"; else fail "lint"; fi

  step "Frontend: vitest unit tests"
  if (cd frontend && npm test -- --run 2>&1 | tail -5); then ok "vitest"; else fail "vitest"; fi

  step "Frontend: build"
  if (cd frontend && npm run build 2>&1 | tail -3); then ok "build"; else fail "build"; fi
fi

# ── KP_SDLC quality-gate ────────────────────────────────────────────────
if [[ -f quality-gate/quality_gate.py ]]; then
  step "KP_SDLC: quality-gate"
  if python quality-gate/quality_gate.py --root . --json > /dev/null 2>&1; then ok "QG"; else fail "QG"; fi
fi

# ── Ratchet ─────────────────────────────────────────────────────────────
if [[ -f scripts/ratchet.py ]]; then
  step "Ratchet: monotonic-improvement check"
  if python scripts/ratchet.py check 2>&1 | tail -10; then ok "ratchet"; else fail "ratchet"; fi
fi

# ── Summary ─────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════"
if [ ${#failed[@]} -eq 0 ]; then
  echo "  All checks passed."
  exit 0
else
  echo "  ${#failed[@]} check(s) failed:"
  for c in "${failed[@]}"; do echo "    - $c"; done
  exit 1
fi
