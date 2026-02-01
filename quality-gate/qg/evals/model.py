from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    input: dict[str, Any]
    expected: dict[str, Any] | None = None
    assertions: list[dict[str, Any]] = field(default_factory=list)
    tags: tuple[str, ...] = ()
    timeout_ms: int = 5_000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvalResult:
    case_id: str
    passed: bool
    expected: dict[str, Any] | None
    actual: dict[str, Any] | None
    mismatches: list[str]
    latency_ms: float
    error: str | None = None
    scored_passed: bool | None = None
    outcome: str = ""
    expected_status: str | None = None


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    baseline_version: str
    regression_detected: bool
    deltas: dict[str, float]


@dataclass(frozen=True, slots=True)
class EvalSuite:
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvalSuiteResult:
    suite_name: str
    passed: bool
    cases_passed: int
    cases_total: int
    accuracy: float
    metrics: dict[str, float]
    results: list[EvalResult]
    baseline_comparison: BaselineComparison | None = None
    dataset_path: str | None = None
