"""Psychometric anchor preservation and sentiment drift detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity

# Validated anchor mappings
ANCHOR_MAPPINGS: Dict[str, Dict[str, List[str]]] = {
    "strongly agree": {
        "fr": ["tout à fait d'accord", "fortement d'accord"],
        "es": ["totalmente de acuerdo", "muy de acuerdo"],
        "ja": ["強くそう思う", "非常にそう思う"],
        "de": ["stimme voll zu", "stimme völlig zu"],
        "ar": ["أوافق بشدة"],
    },
    "agree": {
        "fr": ["d'accord"],
        "es": ["de acuerdo"],
        "ja": ["そう思う"],
        "de": ["stimme zu"],
        "ar": ["أوافق"],
    },
    "neutral": {
        "fr": ["neutre", "ni d'accord ni pas d'accord"],
        "es": ["neutral", "ni de acuerdo ni en desacuerdo"],
        "ja": ["どちらともいえない"],
        "de": ["neutral", "weder noch"],
        "ar": ["محايد"],
    },
    "disagree": {
        "fr": ["pas d'accord"],
        "es": ["en desacuerdo"],
        "ja": ["そう思わない"],
        "de": ["stimme nicht zu"],
        "ar": ["لا أوافق"],
    },
    "strongly disagree": {
        "fr": ["pas du tout d'accord", "fortement en désaccord"],
        "es": ["totalmente en desacuerdo", "muy en desacuerdo"],
        "ja": ["全くそう思わない"],
        "de": ["stimme überhaupt nicht zu"],
        "ar": ["لا أوافق بشدة"],
    },
}

NEGATIVE_MARKERS: Dict[str, List[str]] = {
    "en": ["not", "never", "bad", "worst", "terrible", "fail"],
    "fr": ["pas", "jamais", "mauvais", "pire", "terrible", "échec"],
    "es": ["no", "nunca", "mal", "peor", "terrible", "fallo"],
    "ja": ["ない", "悪い", "最悪", "失敗"],
    "de": ["nicht", "nie", "schlecht", "schlimmste"],
    "ar": ["لا", "أبداً", "سيء", "أسوأ"],
}


class AnalyticalCheck:
    """Checks psychometric anchor preservation and sentiment stability."""

    name = "analytical"

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        if not constraints:
            return []

        # Only run for analytical archetype
        if constraints.get("archetype") != "ANALYTICAL" and not constraints.get("check_analytical_anchors"):
            return []

        defects = []
        defects.extend(self._check_anchors(source_text, target_text, target_lang))
        defects.extend(self._check_sentiment(source_text, target_text, source_lang, target_lang))
        return defects

    def _check_anchors(self, source_text: str, target_text: str, target_lang: str) -> List[QualityDefect]:
        source_lower = source_text.lower().strip()
        target_lower = target_text.lower().strip()

        if source_lower not in ANCHOR_MAPPINGS:
            return []

        valid = ANCHOR_MAPPINGS[source_lower].get(target_lang, [])
        if valid and target_lower not in valid:
            return [QualityDefect(
                category="ANCHOR_MISMATCH",
                severity=Severity.CRITICAL,
                message=f"Anchor mismatch: expected one of {valid}, got '{target_lower}'.",
                source_text=source_text,
                suggestion=valid[0],
            )]
        return []

    def _check_sentiment(
        self, source_text: str, target_text: str, source_lang: str, target_lang: str
    ) -> List[QualityDefect]:
        src_markers = NEGATIVE_MARKERS.get(source_lang, NEGATIVE_MARKERS.get("en", []))
        tgt_markers = NEGATIVE_MARKERS.get(target_lang, [])

        if not tgt_markers:
            return []

        src_lower = source_text.lower()
        tgt_lower = target_text.lower()

        src_neg = sum(1 for w in src_markers if w in src_lower)
        tgt_neg = sum(1 for w in tgt_markers if w in tgt_lower)

        if (src_neg == 0 and tgt_neg > 0) or (src_neg > 0 and tgt_neg == 0):
            return [QualityDefect(
                category="SENTIMENT_SHIFT",
                severity=Severity.MAJOR,
                message=f"Sentiment shift: source negatives={src_neg}, target negatives={tgt_neg}.",
                source_text=source_text,
            )]
        return []
