#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _packs_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "packs"


def main() -> int:
    parser = argparse.ArgumentParser(description="List available quality-gate packs (modules).")
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    args = parser.parse_args()

    packs_dir = _packs_dir()
    items: list[dict[str, str]] = []
    for path in sorted(packs_dir.glob("*.json")):
        data = _read_json(path)
        items.append(
            {
                "name": path.stem,
                "description": str(data.get("description") or "").strip(),
                "path": str(path),
            }
        )

    if args.json:
        print(json.dumps(items, indent=2))
    else:
        for item in items:
            desc = item["description"]
            suffix = f" - {desc}" if desc else ""
            print(f"{item['name']}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
