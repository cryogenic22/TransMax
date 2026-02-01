from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = out.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            out[key] = deep_merge(existing, value)
        else:
            out[key] = value
    return out


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pack_paths(*, script_dir: Path, pack_names: list[str]) -> list[Path]:
    packs_dir = script_dir / "packs"
    if not pack_names:
        return []
    out: list[Path] = []
    packs_root = packs_dir.resolve()
    for raw in pack_names:
        name = str(raw).strip()
        if not name:
            continue
        if not _PACK_NAME_RE.match(name):
            continue
        candidate = (packs_root / f"{name}.json").resolve()
        try:
            candidate.relative_to(packs_root)
        except ValueError:
            continue
        if candidate.exists():
            out.append(candidate)
    return out


def config_sources(*, script_dir: Path, root_dir: Path, config_path: str | None) -> list[Path]:
    sources: list[Path] = []
    defaults_path = script_dir / "quality-gate.config.json"
    if defaults_path.exists():
        sources.append(defaults_path)
    root_override = root_dir / ".quality-gate.json"
    if root_override.exists():
        sources.append(root_override)
    root_config = root_dir / "quality-gate.config.json"
    if root_config.exists():
        sources.append(root_config)
    if config_path:
        p = Path(config_path)
        if p.exists():
            sources.append(p)
    return sources


def load_config(
    *,
    script_dir: Path,
    root_dir: Path,
    config_path: str | None,
    default_config: dict[str, Any],
) -> tuple[dict[str, Any], list[Path]]:
    base_sources = config_sources(script_dir=script_dir, root_dir=root_dir, config_path=config_path)

    early: dict[str, Any] = dict(default_config)
    for src in base_sources:
        early = deep_merge(early, read_json(src))

    packs = early.get("packs", [])
    pack_names = [str(p) for p in packs] if isinstance(packs, list) else []
    pack_sources = pack_paths(script_dir=script_dir, pack_names=pack_names)

    final_sources: list[Path] = []
    defaults_path = script_dir / "quality-gate.config.json"
    if defaults_path.exists():
        final_sources.append(defaults_path)
    final_sources.extend(pack_sources)
    for src in base_sources:
        if src == defaults_path:
            continue
        final_sources.append(src)

    merged: dict[str, Any] = dict(default_config)
    for src in final_sources:
        merged = deep_merge(merged, read_json(src))
    return merged, final_sources
