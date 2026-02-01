from __future__ import annotations

import importlib
import json
import subprocess
from dataclasses import dataclass
from typing import Any

from .model import EvalCase


class EvalExecutorError(RuntimeError):
    pass


class Executor:
    def execute(self, *, suite_name: str, case: EvalCase, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise EvalExecutorError(f"Executor returned {type(value).__name__}, expected dict.")


@dataclass(frozen=True, slots=True)
class PythonCallableExecutor(Executor):
    callable_path: str

    def execute(self, *, suite_name: str, case: EvalCase, config: dict[str, Any]) -> dict[str, Any]:
        func = _import_callable(self.callable_path)
        try:
            out = func(case.input, config)
        except TypeError:
            out = func(case.input)
        return _ensure_mapping(out)


def _import_callable(path: str):
    raw = (path or "").strip()
    if ":" not in raw:
        raise EvalExecutorError("Python callable must be in format 'module.sub:callable_name'.")
    mod, name = raw.split(":", 1)
    module = importlib.import_module(mod)
    func = getattr(module, name, None)
    if func is None:
        raise EvalExecutorError(f"Callable not found: {raw}")
    if not callable(func):
        raise EvalExecutorError(f"Target is not callable: {raw}")
    return func


@dataclass(frozen=True, slots=True)
class SubprocessExecutor(Executor):
    command: tuple[str, ...]
    timeout_ms: int = 10_000

    def execute(self, *, suite_name: str, case: EvalCase, config: dict[str, Any]) -> dict[str, Any]:
        if not self.command:
            raise EvalExecutorError("Subprocess executor requires a non-empty command.")
        payload = _build_payload(suite_name=suite_name, case=case, config=config)
        proc = _run_executor(self.command, payload=payload, timeout_ms=self.timeout_ms)
        decoded = _parse_executor_stdout(proc.stdout)
        return _coerce_executor_output(decoded)


def _build_payload(*, suite_name: str, case: EvalCase, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite": {"name": suite_name},
        "case": {
            "id": case.id,
            "input": case.input,
            "tags": list(case.tags),
            "metadata": case.metadata,
        },
        "config": config,
    }


def _run_executor(command: tuple[str, ...], *, payload: dict[str, Any], timeout_ms: int):
    try:
        proc = subprocess.run(
            list(command),
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=max(0.01, timeout_ms / 1000.0),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvalExecutorError(f"Executor timed out after {timeout_ms}ms") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise EvalExecutorError(
            f"Executor failed (exit={proc.returncode}): {stderr or '<no stderr>'}"
        )
    return proc


def _parse_executor_stdout(stdout: bytes) -> Any:
    raw = (stdout or b"").decode("utf-8", errors="replace").strip()
    if not raw:
        raise EvalExecutorError("Executor returned empty stdout.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvalExecutorError("Executor stdout was not valid JSON.") from exc


def _coerce_executor_output(decoded: Any) -> dict[str, Any]:
    if isinstance(decoded, dict) and isinstance(decoded.get("actual"), dict):
        return dict(decoded["actual"])
    if isinstance(decoded, dict):
        return dict(decoded)
    raise EvalExecutorError("Executor JSON output must be an object (dict).")
