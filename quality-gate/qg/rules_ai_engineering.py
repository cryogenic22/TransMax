from __future__ import annotations

import ast
from collections.abc import Iterable

from .context import RuleContext, rule_config
from .types import Severity, parse_severity


def apply(ctx: RuleContext) -> None:
    if ctx.language != "python":
        return
    try:
        tree = ast.parse(ctx.content, filename=str(ctx.file_path))
    except SyntaxError:
        return

    _check_async_anti_patterns(ctx, tree)
    _check_pydantic_anti_patterns(ctx, tree)
    _check_polars_anti_patterns(ctx, tree)
    if ctx.is_test:
        _check_test_fidelity(ctx, tree)


def _enabled(ctx: RuleContext, name: str, default: bool = False) -> bool:
    return bool(rule_config(ctx, name).get("enabled", default))


def _severity(ctx: RuleContext, name: str, default: Severity) -> Severity:
    return parse_severity(rule_config(ctx, name).get("severity"), default=default)


def _dotted(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _dotted(expr.value)
        if not base:
            return expr.attr
        return f"{base}.{expr.attr}"
    if isinstance(expr, ast.Call):
        return _dotted(expr.func)
    return None


def _iter_ast_nodes(fn: ast.AST) -> Iterable[ast.AST]:
    return ast.walk(fn)


def _has_async_fn(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(tree))


def _blocking_calls_from_config(ctx: RuleContext) -> set[str]:
    cfg = rule_config(ctx, "async_blocking_calls")
    raw = cfg.get("blocking_calls") or []
    return {str(v).strip() for v in raw if str(v).strip()}


class _AsyncAntiPatternVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        ctx: RuleContext,
        blocking_calls: set[str],
        blocking_severity: Severity,
        offload_severity: Severity,
    ) -> None:
        self._ctx = ctx
        self._blocking_calls = blocking_calls
        self._blocking_severity = blocking_severity
        self._offload_severity = offload_severity
        self._current_fn: str | None = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev = self._current_fn
        self._current_fn = node.name
        self.generic_visit(node)
        self._current_fn = prev

    def visit_Call(self, node: ast.Call) -> None:
        if self._current_fn is None:
            self.generic_visit(node)
            return
        call = _dotted(node.func) or ""
        self._maybe_emit_blocking(node, call)
        self._maybe_emit_offload(node, call)
        self.generic_visit(node)

    def _maybe_emit_blocking(self, node: ast.Call, call: str) -> None:
        if not _enabled(self._ctx, "async_blocking_calls", default=False):
            return
        if call not in self._blocking_calls:
            return
        self._ctx.add_issue(
            file=str(self._ctx.file_path),
            line=int(getattr(node, "lineno", 1) or 1),
            rule="async_blocking_calls",
            severity=self._blocking_severity,
            message=f"Blocking call `{call}` inside `async def {self._current_fn}()`.",
            suggestion=_async_alternative(call),
        )

    def _maybe_emit_offload(self, node: ast.Call, call: str) -> None:
        if not _enabled(self._ctx, "async_thread_offload", default=False):
            return
        if call != "asyncio.to_thread" and not call.endswith(".run_in_executor"):
            return
        self._ctx.add_issue(
            file=str(self._ctx.file_path),
            line=int(getattr(node, "lineno", 1) or 1),
            rule="async_thread_offload",
            severity=self._offload_severity,
            message=(
                f"`{call}` detected inside `async def {self._current_fn}()`; "
                "verify this is not hiding blocking I/O."
            ),
            suggestion=(
                "Prefer native async libraries; use thread offload only when unavoidable and clearly documented."
            ),
        )


def _check_async_anti_patterns(ctx: RuleContext, tree: ast.AST) -> None:
    name = "async_blocking_calls"
    offload_name = "async_thread_offload"
    if not _enabled(ctx, name, default=False) and not _enabled(ctx, offload_name, default=False):
        return
    if not _has_async_fn(tree):
        return

    severity = _severity(ctx, name, default=Severity.WARNING)
    offload_severity = _severity(ctx, offload_name, default=Severity.INFO)
    _AsyncAntiPatternVisitor(
        ctx=ctx,
        blocking_calls=_blocking_calls_from_config(ctx),
        blocking_severity=severity,
        offload_severity=offload_severity,
    ).visit(tree)


def _async_alternative(call: str) -> str:
    alternatives = {
        "time.sleep": "Use `await asyncio.sleep(...)` instead of `time.sleep(...)`.",
        "requests.get": "Use `httpx.AsyncClient.get(...)` / `aiohttp` instead of `requests` in async code.",
        "requests.post": "Use `httpx.AsyncClient.post(...)` / `aiohttp` instead of `requests` in async code.",
        "subprocess.run": "Use `await asyncio.create_subprocess_exec(...)` for async subprocess execution.",
        "os.system": "Use `await asyncio.create_subprocess_exec(...)` and avoid shell invocation where possible.",
        "open": "Use `aiofiles.open(...)` if file I/O must occur in an async handler.",
        "sqlite3.connect": "Use an async DB driver or run DB access outside the event loop.",
        "psycopg2.connect": "Use `asyncpg` or psycopg3 async mode.",
    }
    return alternatives.get(call, "Use an async alternative or move blocking work off the event loop.")


def _has_pydantic_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(str(alias.name).startswith("pydantic") for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module and str(node.module).startswith("pydantic"):
            return True
    return False


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        base_name = _dotted(base) or ""
        if base_name.endswith("BaseModel") or base_name.endswith("BaseSettings"):
            return True
    return False


def _pydantic_context(tree: ast.AST) -> bool:
    if _has_pydantic_import(tree):
        return True
    return any(isinstance(n, ast.ClassDef) and _is_pydantic_model(n) for n in ast.walk(tree))


def _is_v1_validator(dec: ast.AST) -> bool:
    name = _dotted(dec) or ""
    if not name.endswith("validator"):
        return False
    return not name.endswith(("field_validator", "model_validator"))


def _mutable_literal(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Dict, ast.Set))


class _PydanticAntiPatternVisitor(ast.NodeVisitor):
    def __init__(self, *, ctx: RuleContext, mut_sev: Severity, depr_sev: Severity) -> None:
        self._ctx = ctx
        self._mut_sev = mut_sev
        self._depr_sev = depr_sev

    def visit_Call(self, node: ast.Call) -> None:
        if _enabled(self._ctx, "pydantic_deprecated_apis", default=False):
            self._emit_deprecated_call(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if _is_pydantic_model(node):
            if _enabled(self._ctx, "pydantic_deprecated_apis", default=False):
                self._check_deprecated_in_class(node)
            if _enabled(self._ctx, "pydantic_mutable_field_default", default=False):
                self._check_mutable_defaults(node)
        self.generic_visit(node)

    def _emit_deprecated_call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in {"dict", "parse_obj"}:
            return
        self._ctx.add_issue(
            file=str(self._ctx.file_path),
            line=int(getattr(node, "lineno", 1) or 1),
            rule="pydantic_deprecated_apis",
            severity=self._depr_sev,
            message=f"Deprecated Pydantic API `{node.func.attr}()` detected.",
            suggestion="On Pydantic v2 prefer `.model_dump()` / `.model_validate()`.",
        )

    def _check_deprecated_in_class(self, node: ast.ClassDef) -> None:
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Config":
                self._ctx.add_issue(
                    file=str(self._ctx.file_path),
                    line=int(getattr(item, "lineno", 1) or 1),
                    rule="pydantic_deprecated_apis",
                    severity=self._depr_sev,
                    message="Pydantic v1-style `class Config:` detected.",
                    suggestion="On Pydantic v2 use `model_config = ConfigDict(...)`.",
                )
            if isinstance(item, ast.FunctionDef) and any(_is_v1_validator(d) for d in item.decorator_list):
                self._ctx.add_issue(
                    file=str(self._ctx.file_path),
                    line=int(getattr(item, "lineno", 1) or 1),
                    rule="pydantic_deprecated_apis",
                    severity=self._depr_sev,
                    message="Pydantic v1-style `@validator` detected.",
                    suggestion="On Pydantic v2 use `@field_validator` / `@model_validator`.",
                )

    def _check_mutable_defaults(self, node: ast.ClassDef) -> None:
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and item.value is not None and _mutable_literal(item.value):
                self._ctx.add_issue(
                    file=str(self._ctx.file_path),
                    line=int(getattr(item, "lineno", 1) or 1),
                    rule="pydantic_mutable_field_default",
                    severity=self._mut_sev,
                    message=f"Mutable default value in Pydantic model `{node.name}` field.",
                    suggestion="Use `Field(default_factory=...)` instead of a mutable literal default.",
                )
            if isinstance(item, ast.Assign):
                self._check_field_default(node, item)

    def _check_field_default(self, model: ast.ClassDef, item: ast.Assign) -> None:
        if not isinstance(item.value, ast.Call):
            return
        call = _dotted(item.value.func) or ""
        if not call.endswith("Field"):
            return
        if any(getattr(kw, "arg", None) == "default_factory" for kw in item.value.keywords):
            return
        for kw in item.value.keywords:
            if kw.arg == "default" and kw.value is not None and _mutable_literal(kw.value):
                self._ctx.add_issue(
                    file=str(self._ctx.file_path),
                    line=int(getattr(item, "lineno", 1) or 1),
                    rule="pydantic_mutable_field_default",
                    severity=self._mut_sev,
                    message=f"Mutable `Field(default=...)` value in Pydantic model `{model.name}`.",
                    suggestion="Prefer `Field(default_factory=...)` for mutable defaults.",
                )


def _check_pydantic_anti_patterns(ctx: RuleContext, tree: ast.AST) -> None:
    name_mut = "pydantic_mutable_field_default"
    name_depr = "pydantic_deprecated_apis"
    if not _enabled(ctx, name_mut, default=False) and not _enabled(ctx, name_depr, default=False):
        return
    if not _pydantic_context(tree):
        return

    mut_sev = _severity(ctx, name_mut, default=Severity.WARNING)
    depr_sev = _severity(ctx, name_depr, default=Severity.INFO)
    _PydanticAntiPatternVisitor(ctx=ctx, mut_sev=mut_sev, depr_sev=depr_sev).visit(tree)


def _polars_context(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if str(alias.name) == "polars" or str(alias.name).startswith("polars."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if str(node.module) == "polars" or str(node.module).startswith("polars."):
                return True
    return False


_POLARS_RULES: dict[str, str] = {
    "polars_apply": "Prefer Polars expressions (`pl.when`, `pl.col`, `.map_elements(...)` with dtype).",
    "polars_to_pandas": "Avoid `.to_pandas()` unless required; keep data in Polars for performance.",
    "polars_row_iteration": "Avoid row-by-row iteration; use vectorised Polars expressions instead.",
}


def _check_polars_anti_patterns(ctx: RuleContext, tree: ast.AST) -> None:
    enabled = {r for r in _POLARS_RULES if _enabled(ctx, r, default=False)}
    if not enabled:
        return
    if not _polars_context(tree):
        return

    severities = {r: _severity(ctx, r, default=Severity.INFO) for r in enabled}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        _maybe_emit_polars_call(ctx, node, enabled=enabled, severities=severities)


def _maybe_emit_polars_call(
    ctx: RuleContext,
    node: ast.Call,
    *,
    enabled: set[str],
    severities: dict[str, Severity],
) -> None:
    attr = node.func.attr if isinstance(node.func, ast.Attribute) else ""
    if attr == "apply" and "polars_apply" in enabled:
        _emit_polars(ctx, node, rule="polars_apply", sev=severities["polars_apply"])
        return
    if attr == "to_pandas" and "polars_to_pandas" in enabled:
        _emit_polars(ctx, node, rule="polars_to_pandas", sev=severities["polars_to_pandas"])
        return
    if attr in {"rows", "iter_rows", "iterrows", "itertuples"} and "polars_row_iteration" in enabled:
        _emit_polars(ctx, node, rule="polars_row_iteration", sev=severities["polars_row_iteration"], attr=attr)


def _emit_polars(ctx: RuleContext, node: ast.Call, *, rule: str, sev: Severity, attr: str | None = None) -> None:
    message = "Polars `.apply()` detected; it is often slow compared to expressions."
    if rule == "polars_to_pandas":
        message = "Polars `.to_pandas()` detected; this can negate Polars performance benefits."
    if rule == "polars_row_iteration":
        message = f"Row iteration via `.{attr}()` detected." if attr else "Row iteration detected."
    ctx.add_issue(
        file=str(ctx.file_path),
        line=int(getattr(node, "lineno", 1) or 1),
        rule=rule,
        severity=sev,
        message=message,
        suggestion=_POLARS_RULES[rule],
    )


def _check_test_fidelity(ctx: RuleContext, tree: ast.AST) -> None:
    name = "test_overmocking"
    name_rv = "test_mock_return_without_assert"
    if not _enabled(ctx, name, default=False) and not _enabled(ctx, name_rv, default=False):
        return

    cfg = rule_config(ctx, name)
    max_mocks = int(cfg.get("max_mocks_per_test", 5) or 5)
    sev = _severity(ctx, name, default=Severity.INFO)
    rv_sev = _severity(ctx, name_rv, default=Severity.INFO)
    for fn in ast.walk(tree):
        if not _is_test_fn(fn):
            continue
        mock_count, sets_return_value, has_mock_assertions = _mock_metrics(fn)
        _maybe_emit_overmocking(ctx, fn, mock_count=mock_count, max_mocks=max_mocks, sev=sev)
        _maybe_emit_return_value(
            ctx,
            fn,
            sets_return_value=sets_return_value,
            has_mock_assertions=has_mock_assertions,
            sev=rv_sev,
        )


def _is_test_fn(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")


def _mock_metrics(fn: ast.AST) -> tuple[int, bool, bool]:
    count = 0
    sets_return_value = False
    has_mock_assertions = False
    for node in _iter_ast_nodes(fn):
        if isinstance(node, ast.Call):
            count += int(_is_mock_patch_call(node))
            has_mock_assertions = has_mock_assertions or _is_mock_assert_call(node)
        if isinstance(node, ast.Attribute) and node.attr == "call_count":
            has_mock_assertions = True
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _sets_mock_return_value(node):
            sets_return_value = True
    return count, sets_return_value, has_mock_assertions


def _is_mock_patch_call(node: ast.Call) -> bool:
    call = _dotted(node.func) or ""
    return call.endswith(".patch") or call == "patch" or ".patch." in call or call.startswith("mocker.")


def _is_mock_assert_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert_")


def _sets_mock_return_value(node: ast.AST) -> bool:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    for target in targets:
        if isinstance(target, ast.Attribute) and target.attr in {"return_value", "side_effect"}:
            return True
    return False


def _maybe_emit_overmocking(
    ctx: RuleContext,
    fn: ast.AST,
    *,
    mock_count: int,
    max_mocks: int,
    sev: Severity,
) -> None:
    if not _enabled(ctx, "test_overmocking", default=False):
        return
    if mock_count <= max_mocks:
        return
    ctx.add_issue(
        file=str(ctx.file_path),
        line=int(getattr(fn, "lineno", 1) or 1),
        rule="test_overmocking",
        severity=sev,
        message=f"Test `{getattr(fn, 'name', '<test>')}` uses {mock_count} mocks/patches (threshold: {max_mocks}).",
        suggestion="Consider adding integration-style tests or refactoring to reduce mocking surface area.",
    )


def _maybe_emit_return_value(
    ctx: RuleContext,
    fn: ast.AST,
    *,
    sets_return_value: bool,
    has_mock_assertions: bool,
    sev: Severity,
) -> None:
    if not _enabled(ctx, "test_mock_return_without_assert", default=False):
        return
    if not sets_return_value or has_mock_assertions:
        return
    ctx.add_issue(
        file=str(ctx.file_path),
        line=int(getattr(fn, "lineno", 1) or 1),
        rule="test_mock_return_without_assert",
        severity=sev,
        message=f"Test `{getattr(fn, 'name', '<test>')}` sets mock return values but has no obvious mock-call assertions.",
        suggestion="Add `assert_called*` / `assert_awaited*` checks or validate outcomes so the test can fail.",
    )
