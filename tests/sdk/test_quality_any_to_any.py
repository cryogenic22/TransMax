"""Tests for quality checks on non-English source languages."""

from transmax_sdk.quality.gate import PharmaQualityGate
from transmax_sdk.types import Severity


class TestAnyToAnyQualityChecks:
    def test_fr_to_de_numeric_check(self):
        gate = PharmaQualityGate()
        defects = gate.check_segment(
            source_text="Prendre 10mg par jour",
            target_text="Täglich einnehmen",
            source_lang="fr",
            target_lang="de",
        )
        critical = [d for d in defects if d.severity == Severity.CRITICAL]
        assert len(critical) > 0  # Missing 10

    def test_fr_to_de_clean(self):
        gate = PharmaQualityGate()
        defects = gate.check_segment(
            source_text="Bonjour",
            target_text="Guten Tag",
            source_lang="fr",
            target_lang="de",
        )
        assert len(defects) == 0

    def test_ja_to_ar_numeric_preserved(self):
        gate = PharmaQualityGate()
        defects = gate.check_segment(
            source_text="毎日10mg服用",
            target_text="تناول 10 ملغ يومياً",
            source_lang="ja",
            target_lang="ar",
        )
        # 10 is present in both
        numeric_defects = [d for d in defects if d.category == "NUMERIC_MISMATCH"]
        assert len(numeric_defects) == 0

    def test_de_to_es_negation_check(self):
        gate = PharmaQualityGate()
        defects = gate.check_segment(
            source_text="Nicht einnehmen",
            target_text="Tomar diariamente",  # Missing negation
            source_lang="de",
            target_lang="es",
        )
        negation_defects = [d for d in defects if d.category == "NEGATION_FLIP"]
        assert len(negation_defects) > 0

    def test_source_lang_passed_to_plugins(self):
        """Ensure source_lang is correctly propagated to all plugins."""
        gate = PharmaQualityGate()
        # This should not crash even with exotic pairs
        defects = gate.check_segment(
            source_text="Test 123",
            target_text="Test 123",
            source_lang="ko",
            target_lang="vi",
        )
        assert isinstance(defects, list)
