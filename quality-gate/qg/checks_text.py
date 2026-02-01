from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .checks_comments import js_comment_tokens, python_comment_tokens
from .types import Severity, parse_severity

AddIssue = Callable[..., None]

_PY_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore(?:\[(?P<codes>[^\]]+)\])?")


def _rule(config: dict[str, Any], name: str) -> dict[str, Any]:
    return (config.get("rules", {}) or {}).get(name, {}) or {}


def _enabled(config: dict[str, Any], name: str, *, default: bool) -> bool:
    return bool(_rule(config, name).get("enabled", default))


def check_no_todo_fixme(
    *,
    file_path: Path,
    content: str,
    lines: list[str],
    language: str,
    config: dict[str, Any],
    add_issue: AddIssue,
) -> None:
    name = "no_todo_fixme"
    if not _enabled(config, name, default=True):
        return

    rule = _rule(config, name)
    patterns = [
        str(p) for p in (rule.get("patterns", ["TODO", "FIXME", "XXX", "HACK", "BUG"]) or [])
    ]
    allow_with_issue = bool(rule.get("allow_with_issue", True))
    issue_pattern = str(rule.get("issue_pattern", r"(TODO|FIXME|XXX|HACK|BUG)\s*\(#\d+\)"))
    severity = parse_severity(rule.get("severity"), default=Severity.ERROR)

    tokens = (
        python_comment_tokens(content)
        if language == "python"
        else js_comment_tokens(lines)
        if language in {"typescript", "javascript"}
        else []
    )
    if not tokens:
        return

    issue_re = re.compile(issue_pattern, re.IGNORECASE)
    pattern_res = [(pat, re.compile(rf"\\b{re.escape(pat)}\\b", re.IGNORECASE)) for pat in patterns]
    for line_no, comment in tokens:
        for pat, pat_re in pattern_res:
            if not pat_re.search(comment):
                continue
            if allow_with_issue and issue_re.search(comment):
                continue
            add_issue(
                line=int(line_no),
                rule=name,
                severity=severity,
                message=f"Found '{pat}'. Either fix it or link to an issue.",
                snippet=str(lines[line_no - 1].strip()[:100]) if 0 < line_no <= len(lines) else "",
                suggestion=f"Change to: {pat}(#123): description",
            )


def check_no_type_escape(
    *,
    file_path: Path,
    content: str,
    lines: list[str],
    language: str,
    config: dict[str, Any],
    add_issue: AddIssue,
) -> None:
    name = "no_type_escape"
    if not _enabled(config, name, default=True):
        return

    rule = _rule(config, name)
    patterns_cfg = dict(rule.get("patterns", {}) or {})
    patterns = [str(p) for p in (patterns_cfg.get(language) or [])]
    allowed_codes = {
        str(c).strip()
        for c in (rule.get("allowed_python_type_ignore_codes", []) or [])
        if str(c).strip()
    }
    severity = parse_severity(rule.get("severity"), default=Severity.WARNING)
    if not patterns:
        return

    if language == "python":
        _check_python_type_escape(
            content=content,
            lines=lines,
            patterns=patterns,
            allowed_codes=allowed_codes,
            severity=severity,
            add_issue=add_issue,
        )
        return

    if language in {"typescript", "javascript"}:
        _check_comment_substrings(
            tokens=js_comment_tokens(lines),
            patterns=patterns,
            lines=lines,
            severity=severity,
            add_issue=add_issue,
        )


def _check_python_type_escape(
    *,
    content: str,
    lines: list[str],
    patterns: list[str],
    allowed_codes: set[str],
    severity: Severity,
    add_issue: AddIssue,
) -> None:
    tokens = python_comment_tokens(content)
    if not tokens:
        return
    if "# type: ignore" not in patterns:
        _check_comment_substrings(
            tokens=tokens, patterns=patterns, lines=lines, severity=severity, add_issue=add_issue
        )
        return

    for line_no, comment in tokens:
        if "# type: ignore" not in comment:
            continue
        message = _python_type_ignore_message(comment, allowed_codes=allowed_codes)
        if message is None:
            continue
        add_issue(
            line=int(line_no),
            rule="no_type_escape",
            severity=severity,
            message=message,
            snippet=str(lines[line_no - 1].strip()[:100]) if 0 < line_no <= len(lines) else "",
            suggestion="Fix the type properly instead of escaping.",
        )


def _python_type_ignore_message(comment: str, *, allowed_codes: set[str]) -> str | None:
    match = _PY_TYPE_IGNORE_RE.search(comment)
    if not match:
        return "Type escape found: '# type: ignore'"
    codes_raw = match.group("codes")
    if codes_raw is None:
        return "Type escape found: '# type: ignore'"
    codes = {c.strip() for c in codes_raw.split(",") if c.strip()}
    if codes and allowed_codes and codes.issubset(allowed_codes):
        return None
    return f"Type escape found: '# type: ignore[{codes_raw}]'"


def _check_comment_substrings(
    *,
    tokens: list[tuple[int, str]],
    patterns: list[str],
    lines: list[str],
    severity: Severity,
    add_issue: AddIssue,
) -> None:
    for line_no, comment in tokens:
        for pat in patterns:
            if pat not in comment:
                continue
            add_issue(
                line=int(line_no),
                rule="no_type_escape",
                severity=severity,
                message=f"Type escape found: '{pat}'",
                snippet=str(lines[line_no - 1].strip()[:100]) if 0 < line_no <= len(lines) else "",
                suggestion="Fix the type properly instead of escaping.",
            )
