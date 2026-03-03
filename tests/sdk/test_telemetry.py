"""Tests for telemetry protocol and NoOp implementation."""

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class TestTelemetryProtocol:
    def test_noop_satisfies_protocol(self):
        noop = NoOpTelemetry()
        assert isinstance(noop, TelemetryProtocol)


class TestNoOpTelemetry:
    def test_span_does_not_raise(self):
        noop = NoOpTelemetry()
        with noop.span("test_span", {"key": "value"}):
            pass  # Should not raise

    def test_counter_does_not_raise(self):
        noop = NoOpTelemetry()
        noop.counter("test_counter", 5.0)  # Should not raise

    def test_histogram_does_not_raise(self):
        noop = NoOpTelemetry()
        noop.histogram("test_hist", 1.5)

    def test_gauge_does_not_raise(self):
        noop = NoOpTelemetry()
        noop.gauge("test_gauge", 42.0)

    def test_log_structured_does_not_raise(self):
        noop = NoOpTelemetry()
        noop.log_structured("info", "test message", extra="data")

    def test_record_mode_captures_spans(self):
        noop = NoOpTelemetry(record=True)
        with noop.span("my_span", {"a": 1}):
            pass
        assert len(noop.spans) == 1
        assert noop.spans[0] == ("my_span", {"a": 1})

    def test_record_mode_captures_counters(self):
        noop = NoOpTelemetry(record=True)
        noop.counter("hits", 3.0, labels={"lang": "ja"})
        assert len(noop.counters) == 1
        assert noop.counters[0] == ("hits", 3.0, {"lang": "ja"})

    def test_record_mode_captures_histograms(self):
        noop = NoOpTelemetry(record=True)
        noop.histogram("latency", 0.5, labels={"op": "translate"})
        assert len(noop.histograms) == 1

    def test_record_mode_captures_gauges(self):
        noop = NoOpTelemetry(record=True)
        noop.gauge("queue_size", 10.0)
        assert len(noop.gauges) == 1

    def test_record_mode_captures_logs(self):
        noop = NoOpTelemetry(record=True)
        noop.log_structured("warning", "high drift", score=0.25)
        assert len(noop.logs) == 1
        assert noop.logs[0]["level"] == "warning"
        assert noop.logs[0]["score"] == 0.25

    def test_non_record_mode_does_not_capture(self):
        noop = NoOpTelemetry(record=False)
        noop.counter("test", 1.0)
        with noop.span("test"):
            pass
        assert len(noop.counters) == 0
        assert len(noop.spans) == 0

    def test_reset_clears_all(self):
        noop = NoOpTelemetry(record=True)
        noop.counter("a")
        noop.histogram("b", 1.0)
        noop.gauge("c", 2.0)
        noop.log_structured("info", "msg")
        with noop.span("s"):
            pass
        noop.reset()
        assert len(noop.counters) == 0
        assert len(noop.histograms) == 0
        assert len(noop.gauges) == 0
        assert len(noop.logs) == 0
        assert len(noop.spans) == 0
