"""
Language auto-detection service for the translation pipeline.

Uses langdetect with confidence scoring and fallback logic.
Wired into the pipeline's validate_request node.
"""
import logging
from typing import Literal, Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# TMX-LANGDETECT-HOLD: why a caller could not get a confident detection.
# Carried on a non-confident DetectionResult so the graph can emit a typed
# reason into the audit chain instead of a free-text string (A1/A8).
DetectionHoldReason = Literal[
    "insufficient_text",     # text too short to attempt detection
    "no_results",             # detector ran but returned no candidates
    "low_confidence",         # detector's best guess is below min_confidence
    "detector_unavailable",   # langdetect not installed
    "detector_error",         # detector raised
]

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
    language: str       # BCP-47 code, or "und" (ISO 639-2 "undetermined") when not confident
    confidence: float   # 0.0 - 1.0
    name: str           # Human-readable name
    alternatives: List[Dict[str, float]]  # Other candidates
    # TMX-LANGDETECT-HOLD (A3/RS-06): the explicit, unignorable signal that a
    # caller must NOT treat `language` as an actionable detection. A caller
    # that reads only `.language` on a non-confident result gets "und" — a
    # real "no answer" code — never a specific wrong language.
    low_confidence: bool = False
    reason: Optional[DetectionHoldReason] = None


def detect_language(text: str, min_confidence: float = 0.5) -> DetectionResult:
    """
    Detect the source language of text.

    Returns a DetectionResult with the best guess and alternatives. Never
    silently substitutes "en" when detection is uncertain or fails (A3 /
    RS-06) — the result's `low_confidence` flag and typed `reason` make the
    uncertainty explicit for the caller to act on.
    """
    if not text or len(text.strip()) < 10:
        return DetectionResult(
            language="und", confidence=0.0, name="Undetermined (insufficient text)",
            alternatives=[], low_confidence=True, reason="insufficient_text",
        )

    try:
        from langdetect import detect_langs, DetectorFactory
        # Make detection deterministic
        DetectorFactory.seed = 42

        results = detect_langs(text)

        if not results:
            return _fallback("no_results")

        best = results[0]
        lang_code = str(best.lang)
        confidence = float(best.prob)

        # Normalize code
        lang_code = _CODE_MAP.get(lang_code, lang_code)
        alternatives = [{"language": str(r.lang), "confidence": float(r.prob)} for r in results[:5]]

        if confidence < min_confidence:
            logger.warning(
                f"Language detection low confidence: {lang_code} ({confidence:.2f}) "
                "— holding for confirmation, not defaulting to 'en'"
            )
            return DetectionResult(
                language="und", confidence=confidence, name="Undetermined (low confidence)",
                alternatives=alternatives, low_confidence=True, reason="low_confidence",
            )

        name = LANGUAGE_NAMES.get(lang_code, lang_code)

        logger.info(f"Detected language: {lang_code} ({name}) confidence={confidence:.2f}")
        return DetectionResult(language=lang_code, confidence=confidence, name=name, alternatives=alternatives)

    except ImportError:
        logger.warning("langdetect not installed — holding for confirmation, not defaulting to 'en'")
        return _fallback("detector_unavailable")
    except Exception as e:
        logger.warning(f"Language detection failed: {e} — holding for confirmation, not defaulting to 'en'")
        return _fallback("detector_error")


def _fallback(reason: DetectionHoldReason) -> DetectionResult:
    """Explicit low-confidence hold result — never a bare "en" guess (A3 / RS-06).

    `language="und"` makes the uncertainty visible in the field itself even
    if a caller forgets to check `low_confidence`.
    """
    return DetectionResult(
        language="und", confidence=0.0, name="Undetermined (detection failed)",
        alternatives=[], low_confidence=True, reason=reason,
    )


def get_language_name(code: str) -> str:
    """Get human-readable name for a language code."""
    return LANGUAGE_NAMES.get(code.lower(), code)


# All supported language codes for validation
SUPPORTED_LANGUAGES = set(LANGUAGE_NAMES.keys())
