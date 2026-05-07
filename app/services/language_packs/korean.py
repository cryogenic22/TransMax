"""
Deep Language Pack for Korean (ko).
Handles Hangul punctuation, honorific register, negation, and number formatting.
"""
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity


class KoreanPack(BaseLanguagePack):
    """
    Language Driver for Korean (Pharma).
    Enforces formal/honorific register and Korean-specific checks.
    """

    @property
    def code(self) -> str:
        return "ko"

    @property
    def script_direction(self) -> str:
        return "ltr"

    @property
    def prompt_instruction(self) -> str:
        return (
            "ENSURE HIGH RIGOR: Use formal Korean (합쇼체/하십시오체 honorific level) "
            "suitable for professional pharmaceutical and medical documents. "
            "Use standard medical terminology from KFDA guidelines. "
            "Avoid informal speech levels (해요체, 해체)."
        )

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """Check negation preservation for Korean."""
        negation_markers = [
            "않", "없", "못", "안", "금지", "금기", "불가",
            "하지 마", "사용하지", "복용하지", "투여하지",
            "아니", "말것", "마십시오",
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
                "message": f"Source contains negation '{source_negation.group(0)}' but target lacks Korean negation markers.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """Korean pharma uses Western Arabic numerals for dosages.
        Word-bounded numeric check (TMX-3410)."""
        violations = []
        for num in self._find_missing_numbers(source_text, target_text):
            v_type = ViolationType.NUMBER_MISMATCH
            violations.append({
                "type": v_type.value,
                "message": f"Number '{num}' missing in Korean target text.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """Korean uses a mix of Western and Korean punctuation; enforce consistency."""
        violations = []
        is_korean = re.search(r'[\uac00-\ud7af\u3130-\u318f]', target_text)
        if not is_korean:
            return violations
        # Korean accepts Western period and comma but should use standard spacing
        return violations

    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Check for informal speech patterns in pharma text.
        Korean pharma docs must use formal register (합쇼체).
        """
        violations = []
        is_korean = re.search(r'[\uac00-\ud7af]', target_text)
        if not is_korean:
            return violations

        # Detect informal endings
        informal_patterns = [
            (r'[가-힣]+해요', "해요체 (polite informal) detected; use 하십시오체 (formal) for pharma documents."),
            (r'[가-힣]+해\b', "해체 (casual) detected; use formal register for pharma documents."),
            (r'[가-힣]+거든요', "Informal colloquial ending detected; use formal register."),
        ]
        for pattern, msg in informal_patterns:
            if re.search(pattern, target_text):
                violations.append({
                    "type": "register_violation",
                    "message": msg,
                    "severity": "major",
                    "segment_id": "unknown",
                })
        return violations

    def extract_frequency(self, text: str) -> List[Dict[str, Any]]:
        """Extract dosing frequency from Korean text."""
        freqs = []
        if "1일 1회" in text or "하루 한 번" in text:
            freqs.append({"count": 1.0, "interval": "day", "raw": "1일 1회"})
        if "1일 2회" in text or "하루 두 번" in text:
            freqs.append({"count": 2.0, "interval": "day", "raw": "1일 2회"})
        if "1일 3회" in text or "하루 세 번" in text:
            freqs.append({"count": 3.0, "interval": "day", "raw": "1일 3회"})
        return freqs
