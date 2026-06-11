from typing import List, Dict
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity


class PolishPack(BaseLanguagePack):
    @property
    def code(self) -> str:
        return "pl"

    @property
    def script_direction(self) -> str:
        return "ltr"

    def check_negation(
        self, source_text: str, target_text: str
    ) -> List[Dict[str, object]]:
        source_negation = re.search(
            r"\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t)\b",
            source_text,
            re.IGNORECASE,
        )

        negation_markers = ["nie", "żaden", "nigdy", "ani"]
        target_has_negation = any(
            marker in target_text.lower() for marker in negation_markers
        )

        violations = []
        if source_negation and not target_has_negation:
            v_type = ViolationType.NEGATION_FLIP
            violations.append(
                {
                    "type": v_type.value,
                    "message": f"Source contains negation '{source_negation.group(0)}' but Target lacks Polish negation markers.",
                    "severity": get_severity(v_type).value,
                    "segment_id": "unknown",
                }
            )
        return violations

    def check_numbers(self, source: str, target: str) -> List[Dict[str, object]]:
        # Word-bounded numeric check (TMX-3410). Polish uses comma decimal.
        violations = []
        for num in self._find_missing_numbers(source, target, accept_decimal_swap=True):
            v_type = ViolationType.NUMBER_MISMATCH
            violations.append(
                {
                    "type": v_type.value,
                    "message": f"Missing number {num}",
                    "severity": get_severity(v_type).value,
                }
            )
        return violations

    def check_punctuation(self, t):
        return []

    def check_variants(self, t):
        return []

    @property
    def prompt_instruction(self) -> str:
        return "ENSURE HIGH RIGOR: Use formal Polish suitable for pharmaceutical/regulatory (EMA) contexts."
