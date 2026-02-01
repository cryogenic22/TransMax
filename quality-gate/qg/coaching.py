from __future__ import annotations

_COACHING_SUGGESTIONS: dict[str, str] = {
    "file_size": "Split the file into smaller modules (extract cohesive helpers/classes; keep one responsibility per file).",
    "function_size": "Extract helper functions and use guard clauses; aim for one level of abstraction per function.",
    "max_complexity": "Reduce branching: extract helpers, use guard clauses, or split into smaller functions/strategies.",
    "parameter_count": "Introduce a request/dataclass parameter object or group related params into a typed structure.",
    "nesting_depth": "Use early returns/guard clauses and extract inner blocks into helpers to flatten control flow.",
    "no_todo_fixme": "Either remove the TODO/FIXME now or link it to a tracked issue (e.g., TODO(#123): ...).",
    "no_debug_statements": "Remove debug statements or guard them behind a logger with appropriate level.",
    "no_type_escape": "Avoid `# type: ignore`; fix the type or narrow it with Protocols/TypedDicts/casts with justification.",
    "mutable_default": "Replace mutable defaults with `None` + initialization or `default_factory` (dataclasses/pydantic).",
    "bare_except": "Catch specific exceptions; never use bare `except:` (it catches KeyboardInterrupt/SystemExit).",
    "sql_injection": "Avoid string interpolation in SQL; use parameterized queries and validate identifiers.",
    "command_injection": "Avoid shell execution; use `subprocess.run([...], check=True)` with args list (no `shell=True`).",
    "async_blocking_calls": "Use native async libraries (httpx/aiohttp/aiofiles) or move blocking work off the event loop.",
    "async_thread_offload": "Thread offload is a last resort; prefer true async APIs and document why offload is needed.",
    "pydantic_deprecated_apis": "Prefer Pydantic v2 APIs (`model_dump`, `model_validate`, `ConfigDict`).",
    "pydantic_mutable_field_default": "Use `Field(default_factory=...)` for mutable fields; avoid `=[]` / `default=[]`.",
    "polars_apply": "Avoid `.apply()`; prefer vectorized Polars expressions for performance.",
    "polars_to_pandas": "Avoid `.to_pandas()` unless required; it negates Polars performance benefits.",
    "polars_row_iteration": "Avoid iterating rows; use expressions or joins/aggregations instead.",
    "test_overmocking": "Too much mocking often means you’re testing internals; prefer integration-style tests or refactor seams.",
    "test_mock_return_without_assert": "If you set mock return values, assert calls/awaits or validate outcomes that can fail.",
}


def coaching_suggestion(rule: str) -> str:
    return _COACHING_SUGGESTIONS.get(str(rule), "")

