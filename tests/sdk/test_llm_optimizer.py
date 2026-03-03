"""Tests for LLM optimizer (batching, model routing, TM separation)."""

from transmax_sdk.llm.optimizer import LLMOptimizer
from transmax_sdk.types import TranslationSegment


class TestLLMOptimizer:
    def test_create_batches(self):
        opt = LLMOptimizer(batch_size=3)
        segments = [
            TranslationSegment(segment_id=f"s{i}", source_text=f"Text {i}")
            for i in range(7)
        ]
        batches = opt.create_batches(segments)
        assert len(batches) == 3  # [3, 3, 1]
        assert len(batches[0]) == 3
        assert len(batches[2]) == 1

    def test_select_model_simple(self):
        opt = LLMOptimizer(complexity_threshold=100)
        seg = TranslationSegment(segment_id="s1", source_text="Short text")
        assert opt.select_model(seg) == "gpt-4o-mini"

    def test_select_model_complex(self):
        opt = LLMOptimizer(complexity_threshold=10)
        seg = TranslationSegment(segment_id="s1", source_text="A much longer text that exceeds the threshold")
        assert opt.select_model(seg) == "gpt-4o"

    def test_select_model_special_chars(self):
        opt = LLMOptimizer()
        seg = TranslationSegment(segment_id="s1", source_text="Formula: $E = mc^2$")
        assert opt.select_model(seg) == "gpt-4o"

    def test_separate_tm_matches(self):
        opt = LLMOptimizer()
        segments = [
            TranslationSegment(segment_id="s1", source_text="Hello"),
            TranslationSegment(segment_id="s2", source_text="World"),
            TranslationSegment(segment_id="s3", source_text="Test"),
        ]
        tm_results = {
            "s1": {"type": "exact", "target": "Bonjour", "score": 1.0},
            "s3": {"type": "fuzzy", "target": "Essai", "score": 0.9},
        }
        need_llm, tm_resolved = opt.separate_tm_matches(segments, tm_results)
        assert len(need_llm) == 2  # s2 and s3 (fuzzy is not exact)
        assert len(tm_resolved) == 1  # s1 only

    def test_estimate_batch_cost(self):
        opt = LLMOptimizer()
        segments = [
            TranslationSegment(segment_id="s1", source_text="Take 10mg daily"),
        ]
        cost = opt.estimate_batch_cost(segments)
        assert cost > 0
