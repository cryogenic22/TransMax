from __future__ import annotations

import ast
import re
from pathlib import Path

from .checks_comments import (
    js_comment_tokens,
    python_comment_tokens,
    strip_js_ts_strings_and_comments,
)
from .context import RuleContext, rule_config


def apply(ctx: RuleContext) -> None:
    _check_line_length(ctx)
    _check_commented_code(ctx)
    if ctx.language == "python":
        _apply_python(ctx)
    elif ctx.language in {"typescript", "javascript"}:
        _apply_web(ctx)


def _enabled(ctx: RuleContext, name: str, default: bool = False) -> bool:
    return bool(rule_config(ctx, name).get("enabled", default))


def _severity(ctx: RuleContext, name: str, default: str) -> str:
    return str(rule_config(ctx, name).get("severity") or default)


def _matches_any_path(path: Path, patterns: list[str]) -> bool:
    rel = str(path).replace("\\", "/")
    return any(Path(rel).match(pat) for pat in patterns)


def _check_line_length(ctx: RuleContext) -> None:
    name = "line_length"
    if not _enabled(ctx, name, default=False):
        return
    rule = rule_config(ctx, name)
    max_len = int(rule.get("max_length", 120) or 120)
    ignore = list(rule.get("ignore_patterns") or [])
    exceptions = list(rule.get("exceptions") or [])
    if exceptions and _matches_any_path(ctx.file_path, exceptions):
        return

    severity = _severity(ctx, name, default="warning")
    for i, line in enumerate(ctx.lines, 1):
        raw = line.rstrip("\n")
        if len(raw) <= max_len:
            continue
        if ignore and any(re.search(pat, raw) for pat in ignore):
            continue
        ctx.add_issue(
            file=str(ctx.file_path),
            line=i,
            rule=name,
            severity=severity,
            message=f"Line exceeds {max_len} characters.",
            snippet=raw[:120],
            suggestion="Wrap long expressions/strings or extract helpers; prefer readability over dense lines.",
        )


def _check_commented_code(ctx: RuleContext) -> None:
    name = "commented_code"
    if not _enabled(ctx, name, default=False):
        return
    rule = rule_config(ctx, name)
    min_lines = int(rule.get("min_lines", 5) or 5)
    exceptions = list(rule.get("exceptions") or [])
    if exceptions and _matches_any_path(ctx.file_path, exceptions):
        return

    tokens: list[tuple[int, str]]
    if ctx.language == "python":
        tokens = python_comment_tokens(ctx.content)
    elif ctx.language in {"typescript", "javascript"}:
        tokens = js_comment_tokens(ctx.lines)
    else:
        return

    comment_by_line: dict[int, str] = {}
    for line_no, raw in tokens:
        if line_no <= 0:
            continue
        comment_by_line[int(line_no)] = str(raw)

    if not comment_by_line:
        return

    sorted_lines = sorted(comment_by_line.keys())
    run: list[int] = []
    for line_no in sorted_lines:
        if not run or line_no == run[-1] + 1:
            run.append(line_no)
            continue
        _emit_commented_code_run(ctx, run, comment_by_line, min_lines=min_lines)
        run = [line_no]
    _emit_commented_code_run(ctx, run, comment_by_line, min_lines=min_lines)


def _emit_commented_code_run(
    ctx: RuleContext, run: list[int], comment_by_line: dict[int, str], *, min_lines: int
) -> None:
    if len(run) < min_lines:
        return
    comments = [_normalize_comment_text(comment_by_line.get(n, "")) for n in run]
    code_like = sum(1 for c in comments if _looks_like_code(c, ctx.language))
    if code_like < max(3, int(len(run) * 0.6)):
        return

    severity = _severity(ctx, "commented_code", default="warning")
    ctx.add_issue(
        file=str(ctx.file_path),
        line=int(run[0]),
        rule="commented_code",
        severity=severity,
        message=f"Commented-out code block detected ({len(run)} lines).",
        suggestion="Delete dead code; rely on version control. If needed, link to a design note/issue instead.",
    )


def _normalize_comment_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("#"):
        return text.lstrip("#").strip()
    if text.startswith("//"):
        return text[2:].strip()
    if text.startswith("/*"):
        return text[2:].strip("*/").strip()
    if text.startswith("*"):
        return text[1:].strip()
    return text


def _looks_like_code(text: str, language: str) -> bool:
    if not text:
        return False
    if text.startswith(("@", "eslint", "prettier", "noqa", "fmt:", "ruff:")):
        return False
    if re.match(r"^[-*]\s+\w", text):
        return False

    if language == "python":
        return bool(
            re.search(
                r"^\s*(def|class|if|elif|else|for|while|try|except|with|return|import|from)\b",
                text,
            )
            or re.search(r"[:=]\s*[^:]+$", text)
            or re.search(r"\)\s*:$", text)
        )

    return bool(
        re.search(
            r"^\s*(function|const|let|var|if|for|while|try|catch|return|import|export|class)\b",
            text,
        )
        or "=>" in text
        or "{" in text
        or "};" in text
    )


def _apply_python(ctx: RuleContext) -> None:
    try:
        tree = ast.parse(ctx.content, filename=str(ctx.file_path))
    except SyntaxError:
        return

    _check_parameter_count(ctx, tree)
    _check_nesting_depth(ctx, tree)
    _check_dataclass_field_count(ctx, tree)
    _check_excessive_cast(ctx, tree)


def _apply_web(ctx: RuleContext) -> None:
    _check_no_var(ctx)
    _check_react_hooks_rules(ctx)
    _check_missing_key_prop(ctx)


def _check_no_var(ctx: RuleContext) -> None:
    name = "no_var"
    if not _enabled(ctx, name, default=False):
        return
    severity = _severity(ctx, name, default="error")

    cleaned_lines = strip_js_ts_strings_and_comments(ctx.content).splitlines()
    for i, (raw, cleaned) in enumerate(zip(ctx.lines, cleaned_lines, strict=False), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        if re.search(r"\bvar\s+\w", cleaned):
            ctx.add_issue(
                file=str(ctx.file_path),
                line=i,
                rule=name,
                severity=severity,
                message="Avoid `var`; use `const` (preferred) or `let`.",
                snippet=stripped[:120],
                suggestion="Replace `var` with `const`/`let`.",
            )


def _check_parameter_count(ctx: RuleContext, tree: ast.AST) -> None:
    name = "parameter_count"
    if not _enabled(ctx, name, default=False):
        return

    rule = rule_config(ctx, name)
    max_params = int(rule.get("max_parameters", 5) or 5)
    severity = _severity(ctx, name, default="warning")

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        total = _count_parameters(node.args)

        if total > max_params:
            ctx.add_issue(
                file=str(ctx.file_path),
                line=int(getattr(node, "lineno", 1) or 1),
                rule=name,
                severity=severity,
                message=f"Function '{node.name}' has {total} parameters (max: {max_params}).",
                suggestion="Consider grouping parameters into a dataclass/struct or splitting responsibilities.",
            )


def _count_parameters(args: ast.arguments) -> int:
    total = len(getattr(args, "posonlyargs", []) or [])
    total += len(getattr(args, "args", []) or [])
    total += len(getattr(args, "kwonlyargs", []) or [])
    total += 1 if getattr(args, "vararg", None) is not None else 0
    total += 1 if getattr(args, "kwarg", None) is not None else 0
    return max(0, total - _receiver_discount(args))


def _receiver_discount(args: ast.arguments) -> int:
    first = (getattr(args, "args", []) or [None])[0]
    if isinstance(first, ast.arg) and first.arg in {"self", "cls"}:
        return 1
    return 0


def _max_nesting(node: ast.AST, *, depth: int = 0) -> int:
    max_depth = depth

    def _child_depth(child: ast.AST) -> int:
        return _max_nesting(child, depth=depth + 1)

    children: list[ast.AST] = []
    if isinstance(node, ast.If | ast.For | ast.AsyncFor | ast.While):
        children = [*node.body, *node.orelse]
    elif isinstance(node, ast.Try):
        children = [*node.body, *node.orelse, *node.finalbody, *(h.body for h in node.handlers)]
        flat: list[ast.AST] = []
        for item in children:
            if isinstance(item, list):
                flat.extend(item)
            else:
                flat.append(item)
        children = flat
    elif isinstance(node, ast.With | ast.AsyncWith):
        children = list(node.body)
    elif isinstance(node, ast.Match):
        for case in node.cases:
            children.extend(case.body)

    for child in children:
        max_depth = max(max_depth, _child_depth(child))
    return max_depth


def _check_nesting_depth(ctx: RuleContext, tree: ast.AST) -> None:
    name = "nesting_depth"
    if not _enabled(ctx, name, default=False):
        return

    rule = rule_config(ctx, name)
    max_depth = int(rule.get("max_depth", 4) or 4)
    severity = _severity(ctx, name, default="warning")

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        depth = 0
        for stmt in node.body:
            depth = max(depth, _max_nesting(stmt, depth=0))
        if depth > max_depth:
            ctx.add_issue(
                file=str(ctx.file_path),
                line=int(getattr(node, "lineno", 1) or 1),
                rule=name,
                severity=severity,
                message=f"Function '{node.name}' nests {depth} levels (max: {max_depth}).",
                suggestion="Flatten control flow with guard clauses or extract helpers.",
            )


def _check_dataclass_field_count(ctx: RuleContext, tree: ast.AST) -> None:
    name = "dataclass_field_count"
    if not _enabled(ctx, name, default=False):
        return
    rule = rule_config(ctx, name)
    max_fields = int(rule.get("max_fields", 20) or 20)
    severity = _severity(ctx, name, default="info")

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_dataclass(node):
            continue
        fields = _count_dataclass_fields(node)

        if fields > max_fields:
            ctx.add_issue(
                file=str(ctx.file_path),
                line=int(getattr(node, "lineno", 1) or 1),
                rule=name,
                severity=severity,
                message=f"Dataclass '{node.name}' has {fields} fields (max: {max_fields}).",
                suggestion="Consider grouping related fields into nested dataclasses or extracting state objects.",
            )


def _is_dataclass(node: ast.ClassDef) -> bool:
    return any(_is_dataclass_decorator(dec) for dec in node.decorator_list)


def _is_dataclass_decorator(dec: ast.AST) -> bool:
    if isinstance(dec, ast.Name):
        return dec.id == "dataclass"
    if isinstance(dec, ast.Attribute):
        return dec.attr == "dataclass"
    if isinstance(dec, ast.Call):
        return _is_dataclass_decorator(dec.func)
    return False


def _count_dataclass_fields(node: ast.ClassDef) -> int:
    fields = 0
    for stmt in node.body:
        if _is_field_annot(stmt) or _is_field_assign(stmt):
            fields += 1
    return fields


def _is_field_annot(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)


def _is_field_assign(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) for t in stmt.targets)


def _check_excessive_cast(ctx: RuleContext, tree: ast.AST) -> None:
    name = "excessive_cast"
    if not _enabled(ctx, name, default=False):
        return
    rule = rule_config(ctx, name)
    max_casts = int(rule.get("max_casts", 12) or 12)
    severity = _severity(ctx, name, default="info")

    imported_cast_name = _imported_cast_name(tree)

    count = 0
    for node in ast.walk(tree):
        if _is_cast_call(node, imported_cast_name):
            count += 1

    if count > max_casts:
        ctx.add_issue(
            file=str(ctx.file_path),
            line=1,
            rule=name,
            severity=severity,
            message=f"File uses `cast()` {count} times (max: {max_casts}).",
            suggestion="Prefer narrowing via control flow, Protocols, or typed helpers instead of repeated casts.",
        )


def _imported_cast_name(tree: ast.AST) -> str | None:
    for node in getattr(tree, "body", []) or []:
        if not isinstance(node, ast.ImportFrom) or node.module != "typing":
            continue
        for alias in node.names:
            if alias.name == "cast":
                return alias.asname or "cast"
    return None


def _is_cast_call(node: ast.AST, imported_cast_name: str | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and imported_cast_name and func.id == imported_cast_name:
        return True
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "cast":
        return False
    return isinstance(func.value, ast.Name) and func.value.id == "typing"


def _check_react_hooks_rules(ctx: RuleContext) -> None:
    name = "react_hooks_rules"
    if not _enabled(ctx, name, default=False):
        return

    # Heuristic-only: catch obvious hook calls inside condition/loop blocks.
    # A correct implementation should use ESLint (`react-hooks/rules-of-hooks`).
    severity = _severity(ctx, name, default="info")
    hook_pattern = re.compile(r"\buse(?:Effect|LayoutEffect|Memo|Callback|State|Reducer|Ref)\s*\(")
    block_stack: list[str] = []
    depth = 0

    for i, line in enumerate(ctx.lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        depth = _pop_blocks_for_closing(depth, block_stack, line.count("{"), line.count("}"))

        if _starts_control_block(line):
            block_stack.append("control")
            depth += 1

        if hook_pattern.search(line) and "control" in block_stack:
            ctx.add_issue(
                file=str(ctx.file_path),
                line=i,
                rule=name,
                severity=severity,
                message="Possible hook usage inside a conditional/loop; violates Rules of Hooks.",
                snippet=stripped[:120],
                suggestion="Move hooks to top level of the component; use ESLint react-hooks for precise detection.",
            )

        depth = _push_blocks_for_opening(depth, block_stack, line.count("{"), line.count("}"))


def _pop_blocks_for_closing(
    depth: int, block_stack: list[str], open_braces: int, close_braces: int
) -> int:
    brace_delta = close_braces - open_braces
    while brace_delta < 0 and depth > 0:
        depth -= 1
        if block_stack:
            block_stack.pop()
        brace_delta += 1
    return depth


def _push_blocks_for_opening(
    depth: int, block_stack: list[str], open_braces: int, close_braces: int
) -> int:
    net = open_braces - close_braces
    if net > 0:
        depth += net
        block_stack.extend(["block"] * net)
    return depth


def _starts_control_block(line: str) -> bool:
    return bool(re.match(r"^\s*(if|for|while|switch)\b", line) and "{" in line)


def _check_missing_key_prop(ctx: RuleContext) -> None:
    name = "missing_key_prop"
    if not _enabled(ctx, name, default=False):
        return

    # Heuristic-only: flag `.map(...) => (<Tag ...>)` cases where the opening tag line lacks `key=`.
    # A correct implementation should use ESLint (`react/jsx-key`).
    severity = _severity(ctx, name, default="info")
    if not str(ctx.file_path).lower().endswith((".tsx", ".jsx")):
        return

    map_start = re.compile(r"\.map\(\s*\(")
    for i, line in enumerate(ctx.lines, 1):
        if map_start.search(line):
            _check_map_window(ctx, start_line=i, severity=severity, rule=name)


def _check_map_window(ctx: RuleContext, *, start_line: int, severity: str, rule: str) -> None:
    window = ctx.lines[start_line : start_line + 25]
    for j, next_line in enumerate(window, 1):
        stripped = next_line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if not stripped.startswith("<") or stripped.startswith("</") or "key=" in stripped:
            continue
        ctx.add_issue(
            file=str(ctx.file_path),
            line=start_line + j,
            rule=rule,
            severity=severity,
            message="Possible missing `key` prop on element returned from `.map()`.",
            snippet=stripped[:120],
            suggestion="Add a stable `key={...}` to the returned element; use ESLint react/jsx-key for precision.",
        )
        break
