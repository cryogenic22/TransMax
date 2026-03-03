"""PharmaQualityGate: composable quality gate wrapping individual check plugins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import QualityDefect, Severity


# Default check plugin registry
_DEFAULT_PLUGINS = None


def _get_default_plugins():
    global _DEFAULT_PLUGINS
    if _DEFAULT_PLUGINS is None:
        from transmax_sdk.quality.checks.numeric import NumericCheck
        from transmax_sdk.quality.checks.units import UnitsCheck
        from transmax_sdk.quality.checks.negation import NegationCheck
        from transmax_sdk.quality.checks.glossary import GlossaryCheck
        from transmax_sdk.quality.checks.pii import PIICheck
        from transmax_sdk.quality.checks.tables import TablesCheck
        from transmax_sdk.quality.checks.placeholders import PlaceholdersCheck
        from transmax_sdk.quality.checks.complexity import ComplexityCheck
        from transmax_sdk.quality.checks.analytical import AnalyticalCheck

        _DEFAULT_PLUGINS = [
            NumericCheck(),
            UnitsCheck(),
            NegationCheck(),
            GlossaryCheck(),
            PIICheck(),
            TablesCheck(),
            PlaceholdersCheck(),
            ComplexityCheck(),
            AnalyticalCheck(),
        ]
    return _DEFAULT_PLUGINS


class PharmaQualityGate:
    """Composable quality gate for pharmaceutical translations.

    Runs a configurable set of check plugins and produces a verdict.
    Supports any-to-any language pairs by passing both source_lang and target_lang.
    """

    def __init__(
        self,
        plugins: Optional[List[Any]] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._plugins = plugins if plugins is not None else _get_default_plugins()
        self._telemetry = telemetry or NoOpTelemetry()

    def check_segment(
        self,
        source_text: str,
        target_text: str,
        source_lang: str = "en",
        target_lang: str = "en",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        """Run all quality checks on a source/target segment pair."""
        all_defects: List[QualityDefect] = []
        constraints = constraints or {}

        with self._telemetry.span("quality_gate.check_segment", {
            "source_lang": source_lang,
            "target_lang": target_lang,
        }):
            self._telemetry.counter("transmax_quality_checks_total")

            for plugin in self._plugins:
                try:
                    defects = plugin.check(
                        source_text=source_text,
                        target_text=target_text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        constraints=constraints,
                    )
                    all_defects.extend(defects)

                    # Track per-check metrics
                    for d in defects:
                        self._telemetry.counter(
                            "transmax_quality_defects_total",
                            labels={"severity": d.severity.value, "category": d.category},
                        )
                except Exception as e:
                    self._telemetry.log_structured(
                        "error",
                        f"Quality check '{plugin.name}' failed: {e}",
                        check=plugin.name,
                    )

        return all_defects

    def evaluate_verdict(self, defects: List[QualityDefect]) -> Dict[str, Any]:
        """Determine PASS/REVIEW_REQUIRED/BLOCKED from defect list."""
        critical = sum(1 for d in defects if d.severity == Severity.CRITICAL)
        major = sum(1 for d in defects if d.severity == Severity.MAJOR)
        minor = sum(1 for d in defects if d.severity == Severity.MINOR)

        if critical > 0:
            status = "BLOCKED"
            reason = f"Blocking: {critical} critical defect(s)."
        elif major > 0:
            status = "REVIEW_REQUIRED"
            reason = f"Review: {major} major defect(s)."
        else:
            status = "PASS"
            reason = "Quality standards met."

        return {
            "status": status,
            "reason": reason,
            "metrics": {"critical": critical, "major": major, "minor": minor},
        }

    def compare_scorecards(
        self, old_metrics: Dict[str, int], new_metrics: Dict[str, int]
    ) -> str:
        """Safety Net: detect regressions. Returns IMPROVED/DEGRADED/NEUTRAL."""
        if new_metrics["critical"] > old_metrics["critical"]:
            return "DEGRADED"
        if new_metrics["major"] > old_metrics["major"]:
            return "DEGRADED"
        if new_metrics["critical"] < old_metrics["critical"]:
            return "IMPROVED"
        if new_metrics["major"] < old_metrics["major"]:
            return "IMPROVED"
        if new_metrics["minor"] < old_metrics["minor"]:
            return "IMPROVED"
        return "NEUTRAL"
