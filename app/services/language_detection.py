"""
Language auto-detection service for the translation pipeline.

Uses langdetect with confidence scoring and fallback logic.
Wired into the pipeline's validate_request node.
"""
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# BCP-47 language code normalization map
_CODE_MAP = {
    "zh-cn": "zh", "zh-tw": "zh-tw", "pt-br": "pt-br", "pt-pt": "pt-pt",
    "fr-ca": "fr-ca",
}

LANGUAGE_NAMES = {
    "en": "English", "de": "German", "fr": "French", "fr-ca": "French (Canada)",
    "es": "Spanish", "it": "Italian", "ja": "Japanese",
    "zh": "Chinese (Simplified)", "zh-tw": "Chinese (Traditional)",
    "ko": "Korean", "ar": "Arabic", "pt": "Portuguese",
    "pt-br": "Portuguese (Brazilian)", "pt-pt": "Portuguese (European)",
    "ru": "Russian", "hi": "Hindi", "bn": "Bengali", "vi": "Vietnamese",
    "tr": "Turkish", "pl": "Polish", "nl": "Dutch", "th": "Thai",
    "id": "Indonesian", "el": "Greek", "sv": "Swedish", "da": "Danish",
    "no": "Norwegian", "fi": "Finnish", "cs": "Czech", "ro": "Romanian",
    "hu": "Hungarian", "uk": "Ukrainian", "he": "Hebrew", "fa": "Persian",
    "ms": "Malay", "tl": "Tagalog", "sw": "Swahili", "ta": "Tamil",
}


@dataclass
class DetectionResult:
    language: str       # BCP-47 code
    confidence: float   # 0.0 - 1.0
    name: str           # Human-readable name
    alternatives: List[Dict[str, float]]  # Other candidates


def detect_language(text: str, min_confidence: float = 0.5) -> DetectionResult:
    """
    Detect the source language of text.

    Returns a DetectionResult with the best guess and alternatives.
    Falls back to "en" if detection fails or confidence is too low.
    """
    if not text or len(text.strip()) < 10:
        return DetectionResult(
            language="en", confidence=0.0, name="English",
            alternatives=[{"language": "en", "confidence": 0.0}],
        )

    try:
        from langdetect import detect_langs, DetectorFactory
        # Make detection deterministic
        DetectorFactory.seed = 42

        results = detect_langs(text)

        if not results:
            return _fallback()

        best = results[0]
        lang_code = str(best.lang)
        confidence = float(best.prob)

        # Normalize code
        lang_code = _CODE_MAP.get(lang_code, lang_code)

        if confidence < min_confidence:
            logger.warning(f"Language detection low confidence: {lang_code} ({confidence:.2f}), falling back to 'en'")
            return DetectionResult(
                language="en", confidence=confidence, name="English (low confidence fallback)",
                alternatives=[{"language": str(r.lang), "confidence": float(r.prob)} for r in results[:5]],
            )

        name = LANGUAGE_NAMES.get(lang_code, lang_code)
        alternatives = [{"language": str(r.lang), "confidence": float(r.prob)} for r in results[:5]]

        logger.info(f"Detected language: {lang_code} ({name}) confidence={confidence:.2f}")
        return DetectionResult(language=lang_code, confidence=confidence, name=name, alternatives=alternatives)

    except ImportError:
        logger.warning("langdetect not installed, falling back to 'en'")
        return _fallback()
    except Exception as e:
        logger.warning(f"Language detection failed: {e}, falling back to 'en'")
        return _fallback()


def _fallback() -> DetectionResult:
    return DetectionResult(
        language="en", confidence=0.0, name="English (fallback)",
        alternatives=[],
    )


def get_language_name(code: str) -> str:
    """Get human-readable name for a language code."""
    return LANGUAGE_NAMES.get(code.lower(), code)


# All supported language codes for validation
SUPPORTED_LANGUAGES = set(LANGUAGE_NAMES.keys())
