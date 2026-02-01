from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config_loader import load_config
from .executors import EvalExecutorError, PythonCallableExecutor, SubprocessExecutor
from .loaders import DatasetLoadError, discover_datasets, load_dataset
from .matchers import match
from .model import BaselineComparison, EvalCase, EvalResult, EvalSuiteResult
from .regression import load_baseline, write_baseline
from .reporters import print_console_summary, write_json_report

DEFAULT_EVAL_CONFIG: dict[str, Any] = {
    "packs": [],
    "evals": {
        "enabled": False,
        "datasets_path": "eval_datasets/golden",
        "baseline_path": "eval_datasets/regression/baseline.json",
        "thresholds": {
            "min_accuracy": 0.85,
            "regression_tolerance": 0.02,
            "max_latency_p99_ms": 1000,
        },
        "coverage": {"allow_empty": False},
        "executor": {"type": "python_callable", "callable": "", "timeout_ms": 10_000},
    },
}


@dataclass(frozen=True, slots=True)
class EvalRunOutput:
    suite_results: list[EvalSuiteResult]
    report_path: Path | None


@dataclass(frozen=True, slots=True)
class EvalThresholds:
    min_accuracy: float
    max_latency_p99_ms: float
    regression_tolerance: float


@dataclass(frozen=True, slots=True)
class EvalRunRequest:
    suite_names: set[str] | None
    tags: set[str] | None
    executor_override: str | None
    executor_cmd: list[str] | None
    compare_baseline: bool
    update_baseline: bool
    report_path: Path | None


@dataclass(frozen=True, slots=True)
class EvalRuntimeConfig:
    datasets_path: str
    baseline_file: Path
    thresholds: EvalThresholds
    executor_cfg: dict[str, Any]


def _default_root() -> Path:
    # .../quality-gate/qg/evals -> quality-gate -> repo root
    quality_gate_dir = Path(__file__).resolve().parents[2]
    return quality_gate_dir.parent


def run_evals(*, root: Path, config: dict[str, Any], request: EvalRunRequest) -> EvalRunOutput:
    runtime = _build_runtime_config(root=root, config=config)
    suite_results: list[EvalSuiteResult] = []
    for dataset_path in discover_datasets(root, runtime.datasets_path):
        result = _run_dataset_file(
            root=root,
            dataset_path=dataset_path,
            runtime=runtime,
            request=request,
            config=config,
        )
        if result is not None:
            suite_results.append(result)

    if request.report_path:
        write_json_report(
            request.report_path, suite_results=suite_results, meta={"root": str(root)}
        )
    return EvalRunOutput(suite_results=suite_results, report_path=request.report_path)


def _build_runtime_config(*, root: Path, config: dict[str, Any]) -> EvalRuntimeConfig:
    evals_cfg = dict(config.get("evals") or {})
    datasets_path = str(evals_cfg.get("datasets_path") or "eval_datasets/golden")
    baseline_path = Path(
        str(evals_cfg.get("baseline_path") or "eval_datasets/regression/baseline.json")
    )
    thresholds = dict(evals_cfg.get("thresholds") or {})
    thresholds_obj = EvalThresholds(
        min_accuracy=float(thresholds.get("min_accuracy", 0.85)),
        regression_tolerance=float(thresholds.get("regression_tolerance", 0.02)),
        max_latency_p99_ms=float(thresholds.get("max_latency_p99_ms", 1000)),
    )
    executor_cfg = dict(evals_cfg.get("executor") or {})
    return EvalRuntimeConfig(
        datasets_path=datasets_path,
        baseline_file=(root / baseline_path).resolve(),
        thresholds=thresholds_obj,
        executor_cfg=executor_cfg,
    )


def _run_dataset_file(
    *,
    root: Path,
    dataset_path: Path,
    runtime: EvalRuntimeConfig,
    request: EvalRunRequest,
    config: dict[str, Any],
) -> EvalSuiteResult | None:
    dataset_rel = str(dataset_path.relative_to(root)).replace("\\", "/")
    try:
        dataset = load_dataset(dataset_path)
    except DatasetLoadError as exc:
        return _dataset_load_failure(
            dataset_rel=dataset_rel, suite_name=dataset_path.stem, error=str(exc)
        )

    suite_name = dataset.suite.name
    if request.suite_names and suite_name not in request.suite_names:
        return None

    return _run_suite(
        suite_name=suite_name,
        dataset_rel=dataset_rel,
        cases=dataset.cases,
        runtime=runtime,
        request=request,
        config=config,
    )


def _dataset_load_failure(*, dataset_rel: str, suite_name: str, error: str) -> EvalSuiteResult:
    return EvalSuiteResult(
        suite_name=suite_name,
        passed=False,
        cases_passed=0,
        cases_total=0,
        accuracy=0.0,
        metrics={},
        results=[
            EvalResult(
                case_id="dataset_load",
                passed=False,
                expected=None,
                actual=None,
                mismatches=[],
                latency_ms=0.0,
                error=error,
            )
        ],
        dataset_path=dataset_rel,
    )


def _run_suite(
    *,
    suite_name: str,
    dataset_rel: str,
    cases: list[EvalCase],
    runtime: EvalRuntimeConfig,
    request: EvalRunRequest,
    config: dict[str, Any],
) -> EvalSuiteResult:
    executor = _build_executor(
        runtime.executor_cfg, override=request.executor_override, cmd=request.executor_cmd
    )
    selected = _filter_cases(cases, request.tags)
    results, latencies = _execute_cases(
        executor=executor, suite_name=suite_name, cases=selected, config=config
    )
    accuracy = _accuracy(results)
    metrics = _latency_metrics(latencies)
    metrics.update(_outcome_metrics(results))
    baseline_cmp = _maybe_compare_baseline(
        suite_name=suite_name,
        request=request,
        runtime=runtime,
        accuracy=accuracy,
        metrics=metrics,
    )
    passed = _suite_passed(
        accuracy=accuracy, metrics=metrics, thresholds=runtime.thresholds, baseline_cmp=baseline_cmp
    )
    _maybe_update_baseline(
        suite_name=suite_name, request=request, runtime=runtime, accuracy=accuracy, metrics=metrics
    )

    return EvalSuiteResult(
        suite_name=suite_name,
        passed=passed,
        cases_passed=sum(1 for r in results if _scored_passed(r)),
        cases_total=len(results),
        accuracy=accuracy,
        metrics=metrics,
        results=results,
        baseline_comparison=baseline_cmp,
        dataset_path=dataset_rel,
    )


def _filter_cases(cases: list[EvalCase], tags: set[str] | None) -> list[EvalCase]:
    if not tags:
        return list(cases)
    return [c for c in cases if set(c.tags) & tags]


def _execute_cases(
    *,
    executor,
    suite_name: str,
    cases: list[EvalCase],
    config: dict[str, Any],
) -> tuple[list[EvalResult], list[float]]:
    results: list[EvalResult] = []
    latencies: list[float] = []
    for case in cases:
        result = _execute_one(executor=executor, suite_name=suite_name, case=case, config=config)
        results.append(result)
        latencies.append(result.latency_ms)
    return results, latencies


def _execute_one(
    *, executor, suite_name: str, case: EvalCase, config: dict[str, Any]
) -> EvalResult:
    start = time.perf_counter()
    try:
        actual = executor.execute(suite_name=suite_name, case=case, config=config)
        mismatches = _check_case(case=case, actual=actual)
        passed = not mismatches
        err = None
    except EvalExecutorError as exc:
        actual = None
        mismatches = []
        passed = False
        err = str(exc)
    latency_ms = (time.perf_counter() - start) * 1000.0
    expected_status, scored_passed, outcome = _score_case(case=case, passed=passed, config=config)
    return EvalResult(
        case_id=case.id,
        passed=passed,
        scored_passed=scored_passed,
        outcome=outcome,
        expected_status=expected_status,
        expected=case.expected,
        actual=actual,
        mismatches=mismatches,
        latency_ms=latency_ms,
        error=err,
    )


def _accuracy(results: list[EvalResult]) -> float:
    if not results:
        return 1.0
    return sum(1 for r in results if _scored_passed(r)) / len(results)


def _scored_passed(result: EvalResult) -> bool:
    return bool(result.scored_passed if result.scored_passed is not None else result.passed)


def _score_case(
    *, case: EvalCase, passed: bool, config: dict[str, Any]
) -> tuple[str | None, bool, str]:
    expected_status = None
    if isinstance(case.metadata, dict):
        expected_status = str(case.metadata.get("status") or "").strip().lower() or None

    scored_passed = passed
    outcome = "pass" if passed else "fail"
    if (
        expected_status
        and _xfail_enabled(config)
        and expected_status in _xfail_status_values(config)
    ):
        if passed:
            outcome = "xpass"
        else:
            outcome = "xfail"
            scored_passed = True
    return expected_status, scored_passed, outcome


def _xfail_enabled(config: dict[str, Any]) -> bool:
    evals_cfg = dict(config.get("evals") or {})
    xfail_cfg = evals_cfg.get("expected_failures")
    if not isinstance(xfail_cfg, dict):
        return True
    return bool(xfail_cfg.get("enabled", True))


def _xfail_status_values(config: dict[str, Any]) -> set[str]:
    evals_cfg = dict(config.get("evals") or {})
    xfail_cfg = evals_cfg.get("expected_failures")
    if not isinstance(xfail_cfg, dict):
        return {"expected_fail"}
    raw = xfail_cfg.get("status_values") or ["expected_fail"]
    if not isinstance(raw, list):
        return {"expected_fail"}
    return {str(v).strip().lower() for v in raw if str(v).strip()}


def _outcome_metrics(results: list[EvalResult]) -> dict[str, float]:
    counts: dict[str, int] = {"pass": 0, "fail": 0, "xfail": 0, "xpass": 0}
    for r in results:
        key = (r.outcome or ("pass" if _scored_passed(r) else "fail")).strip().lower()
        if key not in counts:
            continue
        counts[key] += 1
    return {f"cases_{k}": float(v) for k, v in counts.items()}


def _suite_passed(
    *,
    accuracy: float,
    metrics: dict[str, float],
    thresholds: EvalThresholds,
    baseline_cmp: BaselineComparison | None,
) -> bool:
    if accuracy < thresholds.min_accuracy:
        return False
    if float(metrics.get("latency_p99_ms", 0.0)) > thresholds.max_latency_p99_ms:
        return False
    return not bool(baseline_cmp and baseline_cmp.regression_detected)


def _maybe_compare_baseline(
    *,
    suite_name: str,
    request: EvalRunRequest,
    runtime: EvalRuntimeConfig,
    accuracy: float,
    metrics: dict[str, float],
) -> BaselineComparison | None:
    if not request.compare_baseline:
        return None
    baseline = load_baseline(runtime.baseline_file)
    return _compare_baseline(
        suite_name=suite_name,
        baseline=baseline,
        current={"accuracy": accuracy, "latency_p99_ms": float(metrics.get("latency_p99_ms", 0.0))},
        regression_tolerance=runtime.thresholds.regression_tolerance,
    )


def _maybe_update_baseline(
    *,
    suite_name: str,
    request: EvalRunRequest,
    runtime: EvalRuntimeConfig,
    accuracy: float,
    metrics: dict[str, float],
) -> None:
    if not request.update_baseline:
        return
    baseline = load_baseline(runtime.baseline_file)
    suites = dict((baseline.suites if baseline else {}) or {})
    suites[suite_name] = {
        "accuracy": accuracy,
        "latency_p99_ms": float(metrics.get("latency_p99_ms", 0.0)),
    }
    write_baseline(
        runtime.baseline_file,
        version=str(os.environ.get("EVAL_BASELINE_VERSION") or "local"),
        suites=suites,
        meta={"updated_by": "qg.evals.runner"},
    )


def _build_executor(exec_cfg: dict[str, Any], *, override: str | None, cmd: list[str] | None):
    from_cmd = _executor_from_cmd(exec_cfg, cmd)
    if from_cmd is not None:
        return from_cmd
    from_override = _executor_from_override(override)
    if from_override is not None:
        return from_override
    return _executor_from_config(exec_cfg)


def _executor_from_cmd(exec_cfg: dict[str, Any], cmd: list[str] | None):
    if not cmd:
        return None
    timeout = int(exec_cfg.get("timeout_ms", 10_000) or 10_000)
    return SubprocessExecutor(command=tuple(cmd), timeout_ms=timeout)


def _executor_from_override(override: str | None):
    if not (override and override.startswith("python:")):
        return None
    return PythonCallableExecutor(callable_path=override.split("python:", 1)[1])


def _executor_from_config(exec_cfg: dict[str, Any]):
    kind = str(exec_cfg.get("type") or "python_callable").strip().lower()
    if kind == "python_callable":
        return PythonCallableExecutor(callable_path=str(exec_cfg.get("callable") or ""))
    if kind != "command":
        raise EvalExecutorError(f"Unknown executor type: {kind}")

    timeout = int(exec_cfg.get("timeout_ms", 10_000) or 10_000)
    raw_cmd = exec_cfg.get("command") or []
    cmd_list = [str(x) for x in raw_cmd] if isinstance(raw_cmd, list) else []
    return SubprocessExecutor(command=tuple(cmd_list), timeout_ms=timeout)


def _check_case(*, case: EvalCase, actual: dict[str, Any] | None) -> list[str]:
    if actual is None:
        return ["no_output"]
    if case.expected is not None and not case.assertions:
        return _check_expected(actual, expected=case.expected)
    return _check_assertions(actual, assertions=case.assertions)


def _check_expected(actual: dict[str, Any], *, expected: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key, expected_value in expected.items():
        if key not in actual:
            mismatches.append(f"missing:{key}")
            continue
        if actual.get(key) != expected_value:
            mismatches.append(f"mismatch:{key}")
    return mismatches


def _check_assertions(actual: dict[str, Any], *, assertions: list[dict[str, Any]]) -> list[str]:
    mismatches: list[str] = []
    for assertion in assertions:
        path = str(assertion.get("path") or "")
        matcher = str(assertion.get("matcher") or "exact")
        expected_value = assertion.get("expected")
        actual_value = _get_path(actual, path) if path else actual
        res = match(actual=actual_value, matcher=matcher, expected=expected_value)
        if not res.passed:
            mismatches.append(f"{path or '<root>'}:{matcher}:{res.reason}")
    return mismatches


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in [p for p in (path or "").split(".") if p]:
        tokens = _split_path_segment(part)
        if not tokens:
            return None
        for token in tokens:
            if isinstance(token, str):
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(token)
            else:
                if not isinstance(cur, list):
                    return None
                idx = int(token)
                cur = cur[idx] if 0 <= idx < len(cur) else None
    return cur


_BRACKET_RE = re.compile(r"^(?P<key>[^\[\]]+)?(?P<idx>(?:\[\d+\])*)$")
_IDX_RE = re.compile(r"\[(\d+)\]")


def _split_path_segment(segment: str) -> list[str | int]:
    part = str(segment or "").strip()
    if not part:
        return []
    match_obj = _BRACKET_RE.match(part)
    if match_obj is None:
        return [part]
    key = match_obj.group("key")
    indices = match_obj.group("idx") or ""

    out: list[str | int] = []
    if key:
        out.append(key)
    for m in _IDX_RE.finditer(indices):
        out.append(int(m.group(1)))
    return out


def _latency_metrics(values: list[float]) -> dict[str, float]:
    if not values:
        return {"latency_p50_ms": 0.0, "latency_p95_ms": 0.0, "latency_p99_ms": 0.0}
    s = sorted(values)
    return {
        "latency_p50_ms": _percentile(s, 0.50),
        "latency_p95_ms": _percentile(s, 0.95),
        "latency_p99_ms": _percentile(s, 0.99),
    }


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    q = min(1.0, max(0.0, float(q)))
    idx = int((len(sorted_values) - 1) * q)
    idx = max(0, min(len(sorted_values) - 1, idx))
    return float(sorted_values[idx])


def _compare_baseline(
    *,
    suite_name: str,
    baseline,
    current: dict[str, float],
    regression_tolerance: float,
) -> BaselineComparison | None:
    if baseline is None:
        return None
    prior = dict(baseline.suites.get(suite_name) or {})
    if not prior:
        return None
    deltas = {
        k: float(current.get(k, 0.0)) - float(prior.get(k, 0.0)) for k in set(prior) | set(current)
    }
    regression = False
    if deltas.get("accuracy", 0.0) < -abs(regression_tolerance):
        regression = True
    if deltas.get("latency_p99_ms", 0.0) > abs(regression_tolerance) * 1000.0:
        regression = True
    return BaselineComparison(
        baseline_version=baseline.version,
        regression_detected=regression,
        deltas={k: round(v, 6) for k, v in deltas.items()},
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quality Gate Evals (portable behavioural regression runner)."
    )
    parser.add_argument("--root", help="Project root (default: parent of quality-gate folder).")
    parser.add_argument("--config", help="Path to config JSON file (merged after repo config).")
    parser.add_argument(
        "--suite", action="append", default=[], help="Suite name to run (repeatable)."
    )
    parser.add_argument(
        "--tags", default="", help="Comma-separated tags filter (cases must match any)."
    )
    parser.add_argument(
        "--executor", default=None, help="Executor override (e.g. 'python:package.mod:callable')."
    )
    parser.add_argument(
        "--executor-cmd", nargs=argparse.REMAINDER, help="Executor command override."
    )
    parser.add_argument(
        "--compare-baseline", action="store_true", help="Compare metrics to baseline."
    )
    parser.add_argument(
        "--update-baseline", action="store_true", help="Write/update baseline file."
    )
    parser.add_argument("--report-json", default="", help="Write JSON report to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root, config = _load_root_and_config(args)
    if not bool(dict(config.get("evals") or {}).get("enabled", False)):
        print("Evals are disabled. Set `evals.enabled=true` in config.")
        return 0

    request = _build_request(args, root=root)
    out = run_evals(root=root, config=config, request=request)
    if not out.suite_results:
        allow_empty = bool(
            dict(dict(config.get("evals") or {}).get("coverage") or {}).get("allow_empty", False)
        )
        if request.suite_names:
            print(
                "No eval suites matched `--suite`. Check dataset metadata.name and/or dataset filenames."
            )
            return 2
        if not allow_empty:
            datasets_path = str(
                dict(config.get("evals") or {}).get("datasets_path") or "eval_datasets/golden"
            )
            print(f"No eval datasets found under '{datasets_path}'.")
            return 2
    print_console_summary(out.suite_results)
    if any(not r.passed for r in out.suite_results):
        return 2
    return 0


def _load_root_and_config(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    root = Path(args.root).resolve() if args.root else _default_root()
    quality_gate_dir = (root / "quality-gate").resolve()
    config, _sources = load_config(
        script_dir=quality_gate_dir,
        root_dir=root,
        config_path=args.config,
        default_config=DEFAULT_EVAL_CONFIG,
    )
    _apply_pythonpath(root=root, config=config)
    return root, config


def _apply_pythonpath(*, root: Path, config: dict[str, Any]) -> None:
    evals_cfg = dict(config.get("evals") or {})
    raw = evals_cfg.get("pythonpath") or []
    if not isinstance(raw, list):
        raise RuntimeError("Invalid config: evals.pythonpath must be an array of paths.")

    missing: list[str] = []
    resolved: list[str] = []
    for entry in raw:
        value = str(entry or "").strip()
        if not value:
            continue
        path = (root / value).resolve()
        if not path.exists():
            missing.append(value)
            continue
        resolved.append(str(path))

    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Invalid config: evals.pythonpath entries not found: {joined}")

    for path in reversed(resolved):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)


def _build_request(args: argparse.Namespace, *, root: Path) -> EvalRunRequest:
    tags = _parse_tag_set(str(args.tags or ""))
    suite_names = {s for s in (args.suite or []) if s} or None
    cmd = _normalize_executor_cmd(list(args.executor_cmd or []))
    report_path = _resolve_report_path(root, str(args.report_json or ""))
    return EvalRunRequest(
        suite_names=suite_names,
        tags=tags,
        executor_override=args.executor,
        executor_cmd=cmd,
        compare_baseline=bool(args.compare_baseline),
        update_baseline=bool(args.update_baseline),
        report_path=report_path,
    )


def _parse_tag_set(raw: str) -> set[str] | None:
    tags = {t.strip() for t in str(raw or "").split(",") if t.strip()}
    return tags or None


def _normalize_executor_cmd(cmd: list[str]) -> list[str] | None:
    out = [str(x) for x in cmd if str(x)]
    if out and out[0] == "--":
        out = out[1:]
    return out or None


def _resolve_report_path(root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (root / p).resolve()
