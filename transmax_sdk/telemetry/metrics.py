"""Prometheus metrics definitions for all SDK modules."""

from __future__ import annotations

from typing import Optional

try:
    from prometheus_client import Counter, Histogram, Gauge

    translations_total = Counter(
        "transmax_translations_total",
        "Total translation requests",
        ["source_lang", "target_lang", "status"],
    )

    translation_duration_seconds = Histogram(
        "transmax_translation_duration_seconds",
        "Translation pipeline duration",
        ["source_lang", "target_lang"],
        buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
    )

    llm_cost_usd_total = Counter(
        "transmax_llm_cost_usd_total",
        "Total LLM cost in USD",
        ["provider", "model"],
    )

    llm_tokens_total = Counter(
        "transmax_llm_tokens_total",
        "Total LLM tokens",
        ["provider", "direction"],
    )

    quality_defects_total = Counter(
        "transmax_quality_defects_total",
        "Total quality defects found",
        ["severity", "category"],
    )

    tm_hits_total = Counter(
        "transmax_tm_hits_total",
        "Translation memory hits",
        ["type"],
    )

    circuit_breaker_state = Gauge(
        "transmax_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=open, 2=half-open)",
        ["provider"],
    )

    audit_events_total = Counter(
        "transmax_audit_events_total",
        "Total audit events logged",
        ["event_type"],
    )

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Stub objects so code doesn't break without prometheus_client
    class _StubMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def set(self, value): pass
        def observe(self, value): pass

    translations_total = _StubMetric()
    translation_duration_seconds = _StubMetric()
    llm_cost_usd_total = _StubMetric()
    llm_tokens_total = _StubMetric()
    quality_defects_total = _StubMetric()
    tm_hits_total = _StubMetric()
    circuit_breaker_state = _StubMetric()
    audit_events_total = _StubMetric()
