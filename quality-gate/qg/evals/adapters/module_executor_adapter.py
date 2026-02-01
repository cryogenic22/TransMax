from __future__ import annotations

from typing import Any, cast


class EvalAdapterError(RuntimeError):
    pass


_EXECUTOR = None


def _get_executor():
    global _EXECUTOR
    if _EXECUTOR is None:
        try:
            from agentfuel_sdk_core.runtime.module_executor import (  # type: ignore[import-not-found]
                ModuleExecutor,
            )
        except Exception as exc:  # pragma: no cover
            raise EvalAdapterError(
                "Cannot import AgentFuel modules. Ensure project packages are importable (e.g. set evals.pythonpath)."
            ) from exc
        _EXECUTOR = ModuleExecutor()
    return _EXECUTOR


def run_case(input_data: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Adapter for AgentFuel's `ModuleExecutor`.

    Input format:
      {
        "module_type": "...",
        "config": {...},
        "input_data": {...}
      }
    """

    module_type = str(input_data.get("module_type") or "").strip()
    if not module_type:
        raise EvalAdapterError("Missing input.module_type")
    module_config = input_data.get("config") or {}
    module_input = input_data.get("input_data") or {}
    if not isinstance(module_config, dict) or not isinstance(module_input, dict):
        raise EvalAdapterError("input.config and input.input_data must be objects.")

    try:
        from agentfuel_sdk_core.runtime.module_executor import (  # type: ignore[import-not-found]
            ModuleExecutionRequest,
        )
    except Exception as exc:  # pragma: no cover
        raise EvalAdapterError(
            "Cannot import AgentFuel modules. Ensure project packages are importable (e.g. set evals.pythonpath)."
        ) from exc

    executor = _get_executor()
    result = cast(Any, executor).execute(
        ModuleExecutionRequest(
            module_type=module_type,
            config=dict(module_config),
            input_data=dict(module_input),
        )
    )
    return {
        "success": bool(getattr(result, "success", False)),
        "output": dict(getattr(result, "output", {}) or {}),
        "explanation": str(getattr(result, "explanation", "") or ""),
        "timing_ms": float(getattr(result, "timing_ms", 0.0) or 0.0),
    }
