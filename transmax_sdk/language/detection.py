"""Language detection using langdetect."""

from __future__ import annotations

from transmax_sdk.types import LanguageDetectionResult

# Language name mappings
LANG_NAMES = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
    "ja": "Japanese", "zh-cn": "Chinese (Simplified)", "zh-tw": "Chinese (Traditional)",
    "ko": "Korean", "ar": "Arabic", "hi": "Hindi", "bn": "Bengali",
    "ta": "Tamil", "vi": "Vietnamese", "th": "Thai", "tr": "Turkish",
    "pl": "Polish", "el": "Greek", "id": "Indonesian", "sv": "Swedish",
    "da": "Danish", "no": "Norwegian", "fi": "Finnish", "cs": "Czech",
    "ro": "Romanian", "hu": "Hungarian", "uk": "Ukrainian", "he": "Hebrew",
    "fa": "Persian", "ms": "Malay", "tl": "Tagalog", "sw": "Swahili",
}


class LanguageDetector:
    """Detects the language of input text using langdetect.

    Returns BCP-47 language codes with confidence scores.
    """

    def detect(self, text: str) -> LanguageDetectionResult:
        """Detect the most likely language of the text."""
        if not text or not text.strip():
            return LanguageDetectionResult(lang_code="und", confidence=0.0, lang_name="Undetermined")

        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            if results:
                top = results[0]
                code = str(top.lang)
                return LanguageDetectionResult(
                    lang_code=code,
                    confidence=top.prob,
                    lang_name=LANG_NAMES.get(code, code),
                )
        except Exception:
            pass

        return LanguageDetectionResult(lang_code="und", confidence=0.0, lang_name="Undetermined")

    def detect_all(self, text: str) -> list[LanguageDetectionResult]:
        """Detect all candidate languages with probabilities."""
        if not text or not text.strip():
            return []

        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            return [
                LanguageDetectionResult(
                    lang_code=str(r.lang),
                    confidence=r.prob,
                    lang_name=LANG_NAMES.get(str(r.lang), str(r.lang)),
                )
                for r in results
            ]
        except Exception:
            return []
