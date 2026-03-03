"""Tests for quality gate telemetry instrumentation."""

from transmax_sdk.quality.gate import PharmaQualityGate
from transmax_sdk.telemetry.noop import NoOpTelemetry


class TestQualityGateTelemetry:
    def test_span_created_on_check(self):
        tel = NoOpTelemetry(record=True)
        gate = PharmaQualityGate(telemetry=tel)
        gate.check_segment("Take 10mg", "Prendre 10mg", "en", "fr")
        assert len(tel.spans) == 1
        assert tel.spans[0][0] == "quality_gate.check_segment"

    def test_counter_incremented(self):
        tel = NoOpTelemetry(record=True)
        gate = PharmaQualityGate(telemetry=tel)
        gate.check_segment("Hello", "Bonjour", "en", "fr")
        counter_names = [c[0] for c in tel.counters]
        assert "transmax_quality_checks_total" in counter_names

    def test_defect_metrics_emitted(self):
        tel = NoOpTelemetry(record=True)
        gate = PharmaQualityGate(telemetry=tel)
        # Trigger a numeric defect
        gate.check_segment("Take 10mg", "Prendre mg", "en", "fr")
        defect_counters = [c for c in tel.counters if c[0] == "transmax_quality_defects_total"]
        assert len(defect_counters) > 0

    def test_span_attributes_include_langs(self):
        tel = NoOpTelemetry(record=True)
        gate = PharmaQualityGate(telemetry=tel)
        gate.check_segment("Test", "Test", "ja", "ar")
        attrs = tel.spans[0][1]
        assert attrs["source_lang"] == "ja"
        assert attrs["target_lang"] == "ar"
