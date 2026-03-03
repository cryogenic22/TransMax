"""Tests for PharmaQualityGate protocol compliance and behavior."""

from transmax_sdk.quality.gate import PharmaQualityGate
from transmax_sdk.quality.protocol import QualityGateProtocol
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.types import Severity


class TestPharmaQualityGateProtocol:
    def test_satisfies_protocol(self):
        gate = PharmaQualityGate()
        assert isinstance(gate, QualityGateProtocol)

    def test_check_segment_returns_list(self):
        gate = PharmaQualityGate()
        result = gate.check_segment("Hello", "Bonjour", "en", "fr")
        assert isinstance(result, list)

    def test_clean_translation_no_defects(self):
        gate = PharmaQualityGate()
        result = gate.check_segment(
            "Hello world", "Bonjour le monde", "en", "fr"
        )
        # No numeric, no units, no PII, etc.
        assert len(result) == 0

    def test_evaluate_verdict_pass(self):
        gate = PharmaQualityGate()
        verdict = gate.evaluate_verdict([])
        assert verdict["status"] == "PASS"

    def test_evaluate_verdict_blocked_on_critical(self):
        from transmax_sdk.types import QualityDefect
        gate = PharmaQualityGate()
        defects = [
            QualityDefect(category="NUMERIC_MISMATCH", severity=Severity.CRITICAL, message="Missing 10")
        ]
        verdict = gate.evaluate_verdict(defects)
        assert verdict["status"] == "BLOCKED"
        assert verdict["metrics"]["critical"] == 1

    def test_evaluate_verdict_review_on_major(self):
        from transmax_sdk.types import QualityDefect
        gate = PharmaQualityGate()
        defects = [
            QualityDefect(category="TERMINOLOGY", severity=Severity.MAJOR, message="Glossary miss")
        ]
        verdict = gate.evaluate_verdict(defects)
        assert verdict["status"] == "REVIEW_REQUIRED"

    def test_compare_scorecards_degraded(self):
        gate = PharmaQualityGate()
        old = {"critical": 0, "major": 1, "minor": 2}
        new = {"critical": 1, "major": 1, "minor": 2}
        assert gate.compare_scorecards(old, new) == "DEGRADED"

    def test_compare_scorecards_improved(self):
        gate = PharmaQualityGate()
        old = {"critical": 1, "major": 2, "minor": 3}
        new = {"critical": 0, "major": 2, "minor": 3}
        assert gate.compare_scorecards(old, new) == "IMPROVED"

    def test_compare_scorecards_neutral(self):
        gate = PharmaQualityGate()
        same = {"critical": 0, "major": 1, "minor": 2}
        assert gate.compare_scorecards(same, same) == "NEUTRAL"
