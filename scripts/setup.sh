#!/usr/bin/env bash
# TransMax — one-command setup. Bootstrapped from kp-sdlc/harness on 2026-05-01.
#
# Installs Python deps, frontend deps, pre-commit hooks, and runs initial DB migration.
# Idempotent: safe to re-run after pulling new changes.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "── TransMax setup ──"
echo

# ── Python ──────────────────────────────────────────────────────────────
echo "▶ Python deps (requirements.txt)"
python -m pip install --upgrade pip > /dev/null
pip install -r requirements.txt
pip install ruff black mypy types-requests types-redis pre-commit pytest-cov

# ── Frontend ────────────────────────────────────────────────────────────
if [[ -f frontend/package.json ]]; then
  echo
  echo "▶ Frontend deps (npm)"
  (cd frontend && npm ci)
fi

# ── Pre-commit hooks ────────────────────────────────────────────────────
echo
echo "▶ Pre-commit hooks"
pre-commit install --hook-type pre-commit --hook-type prepare-commit-msg

# ── DB migrations (Postgres if DATABASE_URL set; else skip) ─────────────
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo
  echo "▶ Alembic migrations"
  alembic upgrade head
else
  echo
  echo "▶ DB: DATABASE_URL not set; skipping migrations (default uses sqlite:///./transmax.db)"
fi

# ── Ratchet baseline check ──────────────────────────────────────────────
if [[ -f scripts/ratchet.py && -f ratchet/baseline.json ]]; then
  echo
  echo "▶ Ratchet baseline"
  python scripts/ratchet.py status
fi

echo
echo "✓ Setup complete. Run ./scripts/check.sh for the smoke test."
