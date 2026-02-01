from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model import EvalSuiteResult


def to_json_report(*, suite_results: list[EvalSuiteResult], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "meta": dict(meta),
        "suites": [asdict(s) for s in suite_results],
    }


def write_json_report(
    path: Path, *, suite_results: list[EvalSuiteResult], meta: dict[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = to_json_report(suite_results=suite_results, meta=meta)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def print_console_summary(suite_results: list[EvalSuiteResult]) -> None:
    if not suite_results:
        print("No eval suites executed.")
        return
    total_cases = sum(r.cases_total for r in suite_results)
    total_passed = sum(r.cases_passed for r in suite_results)
    overall = (total_passed / total_cases) if total_cases else 1.0
    total_xfail = sum(int(r.metrics.get("cases_xfail", 0.0) or 0.0) for r in suite_results)
    total_xpass = sum(int(r.metrics.get("cases_xpass", 0.0) or 0.0) for r in suite_results)
    print("EVAL SUMMARY")
    print(
        f"Suites: {len(suite_results)}  Cases: {total_cases}  Passed: {total_passed}  Accuracy: {overall:.3f}"
    )
    if total_xfail or total_xpass:
        print(f"Expected failures: xfail={total_xfail} xpass={total_xpass}")
    failing = [r for r in suite_results if not r.passed]
    if failing:
        print("Failing suites:")
        for r in failing:
            print(f"  - {r.suite_name}: {r.accuracy:.3f} ({r.cases_passed}/{r.cases_total})")
