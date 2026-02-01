from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Baseline:
    version: str
    suites: dict[str, dict[str, float]]
    meta: dict[str, Any]


def load_baseline(path: Path) -> Baseline | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    version = str(raw.get("version") or "unknown")
    suites_raw = raw.get("suites") or {}
    suites: dict[str, dict[str, float]] = {}
    if isinstance(suites_raw, dict):
        for k, v in suites_raw.items():
            if isinstance(v, dict):
                suites[str(k)] = {str(m): float(val) for m, val in v.items() if _is_number(val)}
    meta = raw.get("meta") or {}
    return Baseline(
        version=version, suites=suites, meta=dict(meta) if isinstance(meta, dict) else {}
    )


def write_baseline(
    path: Path, *, version: str, suites: dict[str, dict[str, float]], meta: dict[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": str(version), "meta": dict(meta), "suites": suites}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
