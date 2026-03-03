"""Negation flip detection across languages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity

# Language-specific negation markers
NEGATION_MARKERS: Dict[str, List[str]] = {
    "en": ["not", "no", "don't", "cannot", "never", "neither", "nor", "won't"],
    "fr": ["pas", "aucun", "ne", "non", "jamais", "ni"],
    "de": ["nicht", "kein", "keine", "niemals", "nie"],
    "es": ["no", "nunca", "ningún", "ninguna", "jamás", "tampoco"],
    "it": ["non", "mai", "nessuno", "nessuna", "niente"],
    "pt": ["não", "nunca", "nenhum", "nenhuma", "jamais"],
    "ja": ["ない", "ません", "しない", "できない", "ず"],
    "ar": ["لا", "ليس", "لم", "لن", "ما", "غير"],
    "zh": ["不", "没", "无", "非", "未"],
    "ko": ["않", "못", "안", "없"],
    "nl": ["niet", "geen", "nooit", "noch"],
    "ru": ["не", "нет", "ни", "никогда", "никто"],
}


class NegationCheck:
    """Detects potential negation flips between source and target."""

    name = "negation"

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        src_markers = NEGATION_MARKERS.get(source_lang, NEGATION_MARKERS.get("en", []))
        tgt_markers = NEGATION_MARKERS.get(target_lang, [])

        if not tgt_markers:
            return []

        src_lower = f" {source_text.lower()} "
        tgt_lower = f" {target_text.lower()} "

        src_has_neg = any(f" {w} " in src_lower for w in src_markers)
        tgt_has_neg = any(f" {w} " in tgt_lower for w in tgt_markers)

        # Also check without spaces for CJK
        if not tgt_has_neg and target_lang in ("ja", "zh", "ko"):
            tgt_has_neg = any(w in target_text for w in tgt_markers)
        if not src_has_neg and source_lang in ("ja", "zh", "ko"):
            src_has_neg = any(w in source_text for w in src_markers)

        if src_has_neg and not tgt_has_neg:
            return [QualityDefect(
                category="NEGATION_FLIP",
                severity=Severity.CRITICAL,
                message="Negation in source but missing in target - potential safety risk.",
            )]
        return []
