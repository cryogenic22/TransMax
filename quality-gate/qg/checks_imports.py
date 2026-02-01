from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .types import Severity, parse_severity

AddIssue = Callable[..., None]


def _rule(config: dict[str, Any], name: str) -> dict[str, Any]:
    return (config.get("rules", {}) or {}).get(name, {}) or {}


def _enabled(config: dict[str, Any], name: str, *, default: bool) -> bool:
    return bool(_rule(config, name).get("enabled", default))


def _matches_any_path(path: Path, patterns: list[str]) -> bool:
    rel = str(path).replace("\\", "/")
    return any(Path(rel).match(pat) for pat in patterns)


def _python_import_modules(content: str) -> list[str]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names if getattr(alias, "name", None))
        elif isinstance(node, ast.ImportFrom):
            if int(getattr(node, "level", 0) or 0) != 0:
                continue
            module = str(getattr(node, "module", "") or "").strip()
            if module:
                out.append(module)
    return out


def _scope_matches(file_path: Path, *, include: list[str], exclude: list[str]) -> bool:
    if include and not _matches_any_path(file_path, include):
        return False
    if exclude and _matches_any_path(file_path, exclude):
        return False
    return True


def _collect_forbidden_modules(rule: dict[str, Any], *, file_path: Path) -> set[str]:
    forbidden: set[str] = set()
    for scope in list(rule.get("scopes") or []):
        include = list((scope or {}).get("include") or [])
        exclude = list((scope or {}).get("exclude") or [])
        if not _scope_matches(file_path, include=include, exclude=exclude):
            continue
        for mod in list((scope or {}).get("forbid_modules") or []):
            name = str(mod or "").strip()
            if name:
                forbidden.add(name)
    return forbidden


def _violations_for_imports(imports: list[str], *, forbidden: set[str]) -> set[str]:
    violations: set[str] = set()
    for imp in imports:
        for mod in forbidden:
            if imp == mod or imp.startswith(f"{mod}."):
                violations.add(mod)
    return violations


def check_import_boundaries(
    *,
    rel_file: str,
    file_path: Path,
    content: str,
    language: str,
    config: dict[str, Any],
    add_issue: AddIssue,
) -> None:
    name = "import_boundaries"
    if not _enabled(config, name, default=False):
        return
    if language != "python":
        return

    rule = _rule(config, name)
    severity = parse_severity(rule.get("severity"), default=Severity.ERROR)
    exceptions = list(rule.get("exceptions") or [])
    if exceptions and _matches_any_path(file_path, exceptions):
        return

    imports = _python_import_modules(content)
    if not imports:
        return

    forbidden = _collect_forbidden_modules(rule, file_path=file_path)
    if not forbidden:
        return

    violations = _violations_for_imports(imports, forbidden=forbidden)
    if not violations:
        return

    mods = ", ".join(sorted(violations))
    add_issue(
        line=1,
        rule=name,
        severity=severity,
        message=f"Forbidden import boundary violated in {rel_file}: {mods}.",
        suggestion=(
            "Move vendor integration to `packages/adapters` or behind a Port; "
            "if exempting, add an `exception_debt` entry in `.quality-gate.json`."
        ),
    )


def check_import_count(
    *,
    language: str,
    lines: list[str],
    config: dict[str, Any],
    add_issue: AddIssue,
) -> None:
    name = "import_count"
    if not _enabled(config, name, default=False):
        return

    rule = _rule(config, name)
    max_imports = int(rule.get("max_imports", 20) or 20)
    severity = parse_severity(rule.get("severity"), default=Severity.INFO)

    count = _count_import_statements(language=language, lines=lines)

    if count > max_imports:
        add_issue(
            line=1,
            rule=name,
            severity=severity,
            message=f"Module has {count} import statements (max: {max_imports}).",
            suggestion="Consider splitting responsibilities or consolidating imports.",
        )


def _count_import_statements(*, language: str, lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if language == "python":
            if stripped.startswith(("import ", "from ")):
                count += 1
            continue
        if language in {"typescript", "javascript"} and stripped.startswith("import "):
            count += 1
    return count
