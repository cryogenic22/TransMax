from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .evals.loaders import discover_datasets
from .evals.regression import load_baseline
from .types import Severity, parse_severity

AddIssue = Callable[..., None]


def _evals_cfg(config: dict[str, Any]) -> dict[str, Any]:
    evals = config.get("evals", {})
    return dict(evals or {}) if isinstance(evals, dict) else {}


def _rule(config: dict[str, Any], name: str) -> dict[str, Any]:
    rules = config.get("rules", {})
    return dict((rules or {}).get(name, {}) or {}) if isinstance(rules, dict) else {}


def _enabled(config: dict[str, Any], name: str, *, default: bool) -> bool:
    return bool(_rule(config, name).get("enabled", default))


def _coverage_settings(evals: dict[str, Any]) -> tuple[bool, bool]:
    coverage = dict(evals.get("coverage", {}) or {})
    allow_empty = bool(coverage.get("allow_empty", False))
    require_golden_sets = bool(coverage.get("require_golden_sets", not allow_empty))
    return allow_empty, require_golden_sets


def _dataset_paths(*, root_dir: Path, evals: dict[str, Any]) -> tuple[str, list[Path]]:
    datasets_path = str(evals.get("datasets_path") or "eval_datasets/golden")
    dataset_paths = discover_datasets(root_dir, datasets_path)
    return datasets_path, dataset_paths


def _count_cases(
    *, root_dir: Path, dataset_paths: list[Path], add_issue: AddIssue, severity: Severity, rule: str
) -> tuple[int, dict[str, int]]:
    total_cases = 0
    per_suite: dict[str, int] = {}
    for dataset_path in dataset_paths:
        try:
            dataset = load_suite_deterministic(dataset_path)
        except Exception as exc:
            add_issue(
                file=str(dataset_path.relative_to(root_dir).as_posix()),
                line=1,
                rule=rule,
                severity=severity,
                message=f"Failed to load eval dataset: {exc}",
                suggestion="Fix the dataset format; prefer JSON for portability and deterministic cases.",
            )
            continue
        suite_name = str(dataset.get("suite_name") or dataset_path.stem)
        count = int(dataset.get("cases", 0) or 0)
        total_cases += count
        per_suite[suite_name] = per_suite.get(suite_name, 0) + count
    return total_cases, per_suite


def _emit_eval_issue(
    *, add_issue: AddIssue, file: str, rule: str, severity: Severity, message: str, suggestion: str
) -> None:
    add_issue(
        file=file,
        line=1,
        rule=rule,
        severity=severity,
        message=message,
        suggestion=suggestion,
    )


def _emit_missing_golden(*, add_issue: AddIssue, datasets_path: str, rule: str, severity: Severity) -> None:
    _emit_eval_issue(
        add_issue=add_issue,
        file=str(Path(datasets_path).as_posix()),
        rule=rule,
        severity=severity,
        message="Evals are enabled but no golden datasets were found.",
        suggestion="Add JSON datasets under eval_datasets/golden (or set evals.coverage.allow_empty=true).",
    )


def _emit_total_case_shortage(
    *, add_issue: AddIssue, datasets_path: str, rule: str, severity: Severity, total: int, minimum: int
) -> None:
    _emit_eval_issue(
        add_issue=add_issue,
        file=str(Path(datasets_path).as_posix()),
        rule=rule,
        severity=severity,
        message=f"Too few eval cases: {total} (min: {minimum}).",
        suggestion="Add more golden cases to cover critical behaviours and edge cases.",
    )


def _emit_suite_case_shortages(
    *,
    add_issue: AddIssue,
    datasets_path: str,
    rule: str,
    severity: Severity,
    per_suite: dict[str, int],
    minimum: int,
) -> None:
    for suite_name, count in sorted(per_suite.items()):
        if count >= minimum:
            continue
        _emit_eval_issue(
            add_issue=add_issue,
            file=str(Path(datasets_path).as_posix()),
            rule=rule,
            severity=severity,
            message=f"Suite '{suite_name}' has {count} cases (min: {minimum}).",
            suggestion="Add more cases or lower eval_coverage.min_cases_per_suite.",
        )


def _rule_severity_and_limits(
    *, config: dict[str, Any], rule_name: str, default_severity: Severity
) -> tuple[Severity, int, int]:
    rule = _rule(config, rule_name)
    severity = parse_severity(rule.get("severity"), default=default_severity)
    min_total_cases = int(rule.get("min_total_cases", 1) or 1)
    min_cases_per_suite = int(rule.get("min_cases_per_suite", 0) or 0)
    return severity, min_total_cases, min_cases_per_suite


def _check_case_counts(
    *,
    root_dir: Path,
    add_issue: AddIssue,
    datasets_path: str,
    dataset_paths: list[Path],
    rule: str,
    severity: Severity,
    min_total_cases: int,
    min_cases_per_suite: int,
) -> None:
    total_cases, per_suite = _count_cases(
        root_dir=root_dir,
        dataset_paths=dataset_paths,
        add_issue=add_issue,
        severity=severity,
        rule=rule,
    )
    if total_cases < min_total_cases:
        _emit_total_case_shortage(
            add_issue=add_issue,
            datasets_path=datasets_path,
            rule=rule,
            severity=severity,
            total=total_cases,
            minimum=min_total_cases,
        )
    if min_cases_per_suite > 0:
        _emit_suite_case_shortages(
            add_issue=add_issue,
            datasets_path=datasets_path,
            rule=rule,
            severity=severity,
            per_suite=per_suite,
            minimum=min_cases_per_suite,
        )


def check_eval_coverage(*, root_dir: Path, config: dict[str, Any], add_issue: AddIssue) -> None:
    evals = _evals_cfg(config)
    if not bool(evals.get("enabled", False)):
        return
    name = "eval_coverage"
    if not _enabled(config, name, default=False):
        return

    _allow_empty, require_golden_sets = _coverage_settings(evals)
    datasets_path, dataset_paths = _dataset_paths(root_dir=root_dir, evals=evals)
    severity, min_total_cases, min_cases_per_suite = _rule_severity_and_limits(
        config=config, rule_name=name, default_severity=Severity.WARNING
    )

    if require_golden_sets and not dataset_paths:
        _emit_missing_golden(
            add_issue=add_issue,
            datasets_path=datasets_path,
            rule=name,
            severity=severity,
        )
        return

    if not dataset_paths:
        return

    _check_case_counts(
        root_dir=root_dir,
        add_issue=add_issue,
        datasets_path=datasets_path,
        dataset_paths=dataset_paths,
        severity=severity,
        rule=name,
        min_total_cases=min_total_cases,
        min_cases_per_suite=min_cases_per_suite,
    )


def load_suite_deterministic(dataset_path: Path) -> dict[str, Any]:
    # Avoid importing runner internals; keep this check fast and conservative.
    # For now we only need suite_name and case count, so parse the dataset via the loader.
    from .evals.loaders import load_dataset

    dataset = load_dataset(dataset_path)
    return {"suite_name": dataset.suite.name, "cases": len(dataset.cases)}


def check_eval_thresholds(*, root_dir: Path, config: dict[str, Any], add_issue: AddIssue) -> None:
    evals = _evals_cfg(config)
    if not bool(evals.get("enabled", False)):
        return
    name = "eval_threshold_assertions"
    if not _enabled(config, name, default=False):
        return

    rule = _rule(config, name)
    severity = parse_severity(rule.get("severity"), default=Severity.ERROR)
    thresholds = dict(evals.get("thresholds", {}) or {})
    required = ["min_accuracy", "max_latency_p99_ms", "regression_tolerance"]
    missing = [k for k in required if k not in thresholds]
    if missing:
        add_issue(
            file=str(Path(str(evals.get("datasets_path") or "eval_datasets/golden")).as_posix()),
            line=1,
            rule=name,
            severity=severity,
            message=f"Missing eval threshold(s): {', '.join(missing)}",
            suggestion="Define thresholds under evals.thresholds in .quality-gate.json.",
        )


def check_baseline_exists(*, root_dir: Path, config: dict[str, Any], add_issue: AddIssue) -> None:
    evals = _evals_cfg(config)
    if not bool(evals.get("enabled", False)):
        return
    name = "eval_baseline_exists"
    if not _enabled(config, name, default=False):
        return

    rule = _rule(config, name)
    severity = parse_severity(rule.get("severity"), default=Severity.WARNING)

    coverage = dict(evals.get("coverage", {}) or {})
    require_baseline = bool(coverage.get("require_regression_baseline", False))
    if not require_baseline:
        return

    baseline_rel, baseline_abs = _baseline_paths(root_dir=root_dir, evals=evals)
    if baseline_abs is None:
        _emit_eval_issue(
            add_issue=add_issue,
            file=baseline_rel,
            rule=name,
            severity=severity,
            message="Regression baseline is required but evals.baseline_path is not set.",
            suggestion="Set evals.baseline_path to a JSON file under eval_datasets/regression/.",
        )
        return
    if not _ensure_baseline_ready(
        root_dir=root_dir,
        baseline_abs=baseline_abs,
        baseline_rel=baseline_rel,
        rule=name,
        severity=severity,
        add_issue=add_issue,
    ):
        return
    _validate_baseline(
        baseline_abs=baseline_abs,
        baseline_rel=baseline_rel,
        rule=name,
        severity=severity,
        add_issue=add_issue,
    )


def _baseline_paths(*, root_dir: Path, evals: dict[str, Any]) -> tuple[str, Path | None]:
    baseline_path = str(evals.get("baseline_path") or "").strip()
    baseline_rel = baseline_path.replace("\\", "/") if baseline_path else "evals"
    if not baseline_path:
        return baseline_rel, None
    return baseline_rel, (root_dir / baseline_path).resolve()


def _ensure_baseline_ready(
    *,
    root_dir: Path,
    baseline_abs: Path,
    baseline_rel: str,
    rule: str,
    severity: Severity,
    add_issue: AddIssue,
) -> bool:
    if not _baseline_is_inside_repo(root_dir=root_dir, baseline_abs=baseline_abs):
        _emit_eval_issue(
            add_issue=add_issue,
            file=baseline_rel,
            rule=rule,
            severity=severity,
            message="Baseline path must be within the repo.",
            suggestion="Move the baseline under eval_datasets/regression/.",
        )
        return False
    if not baseline_abs.exists():
        _emit_eval_issue(
            add_issue=add_issue,
            file=baseline_rel,
            rule=rule,
            severity=severity,
            message="Regression baseline file is missing.",
            suggestion="Create the baseline JSON file (or disable require_regression_baseline until ready).",
        )
        return False
    return True


def _baseline_is_inside_repo(*, root_dir: Path, baseline_abs: Path) -> bool:
    try:
        baseline_abs.relative_to(root_dir.resolve())
    except ValueError:
        return False
    return True


def _validate_baseline(
    *,
    baseline_abs: Path,
    baseline_rel: str,
    rule: str,
    severity: Severity,
    add_issue: AddIssue,
) -> None:
    try:
        load_baseline(baseline_abs)
    except Exception as exc:
        add_issue(
            file=baseline_rel,
            line=1,
            rule=rule,
            severity=severity,
            message=f"Regression baseline file is invalid: {exc}",
            suggestion="Regenerate the baseline via `python quality-gate/eval_runner.py --update-baseline`.",
        )
