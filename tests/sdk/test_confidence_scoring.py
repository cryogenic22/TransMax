"""Tests for confidence scoring."""

from transmax_sdk.quality.scoring import ConfidenceScorer, ScoringWeights


class TestConfidenceScorer:
    def test_perfect_score_no_defects(self):
        scorer = ConfidenceScorer()
        result = scorer.calculate_score(defects=[], source_text="Hello world")
        assert result.final_score > 80
        assert result.band in ("Very High", "High")

    def test_critical_defect_blocks(self):
        scorer = ConfidenceScorer()
        defects = [{"severity": "CRITICAL", "category": "NUMERIC_MISMATCH"}]
        result = scorer.calculate_score(defects=defects)
        assert result.final_score == 0.0
        assert result.status == "BLOCKED"
        assert result.band == "Blocked"

    def test_major_defects_reduce_score(self):
        scorer = ConfidenceScorer()
        defects = [
            {"severity": "MAJOR", "category": "TERMINOLOGY"},
            {"severity": "MAJOR", "category": "GLOSSARY"},
        ]
        result = scorer.calculate_score(defects=defects)
        assert result.final_score < 100
        # 100 - (2 * 15) = 70
        assert result.final_score <= 70

    def test_minor_defects_small_penalty(self):
        scorer = ConfidenceScorer()
        defects = [{"severity": "MINOR", "category": "FORMATTING"}]
        result = scorer.calculate_score(defects=defects)
        # 100 - 5 = 95
        assert result.final_score >= 90

    def test_semantic_drift_high_penalty(self):
        scorer = ConfidenceScorer()
        result = scorer.calculate_score(
            defects=[], semantic_drift_score=0.20, source_text="Test"
        )
        assert result.final_score < 80  # -25 for high drift

    def test_structural_dosage_penalty(self):
        scorer = ConfidenceScorer()
        result = scorer.calculate_score(
            defects=[], source_text="Administer 5mg ibuprofen"
        )
        assert result.components["structural_penalty"] > 0

    def test_process_no_reflexion_penalty(self):
        scorer = ConfidenceScorer()
        result = scorer.calculate_score(
            defects=[], source_text="Test",
            process_flags={"reflexion_run": False},
        )
        assert result.components["process_penalty"] > 0

    def test_custom_weights(self):
        weights = ScoringWeights(penalty_defect_major=20.0)
        scorer = ConfidenceScorer(weights=weights)
        defects = [{"severity": "MAJOR", "category": "A"}]
        result = scorer.calculate_score(defects=defects)
        # 100 - 20 = 80
        assert result.final_score <= 80

    def test_score_never_below_zero(self):
        scorer = ConfidenceScorer()
        defects = [{"severity": "MAJOR", "category": "A"} for _ in range(20)]
        result = scorer.calculate_score(defects=defects, semantic_drift_score=0.5)
        assert result.final_score >= 0.0

    def test_bands_correct(self):
        scorer = ConfidenceScorer()
        # No defects, no structural = ~100
        r1 = scorer.calculate_score(defects=[], source_text="hello")
        assert r1.band == "Very High"

        # 2 major defects = 70
        r2 = scorer.calculate_score(
            defects=[{"severity": "MAJOR"} for _ in range(2)],
            source_text="hello",
        )
        assert r2.band in ("Medium", "High")
