"""Tests for CostTracker with tiktoken token counting."""

import pytest
from transmax_sdk.telemetry.cost import CostTracker


class TestCostTracker:
    def test_count_tokens_basic(self):
        tracker = CostTracker()
        count = tracker.count_tokens("Hello, world!")
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self):
        tracker = CostTracker()
        assert tracker.count_tokens("") == 0

    def test_count_tokens_longer_text(self):
        tracker = CostTracker()
        short = tracker.count_tokens("Hello")
        long = tracker.count_tokens("Hello, this is a much longer sentence with many more tokens")
        assert long > short

    def test_estimate_cost_input(self):
        tracker = CostTracker()
        cost = tracker.estimate_cost("Take 10mg daily with food", model="gpt-4o")
        assert cost > 0
        assert cost < 1.0  # Sanity: single sentence shouldn't cost $1

    def test_estimate_cost_different_models(self):
        tracker = CostTracker()
        text = "Administer 500mg ibuprofen every 6 hours"
        cost_4o = tracker.estimate_cost(text, model="gpt-4o")
        cost_mini = tracker.estimate_cost(text, model="gpt-4o-mini")
        assert cost_mini < cost_4o  # Mini is cheaper

    def test_record_usage(self):
        tracker = CostTracker()
        rec = tracker.record(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        assert rec.cost_usd > 0
        assert rec.provider == "openai"
        assert tracker.total_cost == rec.cost_usd
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 500

    def test_multiple_records_accumulate(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", 100, 50)
        tracker.record("openai", "gpt-4o", 200, 100)
        assert len(tracker.records) == 2
        assert tracker.total_input_tokens == 300
        assert tracker.total_output_tokens == 150

    def test_reset(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", 1000, 500)
        assert tracker.total_cost > 0
        tracker.reset()
        assert tracker.total_cost == 0.0
        assert len(tracker.records) == 0

    def test_record_with_request_id(self):
        tracker = CostTracker()
        rec = tracker.record("openai", "gpt-4o", 100, 50, request_id="req_123")
        assert rec.request_id == "req_123"

    def test_custom_cost_rates(self):
        tracker = CostTracker(
            cost_per_1k_input={"custom-model": 0.1},
            cost_per_1k_output={"custom-model": 0.2},
        )
        rec = tracker.record("custom", "custom-model", 1000, 1000)
        expected = (1000 / 1000) * 0.1 + (1000 / 1000) * 0.2
        assert abs(rec.cost_usd - expected) < 0.001

    def test_unknown_model_uses_default_rate(self):
        tracker = CostTracker()
        rec = tracker.record("openai", "unknown-model-xyz", 1000, 500)
        assert rec.cost_usd > 0  # Falls back to default rates
