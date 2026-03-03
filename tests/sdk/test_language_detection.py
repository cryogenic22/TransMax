"""Tests for language detection."""

from transmax_sdk.language.detection import LanguageDetector


class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_english(self):
        result = self.detector.detect("This is an English sentence about medication.")
        assert result.lang_code == "en"
        assert result.confidence > 0.5

    def test_detect_french(self):
        result = self.detector.detect("Ceci est une phrase en français sur les médicaments.")
        assert result.lang_code == "fr"
        assert result.confidence > 0.5

    def test_detect_german(self):
        result = self.detector.detect("Dies ist ein deutscher Satz über Medikamente.")
        assert result.lang_code == "de"

    def test_detect_japanese(self):
        result = self.detector.detect("これは日本語の文章です。薬について。")
        assert result.lang_code == "ja"

    def test_detect_spanish(self):
        result = self.detector.detect("Esta es una oración en español sobre medicamentos.")
        assert result.lang_code == "es"

    def test_detect_arabic(self):
        result = self.detector.detect("هذه جملة باللغة العربية عن الأدوية")
        assert result.lang_code == "ar"

    def test_detect_chinese(self):
        result = self.detector.detect("这是一个关于药物的中文句子")
        assert result.lang_code in ("zh-cn", "zh-tw", "zh")

    def test_detect_korean(self):
        result = self.detector.detect("이것은 약에 관한 한국어 문장입니다")
        assert result.lang_code == "ko"

    def test_detect_italian(self):
        result = self.detector.detect("Questa è una frase italiana sui farmaci.")
        assert result.lang_code == "it"

    def test_detect_portuguese(self):
        result = self.detector.detect("Esta é uma frase em português sobre medicamentos.")
        assert result.lang_code == "pt"

    def test_empty_text_returns_undetermined(self):
        result = self.detector.detect("")
        assert result.lang_code == "und"
        assert result.confidence == 0.0

    def test_whitespace_returns_undetermined(self):
        result = self.detector.detect("   ")
        assert result.lang_code == "und"

    def test_detect_all_returns_candidates(self):
        results = self.detector.detect_all("This is clearly English text about pharmaceutical dosages.")
        assert len(results) > 0
        assert results[0].lang_code == "en"

    def test_lang_name_populated(self):
        result = self.detector.detect("Hello, this is a test in English.")
        assert result.lang_name == "English"
