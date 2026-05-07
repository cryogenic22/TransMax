"""
Deep Language Pack for Chinese (Simplified & Traditional).
Handles CJK punctuation, number formatting, negation markers,
and pharma-specific terminology enforcement.
"""
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity


class ChinesePack(BaseLanguagePack):
    """
    Language Driver for Chinese (zh / zh-cn / zh-tw).
    Covers Simplified and Traditional with pharma-grade checks.
    """

    def __init__(self, variant: str = "simplified"):
        super().__init__()
        self._variant = variant  # "simplified" or "traditional"

    @property
    def code(self) -> str:
        return "zh-cn" if self._variant == "simplified" else "zh-tw"

    @property
    def script_direction(self) -> str:
        return "ltr"

    @property
    def prompt_instruction(self) -> str:
        if self._variant == "traditional":
            return (
                "ENSURE HIGH RIGOR: Use formal Traditional Chinese (zh-TW) suitable for "
                "professional/medical contexts in Taiwan. Use Traditional character forms only. "
                "Do NOT mix Simplified characters."
            )
        return (
            "ENSURE HIGH RIGOR: Use formal Simplified Chinese (zh-CN) for professional/medical "
            "contexts in mainland China. Use Simplified character forms only. "
            "Do NOT mix Traditional characters."
        )

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """Check negation preservation for Chinese."""
        negation_markers = [
            "不", "没有", "没", "无", "非", "未", "勿", "禁止", "禁忌",
            "切勿", "不可", "不得", "不要", "不能", "不应",
        ]
        source_negation = re.search(
            r'\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t|avoid|prohibited|contraindicated|do not)\b',
            source_text, re.IGNORECASE
        )

        target_has_negation = any(marker in target_text for marker in negation_markers)

        violations = []
        if source_negation and not target_has_negation:
            v_type = ViolationType.NEGATION_FLIP
            violations.append({
                "type": v_type.value,
                "message": f"Source contains negation '{source_negation.group(0)}' but target lacks Chinese negation markers.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Chinese pharma uses Western (Arabic) numerals for dosages.
        Word-bounded numeric check (TMX-3410).
        """
        violations = []
        for num in self._find_missing_numbers(source_text, target_text):
            v_type = ViolationType.NUMBER_MISMATCH
            violations.append({
                "type": v_type.value,
                "message": f"Number '{num}' missing in Chinese target text.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Enforce Chinese punctuation rules:
        - Use Chinese full stop (。) not Western period
        - Use Chinese comma (，) not Western comma
        - Use Chinese brackets and quotation marks
        """
        violations = []
        is_chinese = re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', target_text)
        if not is_chinese:
            return violations

        # Check Western comma in Chinese text
        if ',' in target_text and '，' not in target_text:
            violations.append({
                "type": "cjk_punctuation",
                "message": "Found Western comma ',' in Chinese text; expected '，' (fullwidth comma).",
                "severity": "major",
                "segment_id": "unknown",
            })

        # Check Western period (not in numbers)
        if re.search(r'(?<!\d)\.(?!\d)', target_text) and '。' not in target_text:
            v_type = ViolationType.PUNCTUATION
            violations.append({
                "type": v_type.value,
                "message": "Found Western period '.' in Chinese text; expected '。' (ideographic full stop).",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })

        return violations

    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Enforce character set consistency.
        Simplified text should not contain Traditional-only characters and vice versa.
        """
        violations = []
        # Common Traditional↔Simplified mismatches in pharma context
        if self._variant == "simplified":
            traditional_only = ["藥", "醫", "療", "處", "與", "對", "進", "開"]
            simplified_equiv = ["药", "医", "疗", "处", "与", "对", "进", "开"]
            for trad, simp in zip(traditional_only, simplified_equiv):
                if trad in target_text and simp not in target_text:
                    violations.append({
                        "type": "variant_mismatch",
                        "message": f"Traditional character '{trad}' found in Simplified Chinese text; use '{simp}'.",
                        "severity": "major",
                        "segment_id": "unknown",
                    })
        return violations

    def extract_frequency(self, text: str) -> List[Dict[str, Any]]:
        """Extract dosing frequency from Chinese text."""
        freqs = []
        if "每日一次" in text or "一天一次" in text:
            freqs.append({"count": 1.0, "interval": "day", "raw": "每日一次"})
        if "每日两次" in text or "一天两次" in text or "每日二次" in text:
            freqs.append({"count": 2.0, "interval": "day", "raw": "每日两次"})
        if "每日三次" in text or "一天三次" in text:
            freqs.append({"count": 3.0, "interval": "day", "raw": "每日三次"})
        return freqs
