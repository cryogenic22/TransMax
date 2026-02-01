# Quality Gate Adoption (Portable)

This guide is designed to be copied *with* `quality-gate/` into any repo.

## What you get

- **Layer 0 (stdlib-only):** `python quality-gate/quality_gate.py` (PRS + static hygiene rules)
- **Layer 0.5 (optional):** `python quality-gate/eval_runner.py` (offline golden evals + regression checks)
- **Layer 1 (local):** pre-commit hooks (fast feedback while coding)
- **Layer 2 (CI):** GitHub Actions / GitLab / Azure Pipelines templates

## Recommended policy (defaults)

- PRS gate on changed files: **`prs.min_score >= 85`** (raise per-repo when ready)
- `thresholds.error_count = 0`
- Allow warnings initially, then add a warning budget and ratchet down.

## Install (developer workflow)

### Option A: Minimal (offline-friendly)

```bash
cp quality-gate/.pre-commit-config.min.yaml .pre-commit-config.yaml
pre-commit install
```

### Option B: Full (may require network)

```bash
cp quality-gate/.pre-commit-config.yaml .pre-commit-config.yaml
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push
```

## CI (merge gate)

### GitHub Actions (changed files only)

Copy:

```bash
mkdir -p .github/workflows
cp quality-gate/workflows/quality-gate.yml .github/workflows/quality-gate.yml
```

This gates only changed files so legacy debt doesn’t block new work.

## Repo configuration (`/.quality-gate.json`)

Do **not** edit `quality-gate/quality-gate.config.json` in each repo. Keep repo overrides in `.quality-gate.json`.

Minimum example:

```json
{
  "packs": ["core", "python", "security"],
  "paths": { "exclude": ["**/node_modules/**", "**/.venv/**"] },
  "prs": { "min_score": 85 }
}
```

## Running manually

```bash
python quality-gate/quality_gate.py --root . --mode check --summary .
python quality-gate/quality_gate.py --root . --mode audit --top 25 .
python quality-gate/eval_runner.py --root . --report-json .quality-reports/eval_report.json
python quality-gate/tools/export_quality_csv.py --out .quality-reports/quality_assessment.csv --paths .
```

