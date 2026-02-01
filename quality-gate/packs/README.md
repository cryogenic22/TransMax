# Quality Gate Packs

Packs are small, composable config fragments shipped with `quality-gate/` so each repo can enable only what it needs.

List packs:
- `python quality-gate/tools/list_packs.py`

Enable packs (repo root `.quality-gate.json`):

```json
{
  "packs": ["core", "python", "security"],
  "prs": { "min_score": 92 }
}
```

Notes:
- Packs are applied after `quality-gate/quality-gate.config.json` and before `.quality-gate.json`.
- `.quality-gate.json` still wins for overrides/exceptions.

Default packs:
- `ai_engineering` is enabled by default via `quality-gate/quality-gate.config.json` and is designed to be low-noise (rules only trigger when a file uses async/pydantic/polars or is a test file).
