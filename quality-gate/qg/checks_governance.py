from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .types import Severity, parse_severity

AddIssue = Callable[..., None]


def _rule(config: dict[str, Any], name: str) -> dict[str, Any]:
    return (config.get("rules", {}) or {}).get(name, {}) or {}


def _enabled(config: dict[str, Any], name: str, *, default: bool) -> bool:
    return bool(_rule(config, name).get("enabled", default))


def _collect_rule_exceptions(raw_rules: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for rule_name, rule in (raw_rules or {}).items():
        if not isinstance(rule, dict):
            continue
        for key in ("exceptions", "exceptions_paths"):
            items = rule.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                path = str(item or "").strip()
                if path:
                    out.add((str(rule_name), path))
    return out


def _collect_debt_entries(raw: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for entry in raw.get("exception_debt", []) or []:
        if not isinstance(entry, dict):
            continue
        rule = str(entry.get("rule") or "").strip()
        path = str(entry.get("path") or "").strip()
        if rule and path:
            out.add((rule, path))
    return out


def check_exception_debt(*, root_dir: Path, config: dict[str, Any], add_issue: AddIssue) -> None:
    name = "exception_debt"
    if not _enabled(config, name, default=False):
        return

    raw_path = root_dir / ".quality-gate.json"
    if not raw_path.exists():
        return

    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        add_issue(
            file=".quality-gate.json",
            line=1,
            rule=name,
            severity=Severity.ERROR,
            message=f"Failed to parse .quality-gate.json: {exc}",
            suggestion="Fix invalid JSON so the gate can enforce exception governance.",
        )
        return

    severity = parse_severity(_rule(config, name).get("severity"), default=Severity.WARNING)
    exceptions = _collect_rule_exceptions(dict(raw.get("rules") or {}))
    if not exceptions:
        return

    debt = _collect_debt_entries(raw)
    missing = sorted(exceptions - debt)
    if missing:
        formatted = "; ".join([f"{r}:{p}" for r, p in missing[:8]])
        suffix = "" if len(missing) <= 8 else f" (+{len(missing) - 8} more)"
        add_issue(
            file=".quality-gate.json",
            line=1,
            rule=name,
            severity=severity,
            message=f"Undocumented Quality Gate exceptions found: {formatted}{suffix}.",
            suggestion="Add entries under `exception_debt` with {rule, path, reason, owner, until} so exceptions are tracked and time-bounded.",
        )
