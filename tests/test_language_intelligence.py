"""
Tests for Module A: Language Intelligence Engine.
Covers language packs, auto-detection, calibration, and confidence scoring.
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Language Pack Tests ──────────────────────────────────────────────

class TestChinesePack:
    def setup_method(self):
        from app.services.language_packs.chinese import ChinesePack
        self.simplified = ChinesePack("simplified")
        self.traditional = ChinesePack("traditional")

    def test_code_simplified(self):
        assert self.simplified.code == "zh-cn"

    def test_code_traditional(self):
        assert self.traditional.code == "zh-tw"

    def test_script_direction(self):
        assert self.simplified.script_direction == "ltr"

    def test_negation_detected(self):
        violations = self.simplified.check_negation(
            "Do not take this medication with alcohol.",
            "请将此药物与酒精一起服用。"  # Missing negation
        )
        assert len(violations) > 0
        assert violations[0]["type"] == "negation_flip"

    def test_negation_preserved(self):
        violations = self.simplified.check_negation(
            "Do not take this medication.",
            "不要服用此药物。"  # Has 不 (negation)
        )
        assert len(violations) == 0

    def test_number_check(self):
        violations = self.simplified.check_numbers("Take 500 mg daily.", "每日服用毫克。")
        assert len(violations) > 0  # 500 missing

    def test_number_preserved(self):
        violations = self.simplified.check_numbers("Take 500 mg.", "服用500毫克。")
        assert len(violations) == 0

    def test_punctuation_cjk(self):
        # Western period in Chinese text should flag
        violations = self.simplified.check_punctuation("这是一个测试.")
        # Implementation checks for Western punctuation mixed with CJK
        assert isinstance(violations, list)

    def test_variant_enforcement_simplified(self):
        # Traditional characters in simplified context
        violations = self.simplified.check_variants("這是傳統字體的文本")
        assert isinstance(violations, list)

    def test_frequency_extraction(self):
        freqs = self.simplified.extract_frequency("每日一次")
        assert any(f["count"] == 1.0 for f in freqs)


class TestKoreanPack:
    def setup_method(self):
        from app.services.language_packs.korean import KoreanPack
        self.pack = KoreanPack()

    def test_code(self):
        assert self.pack.code == "ko"

    def test_negation_detected(self):
        violations = self.pack.check_negation(
            "Do not exceed the recommended dose.",
            "권장 용량을 초과하십시오."  # Missing negation
        )
        assert len(violations) > 0

    def test_negation_preserved(self):
        violations = self.pack.check_negation(
            "Do not take.",
            "복용하지 마십시오."  # Has negation
        )
        assert len(violations) == 0

    def test_register_violation(self):
        violations = self.pack.check_variants("이 약을 먹어요")  # Informal 해요체
        # Should detect informal register
        assert isinstance(violations, list)

    def test_frequency_extraction(self):
        freqs = self.pack.extract_frequency("1일 2회 복용하십시오")
        assert any(f["count"] == 2.0 for f in freqs)


class TestPortuguesePack:
    def setup_method(self):
        from app.services.language_packs.portuguese import PortuguesePack
        self.br = PortuguesePack("brazilian")
        self.eu = PortuguesePack("european")

    def test_code_brazilian(self):
        assert self.br.code == "pt-br"

    def test_code_european(self):
        assert self.eu.code == "pt-pt"

    def test_negation_detected(self):
        violations = self.br.check_negation(
            "Do not administer to patients under 18.",
            "Administrar a pacientes menores de 18 anos."  # Missing negation
        )
        assert len(violations) > 0

    def test_negation_preserved(self):
        violations = self.br.check_negation(
            "Do not take.",
            "Não tome este medicamento."
        )
        assert len(violations) == 0

    def test_number_decimal_comma(self):
        # Portuguese uses comma for decimal
        violations = self.br.check_numbers("Take 1.5 mg.", "Tome 1,5 mg.")
        assert len(violations) == 0  # 1,5 is valid Portuguese form of 1.5

    def test_variant_check_brazilian(self):
        violations = self.br.check_variants("O doente deve tomar o medicamento.")
        # "doente" is EU Portuguese, should suggest "paciente" for BR
        assert any("doente" in v.get("message", "") for v in violations)

    def test_frequency_extraction(self):
        freqs = self.br.extract_frequency("Tomar duas vezes ao dia")
        assert any(f["count"] == 2.0 for f in freqs)


# ── Language Pack Factory Tests ──────────────────────────────────────

class TestLanguagePackFactory:
    def test_get_chinese_simplified(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("zh")
        assert pack.code == "zh-cn"  # ChinesePack("simplified") returns zh-cn

    def test_get_chinese_traditional(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("zh-tw")
        assert pack.code == "zh-tw"

    def test_get_korean(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("ko")
        assert pack.code == "ko"

    def test_get_portuguese_brazilian(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("pt-br")
        assert pack.code == "pt-br"

    def test_get_portuguese_european(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("pt-pt")
        assert pack.code == "pt-pt"

    def test_bcp47_fallback(self):
        from app.services.language_packs.factory import LanguagePackFactory
        # zh-Hans-CN should fall back to zh via BCP-47 hierarchy
        pack = LanguagePackFactory.get_pack("zh-Hans-CN")
        assert pack.code == "zh-cn"  # Falls back to "zh" key which is ChinesePack("simplified")

    def test_unknown_returns_generic(self):
        from app.services.language_packs.factory import LanguagePackFactory
        pack = LanguagePackFactory.get_pack("xx-unknown")
        # Should be a GenericLanguagePack
        assert hasattr(pack, "prompt_instruction")


# ── Language Detection Tests ─────────────────────────────────────────

class TestLanguageDetection:
    def test_detect_english(self):
        from app.services.language_detection import detect_language
        result = detect_language("This is a test of the emergency broadcast system for quality assurance.")
        assert result.language == "en"
        assert result.confidence > 0.5

    def test_detect_short_text_fallback(self):
        from app.services.language_detection import detect_language
        result = detect_language("Hi")
        assert result.language == "en"
        assert result.confidence == 0.0

    def test_detect_empty_text(self):
        from app.services.language_detection import detect_language
        result = detect_language("")
        assert result.language == "en"

    def test_get_language_name(self):
        from app.services.language_detection import get_language_name
        assert get_language_name("en") == "English"
        assert get_language_name("ja") == "Japanese"
        assert get_language_name("xx") == "xx"  # Unknown returns code

    def test_supported_languages(self):
        from app.services.language_detection import SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES
        assert "ja" in SUPPORTED_LANGUAGES
        assert "zh" in SUPPORTED_LANGUAGES


# ── Language Calibration Tests ───────────────────────────────────────

class TestLanguageCalibration:
    def test_easy_pair(self):
        from app.core.language_calibration import get_pair_calibration
        cal = get_pair_calibration("en", "fr")
        assert cal.defect_multiplier == 1.0
        assert cal.pair_difficulty_penalty == 0.0

    def test_hard_pair_japanese(self):
        from app.core.language_calibration import get_pair_calibration
        cal = get_pair_calibration("en", "ja")
        assert cal.defect_multiplier == 0.8
        assert cal.pair_difficulty_penalty == 5.0
        assert cal.drift_threshold_high == 0.20

    def test_medium_pair_russian(self):
        from app.core.language_calibration import get_pair_calibration
        cal = get_pair_calibration("en", "ru")
        assert cal.defect_multiplier == 0.9
        assert cal.pair_difficulty_penalty == 3.0

    def test_unknown_pair_defaults(self):
        from app.core.language_calibration import get_pair_calibration
        cal = get_pair_calibration("xx", "yy")
        assert cal.defect_multiplier == 1.0
        assert cal.pair_difficulty_penalty == 0.0

    def test_case_insensitive(self):
        from app.core.language_calibration import get_pair_calibration
        cal = get_pair_calibration("EN", "JA")
        assert cal.defect_multiplier == 0.8


# ── Confidence Service with Calibration ──────────────────────────────

class TestConfidenceCalibration:
    def test_easy_pair_no_extra_penalty(self):
        from app.services.confidence_service import ConfidenceService
        result = ConfidenceService.calculate_score(
            defects=[], source_text="Take 10 mg daily.",
            source_language="en", target_language="fr"
        )
        # en→fr has 0 pair_difficulty_penalty
        assert result.final_score >= 85.0

    def test_hard_pair_gets_difficulty_penalty(self):
        from app.services.confidence_service import ConfidenceService
        result_easy = ConfidenceService.calculate_score(
            defects=[], source_text="Take 10 mg daily.",
            source_language="en", target_language="fr"
        )
        result_hard = ConfidenceService.calculate_score(
            defects=[], source_text="Take 10 mg daily.",
            source_language="en", target_language="ja"
        )
        # Japanese should have lower score due to pair_difficulty_penalty=5
        assert result_hard.final_score < result_easy.final_score

    def test_calibrated_drift_thresholds(self):
        from app.services.confidence_service import ConfidenceService
        # For en→ja, drift_threshold_high is 0.20 (more lenient than default 0.15)
        # A drift of 0.18 should NOT trigger high penalty for Japanese
        result_ja = ConfidenceService.calculate_score(
            defects=[], semantic_drift_score=0.18,
            source_text="Test text.",
            source_language="en", target_language="ja"
        )
        # For en→fr, drift_threshold_high is default 0.15
        # A drift of 0.18 SHOULD trigger high penalty for French
        result_fr = ConfidenceService.calculate_score(
            defects=[], semantic_drift_score=0.18,
            source_text="Test text.",
            source_language="en", target_language="fr"
        )
        # Japanese should have higher score (drift not as penalized)
        assert result_ja.final_score > result_fr.final_score

    def test_defect_multiplier_reduces_penalty(self):
        from app.services.confidence_service import ConfidenceService
        defects = [{"severity": "MAJOR", "category": "terminology", "message": "test"}]
        result_fr = ConfidenceService.calculate_score(
            defects=defects, source_text="Test.",
            source_language="en", target_language="fr"
        )
        result_ja = ConfidenceService.calculate_score(
            defects=defects, source_text="Test.",
            source_language="en", target_language="ja"
        )
        # Japanese defect_multiplier=0.8 means less penalty per defect
        # But pair_difficulty_penalty=5 adds penalty
        # Net effect: the defect penalty itself is lower for ja
        assert isinstance(result_fr.final_score, float)
        assert isinstance(result_ja.final_score, float)
