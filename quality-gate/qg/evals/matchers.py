from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MatchResult:
    passed: bool
    reason: str = ""


def match(*, actual: Any, matcher: str, expected: Any) -> MatchResult:
    name = (matcher or "exact").strip().lower()
    if name == "exact":
        return MatchResult(passed=actual == expected, reason=_cmp_reason(actual, expected))
    if name == "contains":
        return _contains(actual, expected)
    if name == "excludes":
        return _excludes(actual, expected)
    if name == "range":
        return _in_range(actual, expected)
    if name == "regex":
        return _regex(actual, expected)
    if name == "subset":
        return _subset(actual, expected)
    return MatchResult(passed=False, reason=f"Unknown matcher '{matcher}'.")


def _cmp_reason(actual: Any, expected: Any) -> str:
    if actual == expected:
        return ""
    return f"expected={expected!r} actual={actual!r}"


def _contains(actual: Any, expected: Any) -> MatchResult:
    if isinstance(actual, str) and isinstance(expected, str):
        ok = expected in actual
        return MatchResult(passed=ok, reason=_cmp_reason(actual, expected))
    if isinstance(actual, (list, tuple, set)):
        ok = expected in actual
        return MatchResult(passed=ok, reason=_cmp_reason(actual, expected))
    return MatchResult(passed=False, reason="contains expects actual to be a string or list-like.")


def _excludes(actual: Any, expected: Any) -> MatchResult:
    if isinstance(actual, str) and isinstance(expected, str):
        ok = expected not in actual
        return MatchResult(passed=ok, reason=_cmp_reason(actual, expected))
    if isinstance(actual, (list, tuple, set)):
        ok = expected not in actual
        return MatchResult(passed=ok, reason=_cmp_reason(actual, expected))
    return MatchResult(passed=False, reason="excludes expects actual to be a string or list-like.")


def _in_range(actual: Any, expected: Any) -> MatchResult:
    if not isinstance(expected, dict):
        return MatchResult(
            passed=False, reason="range matcher expects expected to be an object: {min, max}."
        )
    lo = expected.get("min")
    hi = expected.get("max")
    if not isinstance(actual, (int, float)):
        return MatchResult(passed=False, reason="range matcher expects actual to be a number.")
    if lo is not None and actual < lo:
        return MatchResult(passed=False, reason=f"actual {actual} < min {lo}")
    if hi is not None and actual > hi:
        return MatchResult(passed=False, reason=f"actual {actual} > max {hi}")
    return MatchResult(passed=True)


def _regex(actual: Any, expected: Any) -> MatchResult:
    if not isinstance(actual, str) or not isinstance(expected, str):
        return MatchResult(
            passed=False, reason="regex matcher expects actual and expected to be strings."
        )
    try:
        ok = re.search(expected, actual) is not None
    except re.error as exc:
        return MatchResult(passed=False, reason=f"Invalid regex: {exc}")
    return MatchResult(passed=ok, reason=_cmp_reason(actual, expected))


def _subset(actual: Any, expected: Any) -> MatchResult:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return MatchResult(
            passed=False, reason="subset matcher expects dict actual and dict expected."
        )
    missing = [k for k, v in expected.items() if k not in actual or actual.get(k) != v]
    if missing:
        return MatchResult(passed=False, reason=f"Missing/mismatched keys: {missing[:10]}")
    return MatchResult(passed=True)
